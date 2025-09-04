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

import re
import time
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import List, Optional

from ..firmware.amba_fw import AmbaFirmware
from ..protocols.amba import AmbaCommand, AmbaProtocol
from ..usb import UsbDevice


class AdsCommandType(IntEnum):
	INVALID = 0
	WRITE = 1
	READ = 2
	POLL = 3
	USLEEP = 4
	SLEEP = 5


@dataclass
class AdsCommand:
	type: AdsCommandType
	addr: int = 0
	data: int = 0
	mask: int = 0


class AdsParser:
	def parse(self, script: str) -> List[AdsCommand]:
		commands = []

		for line in script.splitlines():
			line = line.strip()

			if not line or line.startswith("#"):
				continue

			if cmd := self._parse_line(line):
				commands.append(cmd)

		return commands

	def _parse_line(self, line: str) -> Optional[AdsCommand]:
		# Write command: w addr data [mask]
		if m := re.match(
			r"w\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)(?:\s+0x([0-9a-f]+))?", line, re.I
		):
			addr = int(m.group(1), 16)
			data = int(m.group(2), 16)
			mask = int(m.group(3), 16) if m.group(3) else 0xFFFFFFFF
			return AdsCommand(AdsCommandType.WRITE, addr, data, mask)

		# Read command: r addr
		if m := re.match(r"r\s+0x([0-9a-f]+)", line, re.I):
			addr = int(m.group(1), 16)
			return AdsCommand(AdsCommandType.READ, addr)

		# Poll command: p addr data mask
		if m := re.match(
			r"p\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)", line, re.I
		):
			addr = int(m.group(1), 16)
			data = int(m.group(2), 16)
			mask = int(m.group(3), 16)
			return AdsCommand(AdsCommandType.POLL, addr, data, mask)

		# Sleep commands: sleep/usleep time
		if m := re.match(r"(sleep|usleep)\s+(\d+)", line):
			cmd_type = (
				AdsCommandType.SLEEP if m.group(1) == "sleep" else AdsCommandType.USLEEP
			)
			time_val = int(m.group(2))
			return AdsCommand(cmd_type, data=time_val)

		return None


class AmbarellaRecovery:
	def __init__(self, device: UsbDevice):
		self.device = device
		self.protocol = AmbaProtocol(device)
		self.firmware = AmbaFirmware()
		self._ads_parser = AdsParser()

	def _execute_ads_commands(self, commands: List[AdsCommand]) -> None:
		for cmd in commands:
			if cmd.type == AdsCommandType.WRITE:
				self.protocol.send_command(AmbaCommand.RDY_TO_RCV, cmd.addr)
				self.protocol.send_command(AmbaCommand.RCV_DATA, cmd.data)

			elif cmd.type == AdsCommandType.POLL:
				timeout = time.time() + 5.0  # 5 second timeout
				while time.time() < timeout:
					rsp, val, _ = self.protocol.send_command(
						AmbaCommand.INQUIRY_STATUS, cmd.addr
					)
					if (val & cmd.mask) == (cmd.data & cmd.mask):
						break
					time.sleep(0.001)

			elif cmd.type in (AdsCommandType.SLEEP, AdsCommandType.USLEEP):
				sleep_time = (
					cmd.data / 1_000_000
					if cmd.type == AdsCommandType.USLEEP
					else cmd.data
				)
				time.sleep(sleep_time)

	def initialize_dram(self, dram_script: Path) -> None:
		self.firmware.dram_script_path = dram_script
		self.firmware.load()

		commands = self._ads_parser.parse(self.firmware.dram_script)
		self._execute_ads_commands(commands)

	def load_bootloader(self, bootloader: Path) -> None:
		self.firmware.bootloader_path = bootloader
		self.firmware.load()

		self.protocol.send_file(0x0, self.firmware.bootloader)

		board_info = AmbaFirmware.pack_board_info()
		self.protocol.send_file(AmbaFirmware.BOARD_INFO_ADDR, board_info)

	def flash_firmware(self, firmware: Path) -> None:
		fw_info = AmbaFirmware.get_firmware_info(firmware)

		fw_info_data = AmbaFirmware.pack_firmware_info(fw_info)
		self.protocol.send_file(AmbaFirmware.FW_INFO_ADDR, fw_info_data)

		board_info = AmbaFirmware.pack_board_info()
		self.protocol.send_file(AmbaFirmware.BOARD_INFO_ADDR, board_info)

		with open(firmware, "rb") as f:
			fw_data = f.read()
		self.protocol.send_file(fw_info.memfw_prog_addr, fw_data)
