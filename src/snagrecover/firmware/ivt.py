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

IVT_HEADER_1 = b"\xd1\x00\x20\x40"
IVT_HEADER_2 = b"\xd1\x00\x20\x41"

class IVT():
	def __init__(self):
		self.header = None
		self.entry = None
		self.reserved1 = None
		self.dcd = None
		self.boot_data = {
			"start": None,
			"length": None,
			"plugin_flag": None,
		}
		self.addr = None
		self.csf = None
		self.reserved2 = None
		self.offset = None # offset in boot image, in bytes

	def log(self):
		for key,value in self.__dict__.items():
			if key == "boot_data":
				for bkey, bvalue in value.items():
					logger.debug(f"Boot data: {bkey}: 0x{bvalue:x}")
			else:
				logger.debug(f"IVT: {key}: 0x{value:x}")
		return None

	def from_blob(self, blob: bytes) -> bool:
		offset = 0
		while offset < len(blob):
			word = blob[offset:offset+4]
			if word not in [IVT_HEADER_1, IVT_HEADER_2]:
				offset += 4
				continue
			self.offset = offset
			self.header =	 int.from_bytes(word, "little")
			self.entry =	 int.from_bytes(blob[offset + 4:offset + 8], "little")
			self.reserved1 = int.from_bytes(blob[offset + 8:offset + 12], "little")
			self.dcd =		 int.from_bytes(blob[offset + 12:offset + 16], "little")
			boot_datap =	 int.from_bytes(blob[offset + 16:offset + 20], "little")
			self.addr =		 int.from_bytes(blob[offset + 20:offset + 24], "little")
			self.csf =		 int.from_bytes(blob[offset + 24:offset + 28], "little")
			self.reserved2 = int.from_bytes(blob[offset + 28:offset + 32], "little")
			# get boot data
			bootd_offset = self.offset + boot_datap - self.addr
			self.boot_data["start"] = int.from_bytes(blob[bootd_offset:bootd_offset + 4], "little")
			self.boot_data["length"] = int.from_bytes(blob[bootd_offset + 4:bootd_offset + 8], "little")
			self.boot_data["plugin_flag"] = int.from_bytes(blob[bootd_offset + 8:bootd_offset + 12], "little")
			# ignore HDMI firmware for MX8MQ*
			if word == IVT_HEADER_2 and (self.boot_data["plugin_flag"] & 0xfffffffe > 0):
				continue
			self.log()
			return True
		return False

