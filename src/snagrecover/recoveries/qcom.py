# This file is part of Snagboot
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
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

"""
Qualcomm SoC recovery via Sahara protocol.

Orchestrates firmware transfer to Qualcomm devices in EDL mode.
"""

from snagrecover.protocols.qcom_sahara import QSahara
from snagrecover.firmware.firmware import run_firmware
from snagrecover.config import recovery_config
from snagrecover.utils import get_usb
import logging
import time

logger = logging.getLogger("snagrecover")

def main():
	"""
	Main recovery function for Qualcomm devices.
	Orchestrates the QSahara protocol-based recovery process.

	The recovery_config dictionary is populated by the CLI and contains:
	- soc_model: The Qualcomm SoC model
	- usb_path: USB device path (for USB mode)
	- firmware: Dictionary of firmware images to transfer
	"""
	soc_model = recovery_config["soc_model"]
	logger.debug(f"Starting Qualcomm recovery for {soc_model}")

	try:
		usb_dev = get_usb(recovery_config["usb_path"])
		sahara = QSahara(usb_dev)

		# Transfer each firmware image
		firmware_list = list(recovery_config["firmware"].keys())
		logger.info(f"Firmware images to transfer: {firmware_list}")

		for fw_name in firmware_list:
			run_firmware(sahara, fw_name)

		# Cleanup
		sahara.close()

		logger.debug("Qualcomm recovery complete")

	except RuntimeError as e:
		logger.error(f"Failed to initialize QSahara: {e}")
		raise
	except Exception as e:
		logger.error(f"Recovery failed: {e}")
		raise
