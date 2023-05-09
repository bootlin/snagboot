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

import usb.core
import usb.util
import time
from snagrecover.protocols import dfu
from snagrecover.recoveries import stm32_flashlayout as flashlayout
from snagrecover.firmware.firmware import install_firmware
import logging
logger = logging.getLogger("snagrecover")

USB_TIMEOUT = 10
USB_VID = 0x0483
USB_PID = 0xdf11

###################### main ##################################

def main() -> None:
	#USB ENUMERATION
	dev = usb.core.find(idVendor=USB_VID, idProduct=USB_PID)
	if dev is None:
		raise ValueError('STM32 USB device not found')
	cfg = dev.get_active_configuration()
	logger.debug("USB config:")
	for line in str(cfg).splitlines():
		logger.debug(line)
	logger.debug("End of USB config:")

	#DOWNLOAD TF-A
	install_firmware(dev, "tf-a")

	#DOWNLOAD FLASH LAYOUT TO BEGINNING OF RAM 
	dfu_cmd = dfu.DFU(dev)
	phase_id = dfu_cmd.stm32_get_phase()
	part0 = dfu.search_partid(dev, "@Partition0", match_prefix=True)
	if part0 is None:
		raise Exception("No DFU altsetting found with iInterface='Partition0*'")
	if phase_id == part0:
		print("Downloading flash layout...")
		layout_blob = flashlayout.build_image()
		dfu_cmd.download_and_run(layout_blob, FLASHLAYOUT_PARTID, offset=0, size=len(layout_blob))

	#DOWNLOAD U-BOOT
	install_firmware(dev, "u-boot")

	#DETACH DFU DEVICE
	print("Sending detach command to U-BOOT...")
	phase_id = dfu_cmd.stm32_get_phase()
	dfu_cmd.detach(phase_id)

