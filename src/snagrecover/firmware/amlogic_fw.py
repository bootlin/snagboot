# This file is part of Snagboot
# Copyright (C) 2025 Bootlin
#
# Written by François Foltete <francois.foltete@bootlin.com> in 2025.
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
# Based on pyamlboot (https://github.com/superna9999/pyamlboot):
# MIT License

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging

logger = logging.getLogger("snagrecover")

from snagrecover.protocols.amlogic import (
	identify_rom,
	log_rom_id,
	write_large_memory,
	run,
	get_next_AMLC_block,
	write_AMLC_block,
	write_blob_simple_memory,
	ROM_STAGE_MINOR,
	ROM_STAGE_MINOR_SPL,
)
from snagrecover.config import recovery_config
from snagrecover.firmware.firmware import load_fw, get_fw_path
from time import sleep

# Protocol 1 constants'
BL2_DEFAUT_LOAD_ADDR = 0xFFFA_0000
BL2_START_OFFSET = 0
BL2_END_OFFSET = 0x1_0000
BL2_BLOCK_LENGTH = 4096


# Default load addresses for protocol 2
GX_BL2_LOAD_ADDR = 0xD900_0000
GX_BL2_RUNPARA_LOAD_ADDR = 0xD900_C000
GX_UBOOT_LOAD_ADDR = 0x200_C000

AXG_BL2_LOAD_ADDR = 0xFFFC_0000
AXG_BL2_RUNPARA_LOAD_ADDR = 0xFFFC_C000
AXG_UBOOT_LOAD_ADDR = 0x200_C000

BL2_BLOCK_LENGTH = 64
UBOOT_BLOCK_LENGTH = 16384


# Seems to be BL2 DDR initialisation sequence
USBBL2_RUNPARA_DDRINIT: bytes = bytes.fromhex(
	# Seems to be a magic number
	"ABCD 1234"
	# Seems to be a version number
	"0002 0000"
	# Seems to be a command
	"DFC0 0000"
	# Undetermined
	"0100 0000 0000 4000 CCC0 8200 0000 0010 0000 0000"
)

# Seems to be BL2 run FIP image sequence
USBBL2_RUNPARA_RUNFIPIMG: bytes = bytes.fromhex(
	# Seems to be a magic number
	"ABCD 1234"
	# Seems to be a version number
	"0002 0000"
	# Seems to be a command
	"E1C0 0000"
	# Undetermined
	"0100 0000 0000 0000 00C0 0000 0100 0000 00C0 0002 0040 0A00 5762 CC85 C67E 5E10 D4F8 84DF"
)


def get_load_addr(
	fw_name: str, load_addr_field: str, default_load_addr: int | None
) -> int:
	"""
	Retrieve load address from firmware name from recovery config.
	If not found in recovery config use 'default_load_addr', if 'default_load_addr' is None,
	raise KeyError.
	"""
	try:
		load_addr = recovery_config["firmware"][fw_name][load_addr_field]
	except KeyError:
		if default_load_addr is not None:
			load_addr = default_load_addr
			logger.warning(
				f"'{fw_name}'':'{load_addr_field}' not found in firmware file, using default address {default_load_addr:#x}"
			)
		else:
			err_msg = f"'{fw_name}'':'{load_addr_field}' not found in firmware file, and no default load address"
			logger.critical(err_msg)
			raise KeyError(err_msg) from None

	return load_addr


def protocol_1_run(port, fw_name: str, fw_blob: bytes, subfw_name: str) -> None:
	if subfw_name == "BL2":
		logger.debug("Sending BL2 to ROM Code...")
		log_rom_id(identify_rom(port))

		bl2_load_addr = get_load_addr(
			"u-boot-fip", "bl2-load-addr", BL2_DEFAUT_LOAD_ADDR
		)

		write_large_memory(
			port,
			bl2_load_addr,
			fw_blob[BL2_START_OFFSET:BL2_END_OFFSET],
			BL2_BLOCK_LENGTH,
		)
		logger.debug("Starting BL2...")
		run(port, bl2_load_addr)

	elif subfw_name == "U-Boot":
		logger.debug("Sending U-Boot to BL2...")
		prev_length = -1
		prev_offset = -1
		seq = 0
		uboot_fip_size = len(fw_blob)

		(length, offset) = get_next_AMLC_block(port)
		while (length, offset) != (prev_length, prev_offset):
			logger.debug(
				f"Sequence #{seq}, AMLC requested: {offset=}, {length=} of firmware 'u-boot-fip'"
			)

			try:
				# Don't blindly trust ROM Code indexes.
				# Furthermore, slices don't raise exceptions for these cases.
				if offset <= 0:
					raise ValueError(
						f"BL2 asked a negative offset ({offset}) for an AMLC block."
					)
				if length <= 0:
					raise ValueError(
						f"BL2 asked for negative length ({length}) for an AMLC block."
					)
				if (offset + length) > uboot_fip_size:
					raise ValueError(
						f"BL2 asked for a AMLC block ({offset=}, {length=}) overflowing u-boot-fip firmware ({uboot_fip_size})"
					)
			except ValueError as ve:
				logger.critical(ve)
				raise ve

			write_AMLC_block(port, seq, offset, fw_blob[offset : offset + length])

			(prev_length, prev_offset) = (length, offset)
			seq += 1
			(length, offset) = get_next_AMLC_block(port)

	else:
		# sanity check
		err_msg = f"Unexpected subfirmware '{subfw_name}'"
		logger.critical(err_msg)
		raise ValueError(err_msg)


def protocol_2_run(port, fw_name: str, fw_blob: bytes) -> None:
	gx_socs = [
		# GXL
		"s905d",
		"s905x",
		"s905w",
		"s905l",
		"s905m2",
		"s805x",
		"s805y",
		# GXM
		"s912",
		# GXBB
		"s905",
		"s905h",
		"s905m",
	]
	axg_socs = [
		"a113x",
		"a113d",
	]

	soc_model = recovery_config["soc_model"]
	if soc_model in gx_socs:
		bl2_load_addr = GX_BL2_LOAD_ADDR
		bl2_runpara_load_addr = GX_BL2_RUNPARA_LOAD_ADDR
		default_uboot_load_addr = GX_UBOOT_LOAD_ADDR
	elif soc_model in axg_socs:
		bl2_load_addr = AXG_BL2_LOAD_ADDR
		bl2_runpara_load_addr = AXG_BL2_RUNPARA_LOAD_ADDR
		default_uboot_load_addr = AXG_UBOOT_LOAD_ADDR
	else:
		err_msg = f"No BL2 load address for SoC {soc_model}"
		logger.critical(err_msg)
		raise ValueError(err_msg)

	uboot_load_addr = get_load_addr("u-boot", "load-addr", default_uboot_load_addr)

	if fw_name == "bl2":
		log_rom_id(identify_rom(port))

		logger.debug(f"Sending firmware 'bl2' ({get_fw_path('bl2')})")
		bl2_blob = fw_blob
		# we actually need write_simple_memory request here
		# contrary as when we send BL2 to load U-Boot (tested on s905x)
		write_blob_simple_memory(port, bl2_load_addr, bl2_blob)

		logger.debug("Sending BL2 DDR initialisation sequence")
		ddr_init_blob = USBBL2_RUNPARA_DDRINIT
		# For very small firmware like "ddr_init_blob" send the file in one go
		write_large_memory(
			port, bl2_runpara_load_addr, ddr_init_blob, block_length=len(ddr_init_blob)
		)

		logger.debug("Starting firmware 'bl2'")
		run(port, bl2_load_addr)
		logger.debug("Waiting for firmware 'bl2'...")
		sleep(1)
		rom_id = identify_rom(port)
		log_rom_id(rom_id)
		if ord(rom_id[ROM_STAGE_MINOR]) == ROM_STAGE_MINOR_SPL:
			logger.debug("Starting BL2 DDR initialisation sequence")
			run(port, bl2_runpara_load_addr)
			logger.debug("Waiting for BL2 DDR initialisation sequence...")
			sleep(1)

	elif fw_name == "u-boot":
		bl2_blob = load_fw("bl2")
		logger.debug(f"Sending firmware 'bl2' ({get_fw_path('bl2')})")
		write_large_memory(port, bl2_load_addr, bl2_blob, block_length=BL2_BLOCK_LENGTH)

		run_fip_img_blob = USBBL2_RUNPARA_RUNFIPIMG
		logger.debug("Sending BL2 run FIP image sequence")
		# For very small firmware like "run-fip-img" send the file in one go
		write_large_memory(
			port, bl2_runpara_load_addr, run_fip_img_blob, len(run_fip_img_blob)
		)

		u_boot_blob = fw_blob
		logger.debug(f"Sending firmware 'u-boot' ({get_fw_path('u-boot')})")
		write_large_memory(
			port,
			uboot_load_addr,
			u_boot_blob,
			block_length=UBOOT_BLOCK_LENGTH,
			append_zeros=True,
		)

		rom_id = identify_rom(port)
		log_rom_id(rom_id)
		if ord(rom_id[ROM_STAGE_MINOR]) == ROM_STAGE_MINOR_SPL:
			logger.debug("Starting firmware 'u-boot'")
			run(port, bl2_runpara_load_addr)
		else:
			logger.debug("Starting firmware 'bl2'")
			run(port, bl2_load_addr)


def amlogic_run(port, fw_name: str, fw_blob: bytes, subfw_name: str) -> None:
	if fw_name == "u-boot-fip":
		protocol_1_run(port, fw_name, fw_blob, subfw_name)

	elif fw_name in ["bl2", "u-boot"]:
		protocol_2_run(port, fw_name, fw_blob)

	else:
		err_msg = f"Unexpected firmware '{fw_name}'"
		logger.critical(err_msg)
		raise ValueError(err_msg)
