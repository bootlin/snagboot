# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
#
# Written by Romain Gantois <romain.gantois@bootlin.com> in 2023.
#
# Based on sunxi-tools (https://github.com/linux-sunxi/sunxi-tools/fel_lib.c)
# Copyright (C) 2012 Henrik Nordstrom <henrik@henriknordstrom.net>
# Copyright (C) 2015 Siarhei Siamashka <siarhei.siamashka@gmail.com>
# Copyright (C) 2016 Bernhard Nortmann <bernhard.nortmann@web.de>
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

import usb
from snagrecover import utils

class FEL():
	MAX_MSG_LEN = 65536
	"""
	For some of these requests, I haven't
	been able to find any detailed
	documentation.
	"""
	standard_request_codes = {
	"FEL_VERIFY_DEVICE": 0x1,
	"FEL_SWITCH_ROLE": 0x2,
	"FEL_IS_READY": 0x3,
	"FEL_GET_CMD_SET_VER": 0x4,
	"FEL_DISCONNECT": 0x10,
	"FEL_DOWNLOAD": 0x101,
	"FEL_RUN": 0x102,
	"FEL_UPLOAD": 0x103,
	}

	def __init__(self, dev: usb.core.Device, timeout: int):
		self.dev = dev
		cfg = dev.get_active_configuration()
		# select the first interface we find with a bulk in ep and a bulk out ep
		eps_found = False
		for intf in cfg.interfaces():
			ep_in, ep_out = None, None
			for ep in intf.endpoints():
				is_bulk = (ep.bmAttributes & usb.ENDPOINT_TYPE_MASK) == usb.ENDPOINT_TYPE_BULK
				is_in = (ep.bmAttributes & usb.ENDPOINT_TYPE_MASK) == usb.ENDPOINT_TYPE_BULK
				if not is_bulk:
					continue
				is_in = (ep.bEndpointAddress & usb.ENDPOINT_DIR_MASK) == usb.ENDPOINT_IN
				if is_in:
					ep_in = ep.bEndpointAddress
				else:
					ep_out = ep.bEndpointAddress
			if not ((ep_in is None) or (ep_out is None)):
				eps_found = True
				break
		if not eps_found:
			raise Exception("No BULK IN/OUT endpoint pair found in device")
		self.ep_in = ep_in
		self.ep_out = ep_out
		self.timeout = timeout

	def aw_exchange(self, length: int, out: bool, packet: bytes = b"") -> bytes:
		# USB request
		if out:
			cmd = b"\x12"
		else:
			cmd = b"\x11"
		"""
		magic[4] + reserved[4]
		len
		reserved[3]
		cmd_len
		cmd
		reserved
		len2
		reserved[10]
		"""
		packet0 = b"AWUC\x00\x00\x00\x00"\
				+ length.to_bytes(4, "little")\
				+ b"\x00\x00\x00"\
				+ b"\x0c"\
				+ cmd\
				+ b"\x00"\
				+ length.to_bytes(4, "little")\
				+ (10 * b"\x00")
		self.dev.write(self.ep_out, packet0, timeout=self.timeout)
		# main action
		if out:
			ret = (self.dev.write(self.ep_out, packet, timeout=self.timeout)).to_bytes(4, "little")
		else:
			ret = self.dev.read(self.ep_in, length, timeout=self.timeout)
		# USB response
		usb_ret = self.dev.read(self.ep_in, 13, timeout = self.timeout)
		# check magic
		if bytes(usb_ret[:4]) != b"AWUS":
			raise Exception("Malformed packet received")
		csw_status = usb_ret[12]
		if csw_status != 0:
			raise ValueError(f"Error status {csw_status} returned in USB exchange")
		return ret

	def request(self, request: str, response_len: int) -> bytes:
		# send request
		request = (FEL.standard_request_codes[request]).to_bytes(2, "little") \
				+ (14 * b"\x00") # tag + reserved
		self.aw_exchange(len(request), out=True, packet=request)
		# get response
		response = self.aw_exchange(length=response_len, out=False)
		# get state
		ret = self.aw_exchange(length=8, out=False)
		# check mark and state
		if bytes(ret[:2]) != b"\xff\xff":
			raise Exception("Malformed packet received")
		state = ret[4]
		if state != 0:
			raise Exception(f"Device returned error state {state}")
		return response

	def message(self, request: str, addr: int, length: int, data: bytes = b"") -> bytes:
		if length > FEL.MAX_MSG_LEN:
			raise Exception("Data is too long for FEL message")
		if request == "FEL_DOWNLOAD" and len(data) != length:
			raise Exception("Data does not match length parameter")
		# send message
		message = (FEL.standard_request_codes[request]).to_bytes(2, "little") \
				+ b"\x00\x00"\
				+ addr.to_bytes(4, "little")\
				+ length.to_bytes(4, "little")\
				+ b"\x00\x00\x00\x00"
		self.aw_exchange(len(message), out=True, packet=message)
		# get/send data
		if request == "FEL_UPLOAD":
			data = self.aw_exchange(length=length, out=False)
		elif request == "FEL_DOWNLOAD":
			data = self.aw_exchange(length=length, out=True, packet=data)
		else:
			# FEL_RUN
			data = None
		# get state
		ret = self.aw_exchange(length=8, out=False)
		# check mark and state
		if bytes(ret[:2]) != b"\xff\xff":
			raise Exception("Malformed packet received")
		state = ret[4]
		if state != 0:
			raise Exception(f"Device returned error state {state}")
		return data

	def verify_device(self):
		response = self.request("FEL_VERIFY_DEVICE", 32)
		# check magic
		if bytes(response[:8]) != b"AWUSBFEX":
			raise Exception("Malformed FEL_VERIFY_DEVICE response received")
		ret = {
			"board": int.from_bytes(response[8:12], "little"),
			"fw": int.from_bytes(response[12:16], "little"),
			"mode": int.from_bytes(response[16:18], "little"),
			"data_flag": response[18],
			"data_length": response[19],
			"data_start_address": int.from_bytes(response[20:24], "little")
		}
		return ret

	def read32(self, addr: int) -> int:
		data = self.message("FEL_UPLOAD", addr, 4)
		return int.from_bytes(data, "little")

	def write32(self, addr: int, value: int) -> bool:
		packet = value.to_bytes(4, "little")
		nbytes = self.message("FEL_DOWNLOAD", addr, 4, packet)
		return int.from_bytes(nbytes, "little") == 4

	def write_blob(self, blob: bytes, addr: int, offset: int, size: int) -> bool:
		# chop up download in muliple chunks if necessary
		ret = True
		chunk_addr = addr
		for chunk in utils.dnload_iter(blob[offset:offset + size], FEL.MAX_MSG_LEN):
			N = len(chunk)
			nbytes = self.message("FEL_DOWNLOAD", chunk_addr, N, chunk)
			ret &= int.from_bytes(nbytes, "little") == N
			chunk_addr += N
		return ret

	def jump(self, addr: int) -> bool:
		self.message("FEL_RUN", addr, 0)
		return True

