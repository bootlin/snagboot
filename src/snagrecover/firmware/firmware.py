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
from snagrecover.protocols.fastboot import Fastboot
from snagrecover.config import recovery_config
from snagrecover.utils import cli_error


def stm32mp_run(port, fw_name: str, fw_blob: bytes):
	"""
	There isn't a lot of complicated logic to handle stm32mp firmware
	so we can leave it in the common module for now
	"""
	if fw_name == "tf-a":
		partprefixes = ["@FSBL"]
	elif fw_name == "fip":
		partprefixes = ["@Partition3", "@SSBL", "@FIP"]
	elif fw_name == "fip-ddr":
		partprefixes = ["@DDR FIP"]
	else:
		cli_error(f"unsupported firmware {fw_name}")

	logger.info("Searching for partition id...")

	partid = None
	for partprefix in partprefixes:
		partid = dfu.search_partid(port, partprefix, match_prefix=True)
		if partid is not None:
			break

	if partid is None:
		raise Exception(f"No DFU altsetting found with iInterface in '{partprefixes}*'")
	dfu_cmd = dfu.DFU(port)
	logger.info("Downloading file...")
	dfu_cmd.download_and_run(fw_blob, partid, offset=0, size=len(fw_blob))

	if fw_name == "fip-ddr":
		logger.info("Sending detach command...")
		partid = dfu.search_partid(port, "@FIP", match_prefix=True)
		dfu_cmd.detach(partid)

	logger.info("Done")
	return None


def am6x_run(dev, fw_name: str, fw_blob: bytes):
	"""
	There isn't a lot of complicated logic to handle am6x firmware
	so we can leave it in the common module for now
	"""
	# find firmware altsetting (i.e. partition id)
	if fw_name == "tiboot3":
		partname = "bootloader"
	elif fw_name == "sysfw":
		partname = "sysfw.itb"
	elif fw_name == "tispl":
		partname = "tispl.bin"
	elif fw_name == "u-boot":
		partname = "u-boot.img"
	else:
		cli_error(f"unsupported firmware {fw_name}")
	logger.info("Searching for partition id...")
	partid = dfu.search_partid(dev, partname)
	if partid is None:
		raise Exception(f"No DFU altsetting found with iInterface='{partname}'")
	dfu_cmd = dfu.DFU(dev, stm32=False)
	logger.info("Downloading file...")
	dfu_cmd.download_and_run(fw_blob, partid, offset=0, size=len(fw_blob))
	logger.info("Done")
	if fw_name in ["u-boot", "sysfw"]:
		logger.info("Sending detach command...")
		dfu_cmd.detach(partid)


def am62lx_run(dev, fw_name: str, fw_blob: bytes):
	# find firmware altsetting (i.e. partition id)
	if fw_name == "tiboot3":
		partname = "bootloader"
	elif fw_name == "tispl":
		partname = "bootloader"
	elif fw_name == "u-boot":
		partname = "u-boot.img"
	else:
		cli_error(f"unsupported firmware {fw_name}")
	logger.info("Searching for partition id...")
	partid = dfu.search_partid(dev, partname)
	if partid is None:
		raise Exception(f"No DFU altsetting found with iInterface='{partname}'")
	dfu_cmd = dfu.DFU(dev, stm32=False)
	logger.info("Downloading file...")
	dfu_cmd.download_and_run(fw_blob, partid, offset=0, size=len(fw_blob))
	logger.info("Done")
	if fw_name == "u-boot":
		logger.info("Sending detach command...")
		dfu_cmd.detach(partid)


def keembay_run(port, fw_name: str, fw_blob: bytes):
	if fw_name == "fip":
		pass
	else:
		cli_error(f"unsupported firmware {fw_name}")

	logger.info("Searching for partition id...")

	fb_cmd = Fastboot(port)
	logger.info("Downloading file...")
	fb_cmd.download(fw_blob)
	logger.info("Done")

	return None


def check_fw_blob(fw_blob: bytes):
	"""
	Do a quick sanity check on the firmware contents.  If the file passed
	to snagrecover looks like a text file, issue a warning. This can help
	avoid troubleshooting obscure recovery errors caused by simply passing
	the wrong file to snagrecover.
	"""

	first_512 = fw_blob[:512]

	try:
		first_512.decode("ascii")
		first_512.decode("utf-8")
	except UnicodeDecodeError:
		return True

	return False


def get_fw_path(fw_name: str) -> str:
	try:
		fw = recovery_config["firmware"][fw_name]
	except KeyError:
		cli_error(
			f"Could not find firmware {fw_name} in recovery_config, please check your recovery config"
		)
	try:
		fw_path = fw["path"]
	except KeyError:
		cli_error(
			f"Could not find firmware {fw_name} path in recovery config, please check your recovery config"
		)
	return fw_path


def load_fw(fw_name: str, check_fw: bool = True) -> bytes:
	fw_path = get_fw_path(fw_name)

	with open(fw_path, "rb") as file:
		fw_blob = file.read(-1)

	if check_fw and not check_fw_blob(fw_blob):
		logger.warning(f"File {fw_path} looks like a text file!")

	return fw_blob


def run_firmware(port, fw_name: str, subfw_name: str = ""):
	"""
	The "subfw_name" option allows selecting firmware
	subimages inside the same image. This avoids
	having the user pass the same binary in two different
	configs.
	"""

	fw_blob = load_fw(fw_name)

	logger.info(f"Installing firmware {fw_name}")
	if subfw_name != "":
		logger.info(f"Subfirmware: {subfw_name}")

	soc_family = recovery_config["soc_family"]
	if soc_family == "sama5":
		from snagrecover.firmware.sama5_fw import sama5_run

		sama5_run(port, fw_name, fw_blob)
	elif soc_family == "stm32mp":
		stm32mp_run(port, fw_name, fw_blob)
	elif soc_family == "keembay":
		keembay_run(port, fw_name, fw_blob)
	elif soc_family == "imx":
		from snagrecover.firmware.imx_fw import imx_run

		imx_run(port, fw_name, fw_blob, subfw_name)
	elif soc_family == "am335x":
		from snagrecover.firmware.am335x_fw import am335x_run

		am335x_run(port, fw_name)
	elif soc_family == "sunxi":
		from snagrecover.firmware.sunxi_fw.sunxi_fw import sunxi_run

		sunxi_run(port, fw_name, fw_blob)
	elif soc_family == "am6x":
		am6x_run(port, fw_name, fw_blob)
	elif soc_family == "am62lx":
		am62lx_run(port, fw_name, fw_blob)
	elif soc_family == "zynqmp":
		from snagrecover.firmware.zynqmp_fw import zynqmp_run

		zynqmp_run(port, fw_name, fw_blob, subfw_name)
	elif soc_family == "bcm":
		from snagrecover.firmware.bcm import bcm_run

		bcm_run(port, fw_name, fw_blob, subfw_name)
	elif soc_family == "amlogic":
		from snagrecover.firmware.amlogic_fw import amlogic_run

		amlogic_run(port, fw_name, fw_blob, subfw_name)
	else:
		raise Exception(f"Unsupported SoC family {soc_family}")
	logger.info(f"Done installing firmware {fw_name}")
