# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
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
from enum import IntEnum
from typing import Tuple

from ..usb import UsbDevice, UsbError

CMD_SIGNATURE = 0x55434D44
RSP_SIGNATURE = 0x55525350


class AmbaUsbError(Exception):
	pass


class AmbaInquiryType(IntEnum):
	CHIP = 0x00000001
	ADDR = 0x00000002
	REG = 0x00000003


class AmbaCommand(IntEnum):
	RDY_TO_RCV = 0
	RCV_DATA = 1
	RDY_TO_SND = 2
	SND_DATA = 3
	INQUIRY_STATUS = 4


class AmbaResponse(IntEnum):
	SUCCESS = 0
	FAILED = 1
	IN_BLD = 2


@dataclass
class AmbaDeviceInfo:
	chip_type: int
	dram_start: int


class AmbaProtocol:
	def __init__(self, device: UsbDevice):
		self.device = device
		self._cmd_buf = bytearray(32)
		self._rsp_buf = bytearray(16)

	def _pack_command(self, cmd: int, *params) -> bytes:
		struct.pack_into(
			"<IIIIIIII",
			self._cmd_buf,
			0,
			CMD_SIGNATURE,
			cmd,
			*(params + (0,) * (6 - len(params))),
		)
		return self._cmd_buf

	def _unpack_response(self) -> Tuple[int, int, int, int]:
		return struct.unpack_from("<IIII", self._rsp_buf)

	def send_command(self, cmd: int, *params) -> Tuple[int, int, int]:
		try:
			cmd_buf = self._pack_command(cmd, *params)
			self.device.write(cmd_buf)

			self.device.read(self._rsp_buf)
			sig, rsp, p0, p1 = self._unpack_response()

			if sig != RSP_SIGNATURE:
				raise AmbaUsbError("Invalid response signature")

			return rsp, p0, p1

		except UsbError as e:
			raise AmbaUsbError("USB communication error") from e

	def get_device_info(self) -> AmbaDeviceInfo:
		rsp, chip, _ = self.send_command(
			AmbaCommand.INQUIRY_STATUS, AmbaInquiryType.CHIP
		)
		if rsp != AmbaResponse.SUCCESS:
			raise AmbaUsbError("Failed to get chip type")

		rsp, dram_start, _ = self.send_command(
			AmbaCommand.INQUIRY_STATUS, AmbaInquiryType.ADDR
		)
		if rsp != AmbaResponse.SUCCESS:
			raise AmbaUsbError("Failed to get DRAM start address")

		return AmbaDeviceInfo(chip, dram_start)

	def send_file(self, addr: int, data: bytes) -> None:
		rsp, _, _ = self.send_command(AmbaCommand.RDY_TO_RCV, addr)
		if rsp != AmbaResponse.SUCCESS:
			raise AmbaUsbError("Device not ready to receive")

		rsp, _, _ = self.send_command(AmbaCommand.RCV_DATA)
		if rsp != AmbaResponse.SUCCESS:
			raise AmbaUsbError("Failed to initiate data transfer")

		try:
			self.device.write(data)
		except UsbError as e:
			raise AmbaUsbError("Failed to send data") from e

		rsp, _, _ = self.send_command(
			AmbaCommand.RDY_TO_RCV,
			0x80000000,
			addr,
		)
		if rsp != AmbaResponse.SUCCESS:
			raise AmbaUsbError("Data transfer failed")
