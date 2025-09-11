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

from struct import pack, unpack
from usb.util import (
	ENDPOINT_IN,
	ENDPOINT_OUT,
	CTRL_IN,
	CTRL_OUT,
	CTRL_TYPE_VENDOR,
	CTRL_RECIPIENT_DEVICE,
)
from snagrecover.utils import dnload_iter

EP_IN = 1
EP_OUT = 2

REQ_WRITE_MEM = 0x01
REQ_READ_MEM = 0x02
REQ_FILL_MEM = 0x03
REQ_MODIFY_MEM = 0x04
REQ_RUN_IN_ADDR = 0x05
REQ_WRITE_AUX = 0x06
REQ_READ_AUX = 0x07

REQ_WR_LARGE_MEM = 0x11
REQ_RD_LARGE_MEM = 0x12
REQ_IDENTIFY_HOST = 0x20

# Here TPL stands for U-Boot proper
# it is different from U-Boot TPL
REQ_TPL_CMD = 0x30
REQ_TPL_STAT = 0x31

REQ_WRITE_MEDIA = 0x32
REQ_READ_MEDIA = 0x33

REQ_BULKCMD = 0x34

REQ_PASSWORD = 0x35
REQ_NOP = 0x36

REQ_GET_AMLC = 0x50
REQ_WRITE_AMLC = 0x60

FLAG_KEEP_POWER_ON = 0x10

AMLC_AMLS_BLOCK_LENGTH = 0x200
AMLC_MAX_BLOCK_LENGTH = 0x4000
AMLC_MAX_TRANSFERT_LENGTH = 0x10000

MAX_LARGE_BLOCK_COUNT = 65535

WRITE_MEDIA_CHEKSUM_ALG_NONE = 0x00EE
WRITE_MEDIA_CHEKSUM_ALG_ADDSUM = 0x00EF
WRITE_MEDIA_CHEKSUM_ALG_CRC32 = 0x00F0

ROM_VERSION_MAJOR = 0
ROM_VERSION_MINOR = 1
ROM_STAGE_MAJOR = 2
ROM_STAGE_MINOR = 3
ROM_NEED_PASSWORD = 4
ROM_PASSWORD_OK = 5

# rom_id[ROM_STAGE_MINOR] ==
ROM_STAGE_MINOR_IPL = 0  # ROM Code stage
ROM_STAGE_MINOR_SPL = 8  # BL2 stage
# Here TPL stands for U-Boot proper it is different from U-Boot TPL
ROM_STAGE_MINOR_TPL = 16  # U-Boot proper stage

TRANSFERT_TIMEOUT = 1000  # milliseconds


def identify_rom(dev) -> str:
	"""
	Identify the ROM Protocol
	"""
	ret = dev.ctrl_transfer(
		bmRequestType=CTRL_IN | CTRL_RECIPIENT_DEVICE | CTRL_TYPE_VENDOR,
		bRequest=REQ_IDENTIFY_HOST,
		wValue=0,
		wIndex=0,
		data_or_wLength=8,
	)

	rom_id = "".join([chr(c) for c in ret])

	return rom_id


def log_rom_id(rom_id: str) -> None:
	"""
	Helper function to log a debug message of ROM Protocol.
	rom_id is the result of identify_rom.
	"""
	logger.debug(
		"Firmware Version : "
		+ "ROM: %d.%d, "
		% (ord(rom_id[ROM_VERSION_MAJOR]), ord(rom_id[ROM_VERSION_MINOR]))
		+ "Stage: %d.%d, "
		% (ord(rom_id[ROM_STAGE_MAJOR]), ord(rom_id[ROM_STAGE_MINOR]))
		+ "Need Password: %d Password OK: %d"
		% (ord(rom_id[ROM_NEED_PASSWORD]), ord(rom_id[ROM_PASSWORD_OK]))
	)


def write_simple_memory(dev, address: int, data: bytes) -> None:
	if len(data) > 64:
		raise ValueError(f"len(data)={len(data)} surpasses maximum length of 64 bytes")

	dev.ctrl_transfer(
		bmRequestType=CTRL_OUT | CTRL_RECIPIENT_DEVICE | CTRL_TYPE_VENDOR,
		bRequest=REQ_WRITE_MEM,
		wValue=(address >> 16) & 0xFFFF,
		wIndex=address & 0xFFFF,
		data_or_wLength=data,
	)


def write_blob_simple_memory(dev, address: int, blob: bytes) -> None:
	"""
	Helper function to write blob of binary data using N*write_simple_memory
	"""
	offset = 0
	for chunk in dnload_iter(blob, 64):
		write_simple_memory(dev, address + offset, chunk)
		offset += len(chunk)


def write_large_memory(
	dev, address: int, data: bytes, block_length: int = 64, append_zeros: bool = False
) -> None:
	"""
	Write 'data' at 'address' by chunk of 'block_length' size.
	The length of 'data' must be a multiple of 'block_length'.
	You can set 'append_zeros' to True to pad 'data' with zeros so it
	respect this rule.
	"""
	if append_zeros:
		# pad data with zeros so its len is a multiple of block_length
		data = data + pack("b", 0) * (block_length - len(data) % block_length)
	if len(data) % block_length != 0:
		raise ValueError(
			f"'data' length ({len(data)}) is not a multiple of block_length ({block_length})"
		)

	offset = 0
	for block in dnload_iter(data, MAX_LARGE_BLOCK_COUNT):
		block_count = len(block) // block_length + (
			1 if len(block) % block_length else 0
		)
		control_data = pack("<IIII", address + offset, len(block), 0, 0)
		dev.ctrl_transfer(
			bmRequestType=CTRL_OUT | CTRL_RECIPIENT_DEVICE | CTRL_TYPE_VENDOR,
			bRequest=REQ_WR_LARGE_MEM,
			wValue=block_length,
			wIndex=block_count,
			data_or_wLength=control_data,
		)

		for chunk in dnload_iter(block, block_length):
			dev.write(ENDPOINT_OUT | EP_OUT, chunk, TRANSFERT_TIMEOUT)

		offset += len(block)


def run(dev, address: int, keep_power=True) -> None:
	"""Run code from memory"""
	data = address | (FLAG_KEEP_POWER_ON if keep_power else 0)

	control_data = pack("<I", data)
	dev.ctrl_transfer(
		bmRequestType=CTRL_OUT | CTRL_RECIPIENT_DEVICE | CTRL_TYPE_VENDOR,
		bRequest=REQ_RUN_IN_ADDR,
		wValue=(address >> 16) & 0xFFFF,
		wIndex=address & 0xFFFF,
		data_or_wLength=control_data,
	)


def get_next_AMLC_block(dev) -> tuple[int, int]:
	"""Retrieve requested u-boot-fip block, as a length and offset, from BL2."""
	dev.ctrl_transfer(
		bmRequestType=CTRL_OUT | CTRL_RECIPIENT_DEVICE | CTRL_TYPE_VENDOR,
		bRequest=REQ_GET_AMLC,
		wValue=AMLC_AMLS_BLOCK_LENGTH,
		wIndex=0,
		data_or_wLength=None,
	)

	boot_data = dev.read(ENDPOINT_IN | EP_IN, AMLC_AMLS_BLOCK_LENGTH, TRANSFERT_TIMEOUT)
	(tag, length, offset) = unpack("<4s4xII", boot_data[0:16])

	if "AMLC" not in "".join(map(chr, tag)):
		err_msg = f"Invalid AMLC Request {boot_data[0:16]}"
		logger.critical(err_msg)
		raise ValueError(err_msg)

	# Ack the request
	ack_out = pack("<4sIII", bytes("OKAY", "ascii"), 0, 0, 0)
	dev.write(ENDPOINT_OUT | EP_OUT, ack_out, TRANSFERT_TIMEOUT)

	return (length, offset)


def compute_AMLS_checksum(data: bytes) -> int:
	"""
	Calculate data checksum for AMLS transfert.
	unsigned 32 bit additive checksum
	"""
	checksum = 0
	UINT32_MASK = 0xFFFF_FFFF

	for chunk in dnload_iter(data, 4):
		val = int.from_bytes(chunk, byteorder="little", signed=False)
		checksum = (checksum + val) & UINT32_MASK

	return checksum


def write_AMLC_sub_blocks(dev, offset: int, data: bytes) -> None:
	"""Write a AMLC block transfer in sub blocks to BL2."""
	dev.ctrl_transfer(
		bmRequestType=0x40,
		bRequest=REQ_WRITE_AMLC,
		wValue=offset // AMLC_AMLS_BLOCK_LENGTH,
		wIndex=len(data) - 1,
		data_or_wLength=None,
	)

	for chunk in dnload_iter(data, AMLC_MAX_BLOCK_LENGTH):
		dev.write(ENDPOINT_OUT | EP_OUT, chunk, TRANSFERT_TIMEOUT)

	ack_in = dev.read(ENDPOINT_IN | EP_IN, 16, TRANSFERT_TIMEOUT)
	if "OKAY" not in "".join(map(chr, ack_in[0:4])):
		err_msg = f"Invalid ACK IN ({ack_in} != OKAY) after AMLC transfer"
		logger.critical(err_msg)
		raise ValueError(err_msg)


def write_AMLC_block(dev, seq: int, amlc_offset: int, data: bytes) -> None:
	"""Write requested u-boot-fip block (retrieved by 'get_next_AMLC_block') to BL2."""
	offset = 0
	for chunk in dnload_iter(data, AMLC_MAX_TRANSFERT_LENGTH):
		write_AMLC_sub_blocks(dev, offset, chunk)
		offset += len(chunk)

	# Write AMLS with checksum over full block, while transferring part of the first 512 bytes
	checksum = compute_AMLS_checksum(data)
	logger.debug(f"Sending {checksum=} for sequence {seq}")
	amls = (
		pack("<4sBBBBII", bytes("AMLS", "ascii"), seq, 0, 0, 0, checksum, 0)
		+ data[16:512]
	)
	write_AMLC_sub_blocks(dev, amlc_offset, amls)
