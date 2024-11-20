# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

"""
This is not meant as a complete implementation of the
USB HID class specification. Only the class features
required by snagrecover are handled.
I still tried to follow core HID types and concepts
so that this library can be easily extended if more
HID features are required.
"""

from snagrecover.utils import prettify_usb_addr
import glob
import usb
import os
import platform
import select
import re
import logging
logger = logging.getLogger("snagrecover")

CTRL_HID_GET_REPORT   = 0x1
CTRL_HID_SET_REPORT   = 0x9
CTRL_HID_SET_IDLE     = 0xa

# Used by (GET/SET)_REPORT
REPORT_TYPE_INPUT    = 0x1
REPORT_TYPE_OUTPUT   = 0x2

def get_descriptor(dev, desc_size, desc_type, desc_index):
	return dev.ctrl_transfer(0x81 if desc_type == usb.DT_REPORT else 0x80, 6, (desc_type << 8) | desc_index, 0, desc_size)

class HIDError(Exception):
	"Raised to signal failed I/O or invalid HID data in USB descriptors"
	pass

def is_hid(dev: usb.core.Device):
	if dev.bDeviceClass == usb.CLASS_HID:
		return True
	for cfg in dev:
		if usb.util.find_descriptor(cfg, bInterfaceClass=usb.CLASS_HID) is not None:
			return True
	return False

def match_intr_in(desc) -> bool:
	match = bool(desc.bDescriptorType & usb.DT_ENDPOINT)
	match &= bool(desc.bmAttributes & usb.ENDPOINT_TYPE_INTERRUPT)
	match &= bool(desc.bEndpointAddress & usb.ENDPOINT_IN)
	return match

class HIDDevice():
	def err(self, msg):
		err = f"Error while handling HID device {self.pretty_addr}:"
		err += msg
		raise HIDError(err)

	def get_hidraw_device(self):
		intf_sysfs = f"/sys/bus/usb/devices/{self.pretty_addr}:{self.main_cfg.bConfigurationValue}.{self.main_intf.bInterfaceNumber}"
		hidraw_glob = intf_sysfs + "/*/hidraw/hidraw*/uevent"
		devname_regex = re.compile("DEVNAME=(.*)\n")
		results = glob.glob(hidraw_glob)
		if len(results) == 0:
			return None
		uevent = results[0]
		with open(uevent, "r") as file:
			uevent_txt = file.read(-1)

		matches = devname_regex.findall(uevent_txt)
		if len(matches) == 0:
			return None

		hidraw_path = f"/dev/{matches[0]}"
		if not os.path.exists(hidraw_path):
			return None

		return hidraw_path

	def __init__(self, usb_dev: usb.core.Device):
		pretty_addr = prettify_usb_addr((usb_dev.bus, usb_dev.port_numbers))
		if not is_hid(usb_dev):
			raise IOError(f"Device {pretty_addr}, is USB but not HID!")

		self.usb_dev = usb_dev
		self.pretty_addr = pretty_addr

		self.main_cfg = None
		self.main_intf = None
		for cfg in usb_dev:
			intf = usb.util.find_descriptor(cfg, bInterfaceClass=usb.CLASS_HID)
			if intf is not None:
				self.main_cfg = cfg
				self.main_intf = intf
				break


		cur_cfg = self.usb_dev.get_active_configuration()
		if cur_cfg.bConfigurationValue != self.main_cfg.bConfigurationValue:
			logger.info(f"Expected cfg {self.main_cfg.bConfigurationValue} but device {pretty_addr} has cfg {cur_cfg.bConfigurationValue} instead, attempting to set cfg...")
			self.usb_dev.set_configuration(self.main_cfg.bConfigurationValue)

		if platform.system() == "Linux" and self.usb_dev.is_kernel_driver_active(self.main_intf.bInterfaceNumber):
			# The kernel driver in question should be usbhid
			hidraw_path = self.get_hidraw_device()
			if hidraw_path is None:
				raise OSError(f"Failed to find an hidraw device associated with {self.pretty_addr}")
			self.read = self.hidraw_read
			self.write = self.hidraw_write
			self.hidraw_path = hidraw_path
			self.hidraw = open(self.hidraw_path, "rb+", buffering=0)
			logger.info(f"HID device {pretty_addr} has hidraw dev {hidraw_path}")

		else:
			# This case is for systems which don't
			# have usbhid loaded for some reason.
			# It is also suitable for Windows. if
			# the system HID driver has been replaced
			# with the correct libusb driver beforehand.
			try:
				usb.util.claim_interface(self.usb_dev, self.main_intf.bInterfaceNumber)
			except usb.USBError as err:
				raise OSError(f"Failed to claim interface {self.main_intf.bInterfaceNumber} of USB device {pretty_addr}, maybe something else is using this device?") from err

			# Set reporting frequency to 0 for all reports
			try:
				self.set_idle(0, 0)
			except usb.USBError:
				pass

			self.read = self.libusb_read
			self.write = self.libusb_write
			self.hidraw = None

			logger.info(f"HID device {pretty_addr} has no hidraw dev")

		# get interrupt IN endpoint
		self.intr_in = usb.util.find_descriptor(self.main_intf, custom_match=match_intr_in)
		if self.intr_in is None:
			self.err("Could not find interrupt IN endpoint!")

		# ignore the optional interrupt OUT endpoint

		logger.info("Finished initializing HID device {pretty_addr}")

	def set_idle(self, report_id: int, duration: int):
		bmRequestType = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_RECIPIENT_INTERFACE
		bRequest = CTRL_HID_SET_IDLE
		wValue = duration & 0xff00
		wValue |= report_id & 0x00ff
		wIndex = self.main_intf.bInterfaceNumber
		wLength = 0

		return self.usb_dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, wLength)

	def set_report(self, report_id: int, data: bytes):
		bmRequestType = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_RECIPIENT_INTERFACE
		bRequest = CTRL_HID_SET_REPORT
		wValue = (REPORT_TYPE_OUTPUT << 8) & 0xff00
		wValue |= report_id & 0x00ff
		wIndex = self.main_intf.bInterfaceNumber
		logger.debug(f"set_report id {report_id} data length: {len(data)}")

		return self.usb_dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data)

	def libusb_read(self, length: int, timeout: int):
		logger.debug(f"HID libusb read length: {length}")
		data = self.intr_in.read(length + 1)[1:]
		if isinstance(data, int) or data is None:
			raise HIDError("Failed to read {length + 1} bytes from HID device")

		return bytes(data)

	def close(self):
		if self.hidraw:
			self.hidraw.close()
		else:
			usb.util.release_interface(self.usb_dev, self.main_intf.bInterfaceNumber)

	def hidraw_read(self, length: int, timeout: int):
		r,w,e = select.select([self.hidraw], [], [], timeout)
		if self.hidraw not in r:
			raise HIDError(f"Timeout while attempting to read {length} bytes from HID device {self.pretty_addr}")
		# Add one byte for the report id prepended by hidraw
		return self.hidraw.read(length + 1)[1:]

	def libusb_write(self, data: bytes):
		report_id = data[0]
		self.set_report(report_id, data)

	def hidraw_write(self, data: bytes):
		return self.hidraw.write(data)

