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
import logging
logger = logging.getLogger("snagrecover")

from snagrecover.protocols import fel
from snagrecover.firmware.firmware import run_firmware
from snagrecover.config import recovery_config
from snagrecover.utils import get_usb, access_error, prettify_usb_addr

USB_TIMEOUT = 5000
USB_RETRY = 5

def main():
	# Try to reset device
	usb_addr = recovery_config["usb_path"]

	# FEL devices seem to require a slightly special retry procedure, which
	# is why we don't just call get_usb from utils.
	for i in range(USB_RETRY):
		dev = get_usb(usb_addr, error_on_fail=False, retries=0)
		if dev is None:
			if i == USB_RETRY - 1:
				access_error("USB FEL", prettify_usb_addr(usb_addr))
			logger.info("Failed to find device, retrying...")
			continue
		try:
			dev.reset()
		except usb.core.USBError as err:
			logger.info("Failed to reset USB device, retrying...")
			if i == USB_RETRY - 1:
				raise Exception("Maximum retry count exceeded") from err
			time.sleep(2)
			continue
		break

	# Try to set device configuration
	for i in range(USB_RETRY):
		dev = get_usb(usb_addr, error_on_fail=False, retries=0)
		if dev is None:
			if i == USB_RETRY - 1:
				access_error("USB FEL", prettify_usb_addr(usb_addr))
			logger.info("Failed to find device, retrying...")
			continue
		try:
			dev.set_configuration()
		except usb.core.USBError as err:
			logger.info("Failed to initialize device, retrying...")
			if i == USB_RETRY - 1:
				raise Exception("Maximum retry count exceeded") from err
			time.sleep(1)
			continue
		break

	fel_dev = fel.FEL(dev, USB_TIMEOUT)

	for i in range(USB_RETRY):
		try:
			fel_dev.verify_device()
		except (usb.core.USBError, Exception) as err:
			if i == USB_RETRY - 1:
				raise Exception("Maximum retry count exceeded") from err
			time.sleep(1)
			continue
		break
	# user can supply images separately or in a single file
	if "u-boot-with-spl" in recovery_config["firmware"]:
		run_firmware(fel_dev, "u-boot-with-spl")
	else:
		run_firmware(fel_dev, "spl")
		run_firmware(fel_dev, "u-boot")

