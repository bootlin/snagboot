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
CONTAINER_HDR_ALIGNMENT_V2 = 0x4000
CONTAINER_TAG = 0x87
V2X_CONTAINER_TAG = 0x82
V2X_BOOTIMG_FLAG = 0x0B

ROM_CONTAINER_STRUCT_SIZE = 16
ROM_BOOTIMG_STRUCT_SIZE = 128

# offsets of the fields we read in the container header struct
CONTAINER_VERSION_OFFSET = 0
CONTAINER_TAG_OFFSET = 3
CONTAINER_NUM_IMAGES_OFFSET = 11

# offsets and type mask of the fields we read in a boot image struct
BOOTIMG_IMAGE_SIZE_OFFSET = 4
BOOTIMG_FLAGS_OFFSET = 24
BOOTIMG_FLAGS_TYPE_MASK = 0x0F


def get_container_size(boot_blob: bytes) -> int:
	"""
	This function is used to compute the size of the first stage firmware
	container for boards socs using the SDPS protocol.
	"""
	soc_model = recovery_config["soc_model"]
	if soc_model in ["imx815", "imx865", "imx91", "imx93"]:
		return len(boot_blob)

	if (
		boot_blob[CONTAINER_TAG_OFFSET] == CONTAINER_TAG
		and boot_blob[CONTAINER_VERSION_OFFSET] >= 2
	):
		# version >= 2 containers (e.g. i.MX95) use a larger alignment and a dedicated V2X tag
		align = CONTAINER_HDR_ALIGNMENT_V2
		cont_index = 1
		if boot_blob[align + CONTAINER_TAG_OFFSET] == V2X_CONTAINER_TAG:
			# skip V2X container
			cont_index = 2
	else:
		align = CONTAINER_HDR_ALIGNMENT
		if boot_blob[align + CONTAINER_TAG_OFFSET] != CONTAINER_TAG:
			return len(boot_blob)
		cont_index = 1
		romimg_offset = align + ROM_BOOTIMG_STRUCT_SIZE
		flags_pos = romimg_offset + BOOTIMG_FLAGS_OFFSET
		romimg_flags = int.from_bytes(boot_blob[flags_pos : flags_pos + 4], "little")
		if romimg_flags & BOOTIMG_FLAGS_TYPE_MASK == V2X_BOOTIMG_FLAG:
			# skip V2X container
			cont_index = 2
			if boot_blob[cont_index * align + CONTAINER_TAG_OFFSET] != CONTAINER_TAG:
				return len(boot_blob)

	container_offset = cont_index * align
	if boot_blob[container_offset + CONTAINER_TAG_OFFSET] != CONTAINER_TAG:
		return len(boot_blob)
	num_images = int(boot_blob[container_offset + CONTAINER_NUM_IMAGES_OFFSET])
	romimg_offset = (
		container_offset
		+ ROM_CONTAINER_STRUCT_SIZE
		+ (num_images - 1) * ROM_BOOTIMG_STRUCT_SIZE
	)
	# a boot image struct starts with its image offset and size fields
	img_offset = int.from_bytes(boot_blob[romimg_offset : romimg_offset + 4], "little")
	size_pos = romimg_offset + BOOTIMG_IMAGE_SIZE_OFFSET
	img_size = int.from_bytes(boot_blob[size_pos : size_pos + 4], "little")
	container_size = img_offset + img_size + container_offset
	# round container size up
	container_size = (
		ceil(container_size / (1.0 * CONTAINER_HDR_ALIGNMENT)) * CONTAINER_HDR_ALIGNMENT
	)
	if container_size >= len(boot_blob):
		raise ValueError(
			"Error: unsupported image format or image does not contain u-boot proper"
		)
	return container_size
