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
from snagrecover.utils import get_usb
import logging

logger = logging.getLogger("snagrecover")

USB_TIMEOUT = 10


def main():
	soc_model = recovery_config["soc_model"]

	# Choose first stage, must be TF-A or SPL,  implicit if only one present,
	# explicit  by "first_stage" config property otherwise
	fw_config = recovery_config["firmware"]
	first_stages = ("tf-a", "spl")
	explicit_first_stage = fw_config.get("first_stage")
	if explicit_first_stage is None:
		first_stage = None
		for fs in first_stages:
			if fs in fw_config:
				if first_stage is None:
					first_stage = fs
				else:
					raise Exception(
						"Multiple first stage binaries specified - need explicit first_stage config"
					)
		logger.info("Selected first stage '%s' implicitly", first_stage)
	else:
		if explicit_first_stage not in first_stages:
			raise Exception(
				f"Explicit first stage '{explicit_first_stage}' is not supported, must be one of '{first_stages}''"
			)

		if explicit_first_stage not in fw_config:
			raise Exception(
				f"No binary configured for explicit first stage '{explicit_first_stage}'"
			)

		first_stage = explicit_first_stage
		logger.info("Selected first stage '%s' explicitly", first_stage)

	# USB ENUMERATION
	usb_addr = recovery_config["usb_path"]
	dev = get_usb(usb_addr)

	# DOWNLOAD First stage
	dfu_cmd = dfu.DFU(dev)
	run_firmware(dev, first_stage)
	if soc_model in ["stm32mp13", "stm32mp25"]:
		logger.info("Sending detach command to SPL...")
		phase_id = dfu_cmd.stm32_get_phase()
		dfu_cmd.detach(phase_id)

	# DOWNLOAD FLASH LAYOUT TO BEGINNING OF RAM
	# Configuration of the flashing phase is out of scope for
	# Snagrecover so we only download a dummy flash layout
	if soc_model == "stm32mp15" and first_stage == "tf-a":
		phase_id = dfu_cmd.stm32_get_phase()
		part0 = dfu.search_partid(dev, "@Partition0", match_prefix=True)
		if part0 is None:
			raise Exception("No DFU altsetting found with iInterface='Partition0*'")
		if phase_id == part0:
			logger.info("Downloading flash layout...")
			layout_blob = flashlayout.build_image()
			dfu_cmd.download_and_run(
				layout_blob, part0, offset=0, size=len(layout_blob)
			)

	if soc_model == "stm32mp13":
		time.sleep(1.5)

	try:
		dev.reset()
	except usb.core.USBError:
		# this should actually fail
		pass
	time.sleep(0.5)

	usb.util.dispose_resources(dev)
	dev = get_usb(usb_addr)
	dfu_cmd = dfu.DFU(dev)

	if soc_model == "stm32mp25":
		run_firmware(dev, "fip-ddr")
		time.sleep(1)

	usb.util.dispose_resources(dev)
	dev = get_usb(usb_addr)
	dfu_cmd = dfu.DFU(dev)

	second_stage = {"tf-a": "fip", "spl": "u-boot"}[first_stage]
	run_firmware(dev, second_stage)

	# DETACH DFU DEVICE
	logger.info("Sending detach command to U-Boot...")
	if first_stage == "tfa-a":
		phase_id = dfu_cmd.stm32_get_phase()
	else:
		phase_id = 0
	dfu_cmd.detach(phase_id)
