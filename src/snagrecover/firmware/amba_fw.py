# This file is part of Snagboot
# Copyright (C) 2025 Petr Hodina
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

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .firmware import Firmware, FirmwareError

FIRM_OFFSET_VERSION = 0x3C
FIRM_OFFSET_MEMFW_RESULT = 0x40
FIRM_OFFSET_MEMFW_CMD = 0x50
FIRM_OFFSET_MEMFW_PROG = 0x60

BOARD_INFO_MAGIC = 0x12345678
BOARD_INFO_ADDR = 0x100000
PTB_PTR = 0x200000

FW_INFO_MAGIC = 0x87654321
FW_INFO_ADDR = 0x110000


@dataclass
class AmbaFirmwareInfo:
	version: int
	memfw_result_addr: int
	memfw_cmd_addr: int
	memfw_prog_addr: int


class AmbaFirmware(Firmware):
	def __init__(
		self,
		bootloader_path: Optional[Path] = None,
		dram_script_path: Optional[Path] = None,
	):
		super().__init__()
		self.bootloader_path = bootloader_path
		self.dram_script_path = dram_script_path
		self._bootloader_data: Optional[bytes] = None
		self._dram_script_data: Optional[str] = None

	def load(self) -> None:
		if self.bootloader_path:
			try:
				with open(self.bootloader_path, "rb") as f:
					self._bootloader_data = f.read()
			except OSError as e:
				raise FirmwareError("Failed to load bootloader") from e

		if self.dram_script_path:
			try:
				with open(self.dram_script_path, "r") as f:
					self._dram_script_data = f.read()
			except OSError as e:
				raise FirmwareError("Failed to load DRAM script") from e

	@property
	def bootloader(self) -> bytes:
		if not self._bootloader_data:
			raise FirmwareError("Bootloader not loaded")
		return self._bootloader_data

	@property
	def dram_script(self) -> str:
		if not self._dram_script_data:
			raise FirmwareError("DRAM script not loaded")
		return self._dram_script_data

	@staticmethod
	def get_firmware_info(firmware_path: Path) -> AmbaFirmwareInfo:
		try:
			with open(firmware_path, "rb") as f:
				f.seek(FIRM_OFFSET_VERSION)
				version = struct.unpack("<I", f.read(4))[0]

				f.seek(FIRM_OFFSET_MEMFW_RESULT)
				result_addr = struct.unpack("<I", f.read(4))[0]

				f.seek(FIRM_OFFSET_MEMFW_CMD)
				cmd_addr = struct.unpack("<I", f.read(4))[0]

				f.seek(FIRM_OFFSET_MEMFW_PROG)
				prog_addr = struct.unpack("<I", f.read(4))[0]

			return AmbaFirmwareInfo(
				version=version,
				memfw_result_addr=result_addr,
				memfw_cmd_addr=cmd_addr,
				memfw_prog_addr=prog_addr,
			)

		except (OSError, struct.error) as e:
			raise FirmwareError("Failed to extract firmware info") from e

	@staticmethod
	def pack_board_info() -> bytes:
		return struct.pack(
			"<IIII",
			BOARD_INFO_MAGIC,
			0x6F547541,  # 'AuTo' in little endian
			PTB_PTR,
			0,
		)  # reserved

	@staticmethod
	def pack_firmware_info(fw_info: AmbaFirmwareInfo) -> bytes:
		return struct.pack(
			"<IIII",
			FW_INFO_MAGIC,
			fw_info.memfw_cmd_addr,
			fw_info.memfw_result_addr,
			0,
		)
