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

import logging
logger = logging.getLogger("snagrecover")
from snagrecover.protocols import dfu
from snagrecover.firmware.imx_fw import imx_run
from snagrecover.firmware.sama5_fw import sama5_run
from snagrecover.firmware.am335x_fw import am335x_run
from snagrecover.firmware.sunxi_fw.sunxi_fw import sunxi_run
from snagrecover.config import recovery_config
from snagrecover.utils import cli_error
import usb

def stm32mp1_run(port: usb.core.Device, fw_name: str, fw_blob: bytes):
	"""
	There isn't a lot of complicated logic to handle stm32mp1 firmware
	so we can leave it in the common module for now
	"""
	if fw_name == "tf-a":
		partprefix = "@FSBL"
	elif fw_name == "fip":
		partprefix = "@Partition3"
	else:
		cli_error(f"unsupported firmware {fw_name}")
	print("Searching for partition id...")
	partid = dfu.search_partid(port, partprefix, match_prefix=True)
	if partid is None and partprefix == "@Partition3":
		partprefix = "@SSBL"
		partid = dfu.search_partid(port, partprefix, match_prefix=True)
	if partid is None:
		raise Exception(f"No DFU altsetting found with iInterface='{partprefix}*'")
	dfu_cmd = dfu.DFU(port)
	print("Downloading file...")
	dfu_cmd.download_and_run(fw_blob, partid, offset=0, size=len(fw_blob))
	print("Done")
	return None

def am62x_run(dev: usb.core.Device, fw_name: str, fw_blob: bytes):
	"""
	There isn't a lot of complicated logic to handle am62x firmware
	so we can leave it in the common module for now
	"""
	# find firmware altsetting (i.e. partition id)
	if fw_name == "tiboot3":
		partname = "bootloader"
	elif fw_name == "tispl":
		partname = "tispl.bin"
	elif fw_name == "u-boot":
		partname = "u-boot.img"
	else:
		cli_error(f"unsupported firmware {fw_name}")
	print("Searching for partition id...")
	partid = dfu.search_partid(dev, partname)
	if partid is None:
		raise Exception(f"No DFU altsetting found with iInterface='{partname}'")
	dfu_cmd = dfu.DFU(dev, stm32=False)
	print("Downloading file...")
	dfu_cmd.download_and_run(fw_blob, partid, offset=0, size=len(fw_blob))
	print("Done")
	if fw_name == "tispl":
		# run tispl firmware
		print("Sending detach command...")
		dfu_cmd.detach(partid)

def run_firmware(port, fw_name: str, subfw_name: str = ""):
	"""
	The "subfw_name" option allows selecting firmware
	subimages inside the same image. This avoids
	having the user pass the same binary in two different
	configs.
	"""
	soc_family = recovery_config["soc_family"]
	try:
		fw_path = recovery_config["firmware"][fw_name]["path"]
	except KeyError:
		cli_error(f"Could not find firmware {fw_name}, please check your recovery config")
	with open(fw_path, "rb") as file:
		fw_blob = file.read(-1)

	print(f"Installing firmware {fw_name}")
	if subfw_name != "":
		print(f"Subfirmware: {subfw_name}")
	if soc_family == "sama5":
		sama5_run(port, fw_name, fw_blob)
	elif soc_family == "stm32mp1":
		stm32mp1_run(port, fw_name, fw_blob)
	elif soc_family == "imx":
		imx_run(port, fw_name, fw_blob, subfw_name)
	elif soc_family == "am335x":
		am335x_run(port, fw_name)
	elif soc_family == "sunxi":
		sunxi_run(port, fw_name, fw_blob)
	elif soc_family == "am62x":
		am62x_run(port, fw_name, fw_blob)
	else:
		raise Exception(f"Unsupported SoC family {soc_family}")
	print(f"Done installing firmware {fw_name}")

