# Copyright 2025 Collabora Ltd.
#
# SPDX-License-Identifier: GPL-2.0+
#
# Author: Arnaud Patard <arnaud.patard@collabora.com>


from crccheck.crc import Crc16Ibm3740
import logging
import usb

from snagrecover import utils

logger = logging.getLogger("snagrecover")

class RochipBootRomError(Exception):
	pass

class RochipBootRom():
	def __init__(self, dev: usb.core.Device):
		self.dev = dev
		cfg = dev.get_active_configuration()

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
			raise RochipBootRomError("No BULK IN/OUT endpoint pair found in device")
		self.ep_in = ep_in
		self.ep_out = ep_out

	def __write_chunk(self, code: int, chunk: bytes) -> bool:
		logger.debug(f"Sending {len(chunk)} bytes")
		return self.dev.ctrl_transfer(usb.TYPE_VENDOR, 0x0c, 0, code, chunk, timeout=5000)

	def write_blob(self, blob: bytes, code: int) -> bool:
		if code != 0x471 and code != 0x472:
			raise RochipBootRomError("Invalid code value. Can only be 0x471 or 0x472")
		crc = Crc16Ibm3740()
		total_written = 0
		crc_sent = False
		for chunk in utils.dnload_iter(blob, 4096):
			chunk_len = len(chunk)
			if chunk_len == 4096:
				crc.process(chunk)
			elif chunk_len == 4095:
				chunk.append(0x00)
				crc.process(chunk)
			else:
				crc.process(chunk)
				crcbytes = crc.final()
				chunk = bytearray(chunk)
				chunk.append(crcbytes >> 8)
				chunk.append(crcbytes & 0xff)
				crc_sent = True
			written = self.__write_chunk(code, chunk)
			ret = written == len(chunk)
			if ret is False:
				return ret
			total_written += written
			if chunk_len+2 == 4096:
				chunk = [0x00]
				written = self.__write_chunk(code, chunk)
				ret = written == len(chunk)
				if ret is False:
					return ret
		if crc_sent is False:
			chunk = bytearray()
			crcbytes = crc.final()
			chunk.append(crcbytes >> 8)
			chunk.append(crcbytes & 0xff)
			written = self.__write_chunk(code, chunk)
			ret = written == len(chunk)
			if ret is False:
				return ret

		return True
