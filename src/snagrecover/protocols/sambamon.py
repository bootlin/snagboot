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

import serial
import logging
logger = logging.getLogger("snagrecover")

class SambaMon():
	def __init__(self, port: serial.serialposix.Serial):
		self.port = port
		# set sam-ba monitor to binary mode
		logger.debug("Sending sambamon command N#")
		port.write(b"N#")
		port.read_until(b"\r")
		return None

	def get_version(self) -> str:
		# get SAM-BA monitor version
		logger.debug("Sending sambamon command V#")
		self.port.write(b"V#")
		ret = self.port.read_until(b"\r")
		return ret.decode("ascii")

	def read32(self, addr: int) -> int:
		self.port.write(bytes(f"w{addr:x},#", "ascii"))
		ret = self.port.read(4)
		value = int.from_bytes(ret, "little")
		return value

	def write32(self, addr: int, value: int) -> bool:
		nbytes = self.port.write(bytes(f"W{addr:x},{value:x}#", "ascii"))
		return nbytes == 4

	def write_blob(self, blob: bytes, addr: int, offset: int, size: int) -> bool:
		# write binary blob to address
		PAYLOAD_SIZE = 0x4000 # got this value from packet dumps
		N = size // PAYLOAD_SIZE
		R = size % PAYLOAD_SIZE
		nbytes = 0
		for i in range(N):
			logger.debug(f"Sending sambamon command S{addr:x},{PAYLOAD_SIZE:x}#")
			self.port.write(bytes(f"S{addr:x},{PAYLOAD_SIZE:x}#", "ascii"))
			nbytes += self.port.write(blob[offset + i * PAYLOAD_SIZE: offset + (i + 1) * PAYLOAD_SIZE])
			addr += PAYLOAD_SIZE
		if R > 0:
			logger.debug(f"Sending sambamon command S{addr:x},{R:x}#")
			self.port.write(bytes(f"S{addr:x},{R:x}#", "ascii"))
			nbytes += self.port.write(blob[offset + PAYLOAD_SIZE * N: offset\
				+ PAYLOAD_SIZE * N + R])
		return nbytes == size

	def jump(self, addr: int) -> bool:
		# tell SAM-BA monitor to execute code at address
		packet = bytes(f"G{addr:x}#", "ascii")
		nbytes = self.port.write(packet)
		return nbytes == len(packet)

