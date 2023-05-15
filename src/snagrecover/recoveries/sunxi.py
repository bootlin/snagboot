# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
# 
# Written by Romain Gantois <romain.gantois@bootlin.com> in 2023.
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

import usb
import time
from snagrecover.protocols import fel
from snagrecover.protocols import memory_ops
from snagrecover.firmware.firmware import run_firmware
from snagrecover.config import recovery_config
from snagrecover.utils import access_error

USB_TIMEOUT = 5000
USB_RETRY = 10
USB_VID = 0x1f3a
USB_PID = 0xefe8

def main():
	#Try to reset device
	for i in range(USB_RETRY):
		dev = usb.core.find(idVendor=USB_VID, idProduct=USB_PID)
		if dev is None:
			if i == USB_RETRY - 1:
				access_error("USB FEL", f"{USB_VID:04x}:{USB_PID:04x}")
			print("Failed to find device, retrying...")
			continue
		try:
			dev.reset()
		except usb.core.USBError:
			print("Failed to reset USB device, retrying...")
			if i == USB_RETRY - 1:
				raise Exception("Maximum retry count exceeded")
			time.sleep(2)
			continue
		break

	#Try to set device configuration
	for i in range(USB_RETRY):
		dev = usb.core.find(idVendor=USB_VID, idProduct=USB_PID)
		if dev is None:
			if i == usb_retry - 1:
				access_error("USB FEL", f"{USB_VID:04x}:{USB_PID:04x}")
			print("Failed to find device, retrying...")
			continue
		try:
			dev.set_configuration()
		except usb.core.USBError:
			print("Failed to initialize device, retrying...")
			if i == USB_RETRY - 1:
				raise Exception("Maximum retry count exceeded")
			time.sleep(1)
			continue
		break


	fel_dev = fel.FEL(dev, USB_TIMEOUT)
	memops = memory_ops.MemoryOps(fel_dev)

	for i in range(USB_RETRY):
		try:
			ret = fel_dev.verify_device()
		except usb.core.USBError or Exception:
			if i == USB_RETRY - 1:
				raise Exception("Maximum retry count exceeded")
			time.sleep(1)
			continue
		break
	#user can supply images separately or in a single file
	if "u-boot-with-spl" in recovery_config["firmware"]:
		run_firmware(fel_dev, "u-boot-with-spl")
	else:
		run_firmware(fel_dev, "spl")
		run_firmware(fel_dev, "u-boot")

