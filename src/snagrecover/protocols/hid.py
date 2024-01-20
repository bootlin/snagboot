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

ITEM_TYPE_MAIN     = 0
ITEM_TYPE_GLOBAL   = 1

MAIN_ITEM_TAG_INPUT  = 8
MAIN_ITEM_TAG_OUTPUT = 9

GLOBAL_ITEM_TAG_REPORT_ID = 8

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

class HIDShortItem():
	def __init__(self, desc, long=False):
		self.bType = (desc[0] & 0xc) >> 2
		self.bTag = (desc[0] & 0xf0) >> 4
		bSize = desc[0] & 0x3
		full_size = 1 + (4 if bSize == 3 else bSize)
		self.data = None if full_size <= 1 else int.from_bytes(desc[1:], byteorder='little', signed=False)

class HIDReportDesc():
	def is_long_item(header):
		return header == 0b11111110

	def __init__(self, parent):
		self.parent = parent
		self.size = parent.hid_desc.wDescriptorLength
		self.desc = usb.control.get_descriptor(parent.usb_dev, self.size, usb.DT_REPORT, parent.main_intf.bInterfaceNumber)
		if self.desc is None:
			parent.err("Failed to fetch Report descriptor!")

		# Collect items
		self.items = []
		offset = 0
		while offset < self.size:
			header = self.desc[offset]
			if __class__.is_long_item(header):
				continue

			bSize = header & 0x3
			size = 4 if bSize == 3 else bSize
			item = HIDShortItem(self.desc[offset:offset + size + 1])
			item.offset = offset

			self.items.append(item)
			offset += 1 + size

class HIDDesc():
	SIZE = 9

	def find_hid_desc(self, full_cfg_desc):
		offset = 0
		while offset < len(full_cfg_desc):
			desc_size = full_cfg_desc[offset]
			if desc_size == 0:
				self.parent.err("Invalid descriptor size 0!")

			desc_type = full_cfg_desc[offset + 1]
			if desc_type == usb.DT_HID:
				self.desc = full_cfg_desc[offset:offset+desc_size]
				return

			offset += desc_size

		self.parent.err("Failed to find HID descriptor!")

	def __init__(self, parent):
		self.parent = parent
		# The HID descriptor is located right after the interface descriptor
		# i.MX ROM SDP devices don't seem to support querying Interface or HID descriptors
		# directly, so we query the full cfg descriptor and find the HID descriptor inside
		full_cfg_desc = usb.control.get_descriptor(parent.usb_dev, parent.main_cfg.wTotalLength, usb.DT_CONFIG, parent.main_cfg.index)
		if full_cfg_desc is None:
			parent.err("Failed to fetch full Configuration descriptor")

		self.find_hid_desc(full_cfg_desc)
		desc = self.desc

		self.bLength = desc[0]
		ver_maj = desc[3]
		ver_min = desc[2]
		self.bcdHID = (ver_maj << 8) | ver_min
		self.bNumDescriptors = desc[5]
		self.bDescriptorType = desc[6]
		self.wDescriptorLength = (desc[8] << 8) | desc[7]

		# Assume the first class descriptor is a Report.
		# Ignore other class descriptors. Don't fetch optional descriptor
		if self.bNumDescriptors == 0 or self.bDescriptorType != usb.DT_REPORT:
			parent.err(f"HID descriptor has unexpected values for bNumDescriptors and/or bDescriptorType! num: {self.bNumDescriptors} type:0x{self.bDescriptorType:x}")

class HIDReport():
	def __init__(self, item: HIDShortItem, report_id: int):
		self.output = item.bTag == MAIN_ITEM_TAG_OUTPUT
		self.id = report_id

	def __repr__(self):
		return f"(type: {'output' if self.output else 'input'}, id: {self.id})"

class HIDStateTable():
	def __init__(self, report_desc: HIDReportDesc):
		# Fully-fledged HID parsers have nested collections with
		# different types of items, we just use a big array and dump all
		# of the in/out reports in it
		self.reports = []
		self.global_report_id = None

		for item in report_desc.items:
			if item.bType == ITEM_TYPE_MAIN and item.bTag in [MAIN_ITEM_TAG_INPUT, MAIN_ITEM_TAG_OUTPUT]:
				self.reports.append(HIDReport(item, self.global_report_id))
			elif item.bType == ITEM_TYPE_GLOBAL and item.bTag == GLOBAL_ITEM_TAG_REPORT_ID:
				self.global_report_id = item.data

		logger.info("HID State Table has report items: {self.reports}")

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
			print(f"Expected cfg {self.main_cfg.bConfigurationValue} but device {pretty_addr} has cfg {cur_cfg.bConfigurationValue} instead, attempting to set cfg...")
			self.usb_dev.set_configuration(self.main_cfg.bConfigurationValue)

		if self.usb_dev.is_kernel_driver_active(self.main_intf.bInterfaceNumber):
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
			try:
				usb.util.claim_interface(self.usb_dev, self.main_intf.bInterfaceNumber)
			except usb.USBError as err:
				raise OSError(f"Failed to claim interface {self.main_intf.bInterfaceNumber} of USB device {pretty_addr}, maybe something else is using this device?") from err

			self.hid_desc = HIDDesc(self)
			self.report_desc = HIDReportDesc(self)
			self.item_table = HIDStateTable(self.report_desc)
			self.read = self.libusb_read
			self.write = self.libusb_write
			self.hidraw = None

			# Set reporting frequency to 0 for all reports
			self.set_idle(0, 0)

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

	def find_report_by_id(self, report_id: int):
		for report in self.item_table.reports:
			if report.id == report_id:
				return report
		return None

	def set_report(self, report_id: int, data: bytes):
		report = self.find_report_by_id(report_id)
		if report is None:
			raise HIDError(f"No HID report found with ID {report_id}")

		bmRequestType = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_RECIPIENT_INTERFACE
		bRequest = CTRL_HID_SET_REPORT
		wValue = (REPORT_TYPE_OUTPUT if report.output else REPORT_TYPE_INPUT) & 0xff00
		wValue |= report_id & 0x00ff
		wIndex = self.main_intf.bInterfaceNumber

		return self.usb_dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data)

	def get_report(self, report_id: int, length: int):
		report = self.find_report_by_id(report_id)
		if report is None:
			raise HIDError(f"No HID report found with ID {report_id}")

		bmRequestType = usb.util.CTRL_IN | usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_RECIPIENT_INTERFACE
		bRequest = CTRL_HID_GET_REPORT
		wValue = (REPORT_TYPE_OUTPUT if report.output else REPORT_TYPE_INPUT) & 0xff00
		wValue |= report_id & 0x00ff
		wIndex = self.main_intf.bInterfaceNumber
		wLength = length

		return self.usb_dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, wLength)

	def libusb_read(self, length: int, timeout: int):
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

