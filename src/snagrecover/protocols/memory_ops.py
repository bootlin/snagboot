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

class MemoryOps():
	"""
	This is an interface for common I/O operations on device memory
	"""
	def __init__(self, backend):
		self.backend = backend

	def read32(self, addr: int) -> int:
		logger.debug(f"[MemoryOps] read32 0x{addr:x} ...")
		value = self.backend.read32(addr)
		logger.debug(f"[MemoryOps] read32 0x{addr:x} 0x{value:x}")
		return value

	def write32(self, addr: int, value: int) -> bool:
		logger.debug(f"[MemoryOps] write32 0x{addr:x} 0x{value:x}")
		ret = self.backend.write32(addr, value)
		return ret

	def write_blob(self, blob: bytes, addr: int, offset: int, size: int) -> bool:
		if len(blob) > 0:
			logger.debug("[MemoryOps] write_blob "\
				+f"0x{blob[offset]:x}...0x{blob[offset + size - 1]:x} "\
				+f"addr 0x{addr:x} offset 0x{offset:x} size 0x{size:x}")
		ret = self.backend.write_blob(blob, addr, offset, size)
		return ret

	def jump(self, addr: int) -> bool:
		logger.debug(f"[MemoryOps] jump to 0x{addr:x} ...")
		ret = self.backend.jump(addr)
		return ret

