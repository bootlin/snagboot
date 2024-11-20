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

"""
Commands for the SDP protocol used by iMX* MPUs, as described in the IMX8MM
reference manual
"""

import logging
logger = logging.getLogger("snagrecover")
from snagrecover import utils
from snagrecover.protocols import hab_constants
from snagrecover.config import recovery_config
from snagrecover.protocols.hid import HIDDevice, HIDError
from usb.core import USBError
import struct


class SDPCommand():

	command_codes = {
	"READ_REGISTER": b"\x01\x01",
	"WRITE_REGISTER": b"\x02\x02",
	"WRITE_FILE": b"\x04\x04",
	"ERROR_STATUS": b"\x05\x05",
	"DCD_WRITE": b"\x0a\x0a",
	"JUMP_ADDRESS": b"\x0b\x0b",
	"SKIP_DCD_HEADER": b"\x0c\x0c"
	}

	format_codes = {
	"FORMAT_8":	 b"\x08",
	"FORMAT_16": b"\x10",
	"FORMAT_32": b"\x20"
	}

	# High Assurance Boot status codes
	hab_codes = {
	"HAB_OPEN": b"\x56\x78\x78\x56",
	"HAB_CLOSED": b"\x12\x34\x34\x12"
	}

	REPORT2_PACKET_SIZE = 1025

	CBW_BLTC_SIGNATURE = 0x43544C42
	CBW_HOST_TO_DEVICE_FLAGS = 0x00
	BLTC_DOWNLOAD_FW = 0x02
	FT_APP = b"\xaa"
	FT_UNUSED =b"\x00"

	def __init__(self, dev):
		self.dev = dev
		self.clear()

	def clear(self):
		if self.is_hid():
			self._hid_report = b"\x01"
		else:
			self._hid_report = b""
		self.cmd = None
		self.addr = 0
		self.format = b"\x00"
		self.data_count = 0
		self.data = 0
		self.file_type = self.FT_UNUSED

	def build_packet(self) -> bytes:
		return self._hid_report + self.cmd + self.addr.to_bytes(4, "big") \
		+ self.format + self.data_count.to_bytes(4, "big") \
		+ self.data.to_bytes(4, "big") + self.file_type

	def check_hab(self):
		hab_status = self.dev.read(64, timeout=5)
		if hab_status[:4] != __class__.hab_codes["HAB_OPEN"]:
			raise ValueError(f"Error: status HAB_CLOSED or unknown: {hab_status} found on address ")
		return None

	def read32(self, addr: int) -> int:
		self.clear()
		self.cmd = __class__.command_codes["READ_REGISTER"]
		self.format = __class__.format_codes["FORMAT_32"]
		self.addr = addr
		self.data_count = 4
		packet = self.build_packet()
		logger.debug(f"Sending SDP packet {packet}")
		self.dev.write(packet)
		self.check_hab()
		value = self.dev.read(64, timeout=5)[:4]
		return int.from_bytes(value, "little")

	def write32(self, addr: int, value: int) -> bool:
		self.clear()
		self.cmd = __class__.command_codes["WRITE_REGISTER"]
		self.format = __class__.format_codes["FORMAT_32"]
		self.addr = addr
		self.data_count = 4
		self.data = value
		packet = self.build_packet()
		logger.debug(f"Sending SDP packet {packet}")
		self.dev.write(packet)
		self.check_hab()
		complete_status = self.dev.read(64, timeout=5)[:4]
		return complete_status == b"\x12\x8A\x8A\x12"

	def write_dcd(self, blob: bytes, addr: int, offset: int, size: int) -> bool:
		if self.is_hid():
			return self.write_blob(blob, addr, offset, size, write_dcd=True)

		# Non HID devices do not have a DCD_WRITE command
		# They do have a "FileType" byte in WRITE_FILE but that does not
		# appear to actually process the DCD immediately (which we need to
		# configure dram to download u-boot)
		# So instead we manually interpret the DCD as individual read / write
		# operations. This is what imx_usb_loader does too.
		(tag, lg, version), hdr_len = self._unpack_from_blob(">BHB", blob, offset)
		if tag != 0xD2:
			raise ValueError("Bad DCD tag %02x" % tag)
		if version != 0x40:
			raise ValueError("Bad DCD version %02x" % version)

		pos = offset + hdr_len
		end = offset + lg
		while pos < end:
			(tag, lg), _ = self._unpack_from_blob(">BH", blob, pos)

			if tag == 0xcc:
				self._invoke_for_each_dcd_element_addr_data(self._process_dcd_write_data, blob, pos)
			elif tag == 0xcf:
				self._invoke_for_each_dcd_element_addr_data(self._process_dcd_check_data, blob, pos)
			elif tag == 0xc0: # nop
				pass
			else:
				raise ValueError("Invalid DCD command tag %02x" % tag)

			pos += lg

	# unpack binaary data defined by struct format from blob at offset return as (unpacked eltts), total_size
	def _unpack_from_blob(self, fmt, blob, offset):
		s = struct.Struct(fmt)
		return s.unpack(blob[offset:offset + s.size]), s.size

	# Invoke fn for each addr, data pair in the DCD element starting at offset pos of blob
	def _invoke_for_each_dcd_element_addr_data(self, fn, blob, pos):
		(tag, lg, param), hdr_len = self._unpack_from_blob(">BHB", blob, pos)
		elt_size = param & 7
		if elt_size != 4:
			raise ValueError("Only 32 bit access currently supported")

		fmt = struct.Struct(">II")
		cur = pos + hdr_len
		last = pos + lg
		while cur < last:
			addr, val = fmt.unpack(blob[cur:cur + fmt.size])
			ret = fn(addr, val, param)
			if not ret:
				raise RuntimeError("Failed addr=%08x val=%08x" % (addr, val))

			cur += fmt.size

	def _process_dcd_write_data(self, addr, value_mask, param):
		logger.debug("dcd write: addr=%08x val=%08x pram=%2x", addr, value_mask, param)
		is_mask = bool(param & (1 << 3))
		is_set = bool(param & (1 << 4))
		if is_mask:
			value = self.read32(addr)
			if is_set:
				value |= value_mask
			else:
				value &= ~value_mask
		else:
			value = value_mask

		return self.write32(addr, value)

	def _process_dcd_check_data(self, addr, mask, param):
		logger.debug("dcd check: addr=%08x mask=%08x param=%2x", addr, mask, param)
		is_mask = bool(param & (1 << 3))
		is_set = bool(param & (1 << 4))

		while True:
			value = self.read32(addr)
			logger.debug("    check: value=%08x", value)
			if (is_mask, is_set) == (False, False):
				if (value & mask) == 0:
					break

			if (is_mask, is_set) == (False, True):
				if (value & mask) == mask:
					break

			if (is_mask, is_set) == (True, False):
				if (value & mask) != mask:
					break

			if (is_mask, is_set) == (True, True):
				if (value & mask) != 0:
					break

		return True

	def write_blob(self, blob: bytes, addr: int, offset: int, size: int, write_dcd: bool = False) -> bool:
		self.clear()
		self.addr = addr
		self.data_count = size
		self.cmd = __class__.command_codes["WRITE_FILE"]

		# SoCs using HID have separate commands for DCD and DATA
		if self.is_hid() and write_dcd:
			self.cmd = __class__.command_codes["DCD_WRITE"]

		if not self.is_hid():
			self.file_type = self.FT_APP

		packet1 = self.build_packet()
		self.dev.write(packet1)

		if self.is_hid():
			for chunk in utils.dnload_iter(blob[offset:offset + size], __class__.REPORT2_PACKET_SIZE - 1):
				packet2 = b"\x02" + chunk
				if len(packet2) < __class__.REPORT2_PACKET_SIZE:
					packet2 = packet2 + b"\x00" * (__class__.REPORT2_PACKET_SIZE - (len(packet2) % __class__.REPORT2_PACKET_SIZE))
				self.dev.write(packet2)

			self.check_hab()
			complete_status = self.dev.read(64, timeout=5)[:4]
		else:
			self.check_hab()
			self.dev.write(blob[offset:offset + size])

			self.clear()
			self.cmd = __class__.command_codes["ERROR_STATUS"]
			packet = self.build_packet()
			self.dev.write(packet)

			complete_status = self.dev.read(64, timeout=5)[:4]

		logger.info(f"write_blob finished with complete status {complete_status}")
		if write_dcd:
			return complete_status == b"\x12\x8A\x8A\x12"
		else:
			return complete_status == b"\x88\x88\x88\x88"

	def jump(self, addr: int):
		if not self.is_hid():
			return

		self.clear()
		self.cmd = __class__.command_codes["JUMP_ADDRESS"]
		self.addr = addr
		packet = self.build_packet()
		self.dev.write(packet)
		"""
		Looks like the following checks will fail sometimes,
		even if the jump was successful. We still perform them
		though, in case the SoC actually expects them
		"""
		try:
			self.check_hab()
			status = self.dev.read(64, timeout = 5)
			if status != b"":
				decoded_err = hab_constants.status_codes[int(status[0])] \
					+ " | " + hab_constants.reason_codes[int(status[1])]\
					+ " | " + hab_constants.context_codes[int(status[2])]\
					+ " | " + hab_constants.engine_tags[int(status[3])]
				logger.warning(f"error status {decoded_err} returned after jump to 0x{addr:x}")
		except (USBError, HIDError, OSError) as err:
			logger.warning(f"Caught (USB/HID)Error {str(err)}")
		return None

	def skip_dcd_header(self):
		logger.info("Sending SKIP_DCD_HEADER command")
		self.clear()
		self.cmd = __class__.command_codes["SKIP_DCD_HEADER"]
		packet1 = self.build_packet()
		self.dev.write(packet1)
		self.check_hab()
		ack = self.dev.read(64, timeout=5)[:4]
		return ack == b"\x09\xd0\x0d\x90"

	def sdps_write(self, blob: bytes, size: int) -> bool:
		"""
		Command used to write the first stage firmware for boards using the SDPS
		protocol. It has not yet been tested on all supported platforms and may
		require some tweaks.
		"""
		logger.info(f"SDPS write with parameters size:0x{size:x} offset:0x00")
		soc_model = recovery_config["soc_model"]
		if soc_model not in ["imx8qm", "imx8qxp", "imx815", "imx865", "imx93"]:
			# only some mpu models require a preliminary command before the report 2
			# transfer
			packet1_arr = bytearray(b"\x01") # report 1
			packet1_arr += __class__.CBW_BLTC_SIGNATURE.to_bytes(4, "little")
			packet1_arr += b"\x01\x00\x00\x00" # tag
			packet1_arr += size.to_bytes(4, "little") # XferLength
			packet1_arr += __class__.CBW_HOST_TO_DEVICE_FLAGS.to_bytes(1, "little")
			packet1_arr += b"\x00\x00" # reserved
			packet1_arr += __class__.BLTC_DOWNLOAD_FW.to_bytes(1, "little") # Command
			packet1_arr += size.to_bytes(4, "big") # Length
			packet1_arr += b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" # reserved
			packet1 = bytes(packet1_arr)
			self.dev.write(packet1)
		if soc_model in ["imx815", "imx865", "imx93"]:
			transfer_size = 1020
		else:
			transfer_size = 1024

		for chunk in utils.dnload_iter(blob[0:size], transfer_size):
			packet2 = b"\x02" + chunk
			self.dev.write(packet2)
		"""
		self.check_hab()
		complete_status = self.dev.read(64, timeout=5)[:4]
		logger.info(f"write_blob finished with complete status {complete_status}")
		return complete_status == b"\x88\x88\x88\x88"
		"""
		return True

	def is_hid(self):
		return self.dev.__class__ == HIDDevice

	def close(self):
		if self.is_hid():
			return self.dev.close()
		return None
