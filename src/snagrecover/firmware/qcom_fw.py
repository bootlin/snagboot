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
Qualcomm firmware handling for Sahara protocol.
"""

import logging
from snagrecover.config import recovery_config
from snagrecover.utils import cli_error

logger = logging.getLogger("snagrecover")


def qcom_run(sahara, fw_name: str, fw_blob: bytes):
	"""
	Transfer Qualcomm firmware via Sahara protocol.

	This function:
	Transfers the firmware to the device via QSahara protocol along with
    image_id

	Args:
		sahara: QSahara protocol instance
		fw_name: Firmware name (e.g., 'xbl', 'u-boot')
		fw_blob: Firmware binary data (bytes)

	Raises:
		cli_error: If firmware name is unknown or firmware is empty
		Exception: If transfer fails
	"""
	# Get Sahara image ID for this firmware
	image_id = 0
	for key, value in recovery_config['firmware'].items():
		if key == fw_name:
			image_id = value['image_id']
	logger.debug(f"Firmware '{fw_name}' maps to image ID {image_id:#x}")

	# Validate firmware size
	if len(fw_blob) == 0:
		cli_error(f"Firmware {fw_name} is empty")

	# Transfer via Sahara protocol
	try:
		sahara.transfer_image(image_id, fw_blob)
	except Exception as e:
		logger.error(f"Failed to transfer {fw_name}: {e}")
		raise
