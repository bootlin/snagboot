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

STM32IMG_HEADER_MAGIC = b"\x53\x54\x4d\x32"
HEADER_DEFAULT_OPTION = 0x01 # bit 0: no signature
HEADER_TYPE_UBOOT = 0x00
STM32_HEADER_SIZE = 256

stm32_v1_header = {
"magic_number": STM32IMG_HEADER_MAGIC,
"image_signature": 0x0,
"image_checksum": None,
"header_version": 0x10000,
"image_length": None,
"image_entry_point": 0x0,
"reserved1": 0x0,
"load_address": 0x0,
"reserved2": 0x0,
"version_number": 0x0,
"option_flags": HEADER_DEFAULT_OPTION,
"ecdsa_algorithm": 0x0,
"ecdsa_public_key": 0x0,
"padding": 0x0,
"binary_type": HEADER_TYPE_UBOOT,
}

def build_image() -> bytearray:
	FSBL_PARTID = 0x01
	SSBL_PARTID = 0x03
	fsbl_partid = str.encode(f"0x{FSBL_PARTID:02x}", "ascii")
	ssbl_partid = str.encode(f"0x{SSBL_PARTID:02x}", "ascii")

	flashlayout =\
	b"-\t"+fsbl_partid+b"\tfsbl1-boot\tBinary\tnone\t0x0\n"\
	+b"-\t"+ssbl_partid+b"\tssbl-boot\tBinary\tnone\t0x0\n"
	stm32_v1_header["image_checksum"] = sum(flashlayout)
	stm32_v1_header["image_length"] = len(flashlayout)

	image = bytearray(stm32_v1_header["magic_number"])
	for field,value in stm32_v1_header.items():
		if field == "magic_number":
			continue
		elif field in ["image_signature","ecdsa_public_key"]:
			image += bytearray(b"\x00") * 64
		elif field == "padding":
			image += bytearray(b"\x00") * 83
		elif field == "binary_type":
			image += value.to_bytes(1, "little")
		else:
			image += value.to_bytes(4, "little")
	image += flashlayout
	logger.debug("flashlayout:" + repr(image))
	return image

