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

from math import ceil
from snagrecover.config import recovery_config

CONTAINER_HDR_ALIGNMENT = 0x400
CONTAINER_TAG = 0x87
V2X_BOOTIMG_FLAG = 0x0b

ROM_CONTAINER_STRUCT_SIZE = 16
ROM_BOOTIMG_STRUCT_SIZE = 34

def get_container_size(boot_blob: bytes) -> int:
	"""
	This function is used to compute the size of the first stage firmware
	container for boards socs using the SDPS protocol. It has not yet been tested.
	"""
	soc_model = recovery_config["soc_model"]
	if soc_model == "imx815":
		return len(boot_blob)
	rom_container_tag = boot_blob[CONTAINER_HDR_ALIGNMENT + 3]
	if rom_container_tag != b"\x87":
		return len(boot_blob)

	cont_index = 1
	romimg_offset = CONTAINER_HDR_ALIGNMENT + ROM_BOOTIMG_STRUCT_SIZE
	romimg_flags = int.from_bytes(boot_blob[romimg_offset + 24:romimg_offset + 28], "little")
	if romimg_flags & 0x0F == V2X_BOOTIMG_FLAG:
		# skip V2X container
		cont_index = 2
		rom_container_tag = boot_blob[2 * CONTAINER_HDR_ALIGNMENT + 3]
		if rom_container_tag != b"\x87":
			return len(boot_blob)
	container_offset = cont_index * CONTAINER_HDR_ALIGNMENT
	num_images = int(boot_blob[container_offset + 11])
	romimg_offset = container_offset + ROM_CONTAINER_STRUCT_SIZE + (num_images - 1) * ROM_BOOTIMG_STRUCT_SIZE
	romimg_offset = int.from_bytes(boot_blob[romimg_offset: romimg_offset], "little")
	romimg_size = int.from_bytes(boot_blob[romimg_offset + 4: romimg_offset + 8], "little")
	container_size = romimg_offset + romimg_size + cont_index * CONTAINER_HDR_ALIGNMENT
	# round container size up
	container_size = ceil(container_size / (1.0 * CONTAINER_HDR_ALIGNMENT)) * CONTAINER_HDR_ALIGNMENT
	if container_size >= len(boot_blob):
		raise ValueError("Error: unsupported image format or image does not contain u-boot proper")
	return container_size

