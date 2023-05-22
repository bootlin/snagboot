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
from snagrecover.firmware.firmware import run_firmware
from snagrecover.config import recovery_config
from snagrecover.utils import parse_usb,get_usb
import logging
logger = logging.getLogger("snagrecover")

USB_TIMEOUT = 10

###################### main ##################################

def main():
	soc_model = recovery_config["soc_model"]
	# USB ENUMERATION
	usb_vid = recovery_config["rom_usb"][0]
	usb_pid = recovery_config["rom_usb"][1]
	dev = get_usb(usb_vid, usb_pid)
	cfg = dev.get_active_configuration()
	logger.debug("USB config:")
	for line in str(cfg).splitlines():
		logger.debug(line)
	logger.debug("End of USB config:")

	# DOWNLOAD TF-A
	dfu_cmd = dfu.DFU(dev)
	run_firmware(dev, "tf-a")
	if soc_model == "stm32mp13":
		print("Sending detach command to SPL...")
		phase_id = dfu_cmd.stm32_get_phase()
		dfu_cmd.detach(phase_id)

	# DOWNLOAD FLASH LAYOUT TO BEGINNING OF RAM
	if soc_model == "stm32mp15":
		phase_id = dfu_cmd.stm32_get_phase()
		part0 = dfu.search_partid(dev, "@Partition0", match_prefix=True)
		if part0 is None:
			raise Exception("No DFU altsetting found with iInterface='Partition0*'")
		if phase_id == part0:
			print("Downloading flash layout...")
			layout_blob = flashlayout.build_image()
			dfu_cmd.download_and_run(layout_blob, part0, offset=0, size=len(layout_blob))

	# DOWNLOAD U-BOOT
	if soc_model == "stm32mp13":
		time.sleep(1.5)
	# We need to reset here, in the case where TF-A uses a different USB ID
	if "usb" in recovery_config["firmware"]["tf-a"]:
		(usb_vid,usb_pid) = parse_usb(recovery_config["firmware"]["tf-a"]["usb"])
		try:
			dev.reset()
		except usb.core.USBError:
			# this should actually fail
			pass
		time.sleep(0.5)
	usb.util.dispose_resources(dev)
	dev = get_usb(usb_vid, usb_pid)
	cfg = dev.get_active_configuration()
	dfu_cmd = dfu.DFU(dev)
	run_firmware(dev, "fip")

	# DETACH DFU DEVICE
	print("Sending detach command to SPL...")
	phase_id = dfu_cmd.stm32_get_phase()
	dfu_cmd.detach(phase_id)

