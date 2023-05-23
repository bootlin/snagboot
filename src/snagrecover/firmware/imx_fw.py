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
#
# Based on NXP mfgtools (https://github.com/nxp-imx/mfgtools):
# Copyright 2018 NXP.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright notice, this
# list of conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.
#
# Neither the name of the Freescale Semiconductor nor the names of its
# contributors may be used to endorse or promote products derived from this
# software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import logging
logger = logging.getLogger("snagrecover")
from snagrecover.protocols import imx_sdp
from snagrecover.protocols import memory_ops
from snagrecover.firmware import ivt
from snagrecover.firmware import rom_container
from snagrecover.config import recovery_config
from snagrecover import utils

dcd_addr = {
"imx6q": 0x00910000,
"imx6sx": 0x00910000,
"imx6d": 0x00910000,
"imx6sl": 0x00910000,
"imx7d": 0x00911000,
"imx6ul": 0x00910000,
"imx6ull": 0x00910000,
"imx6sll": 0x00910000,
"imx8mq": 0x00910000,
"imx8mm": 0x00910000,
"imx7ulp": 0x2f018000,
"imxrt106x": 0x1000
}

def imx_run(port, fw_name: str, fw_blob: bytes, subfw_name: str = ""):
	MAX_DOWNLOAD_SIZE = 0x200000
	soc_model = recovery_config["soc_model"]

	sdp_cmd = imx_sdp.SDPCommand(port)
	memops = memory_ops.MemoryOps(sdp_cmd)

	if fw_name == "u-boot-sdps":
		write_size = rom_container.get_container_size(fw_blob)
		ret = sdp_cmd.sdps_write(fw_blob, write_size)
		if not ret:
			raise ValueError("Error: failed to write first stage firmware")
		return None

	ivtable = ivt.IVT()
	if ivtable.from_blob(fw_blob) is None:
		raise ValueError("Error: No IVT header in boot image")

	if fw_name == "u-boot-with-dcd":
		# WRITE DEVICE CONFIGURATION DATA
		print("Writing Device Configuration Data...")
		if ivtable.dcd == 0:
			raise ValueError("Error: No DCD data in boot image")
		logger.info("Writing DCD...")
		dcd_offset = ivtable.offset + ivtable.dcd - ivtable.addr
		if fw_blob[dcd_offset] != 0xd2:
			raise ValueError("Error: Invalid DCD tag")
		write_addr = dcd_addr.get(soc_model, None)
		if write_addr is None:
			raise ValueError("Error: DCD is not supported for this chip, please choose a boot image without DCD.")
		dcd_size = int.from_bytes(fw_blob[dcd_offset + 1:dcd_offset + 3], "big")
		sdp_cmd.write_dcd(fw_blob[dcd_offset:dcd_offset + dcd_size], write_addr, 0, dcd_size)
		dcd_offset = ivtable.offset + ivtable.dcd - ivtable.addr
		print("Done")
		logger.info("Done writing DCD")

	logger.info(f"Downloading firmware {fw_name}...")
	if fw_name == "flash-bin" and subfw_name == "u-boot":
		"""
		get uboot/atf offset and size by assuming that it is located immediately after the
		section of the boot image that we previously downloaded to the board
		"""
		write_offset = ivtable.offset + ivtable.boot_data["length"] - (ivtable.addr - ivtable.boot_data["start"])
		write_size = len(fw_blob) - write_offset
		if	write_size <= 0:
			raise ValueError("Error: Invalid offset found for U-BOOT proper in boot image")
		# We ask for a write at 0 but SPL should determine u-boot proper's
		# write address on its own
		print("Downloading file...")
		memops.write_blob(fw_blob, 0, write_offset, write_size)
		print("Done\nJumping to firmware...")
		memops.jump(0)
		return None
	else:
		write_size = ivtable.boot_data["length"] - (ivtable.addr - ivtable.boot_data["start"])
		# If the IVT offset is large enough, the write can overflow the source buffer
		if write_size > len(fw_blob) - ivtable.offset:
			logger.warning("Write size is too large, truncating...")
			write_size = len(fw_blob) - ivtable.offset
		# protocols other than SPLV/U have a maximum download size
		# split download into chunks < MAX_DOWNLOAD_SIZE
		chunk_offset = 0
		print("Downloading file...")
		for chunk in utils.dnload_iter(fw_blob[ivtable.offset:ivtable.offset + write_size], 0x200000):
			memops.write_blob(chunk, ivtable.addr + chunk_offset, chunk_offset, len(chunk))
			chunk_offset += MAX_DOWNLOAD_SIZE
		print("Done")

	if fw_name in ["u-boot-with-dcd", "SPL"] or (fw_name == "flash-bin" and subfw_name == "spl"):
		if soc_model in ["imx6q","imx6d","imx6sl"]:
			# CLEAR DCD
			print("Clearing Device Configuration Data...")
			logger.info("Clearing DCD...")
			"""
			Re-copy the IVT with dcd address set to 0.
			Some socs will write a whole report2 transfer (1024 bytes) to memory,
			so we have to copy more than just the ivt to avoid overriting other
			data.
			"""
			if len(fw_blob[ivtable.offset:]) < 1024:
				logger.warning("Boot image is too small to clear DCD")
			else:
				new_ivt = bytearray(fw_blob[ivtable.offset:ivtable.offset + 1024])
				new_ivt[12:16] = bytearray(b"\x00\x00\x00\x00")
				memops.write_blob(new_ivt, ivtable.addr, 0, 1024)
			logger.info("Done clearing DCD")
			print("Done")
		else:
			# SEND SKIP_DCD_HEADER
			print("Skipping DCD header...")
			logger.info("Skipping DCD...")
			sdp_cmd.skip_dcd_header()
			logger.info("Done skipping DCD")
			print("Done")

	# JUMP TO FIRMWARE
	logger.info(f"Jumping to firmware {fw_name}")
	print(f"Jumping to {fw_name}...")
	memops.jump(ivtable.addr)
	return None

