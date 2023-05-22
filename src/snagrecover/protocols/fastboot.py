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

import usb
import time
from snagrecover import utils
import logging
logger = logging.getLogger("snagrecover")

"""
See doc/android/fastboot-protocol.rst in the U-Boot sources
for more information on fastboot support in U-Boot.
"""

class Fastboot():
	def __init__(self, dev: usb.core.Device, timeout: int = 10000):
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
		# choose max packet size as specified by fastboot spec
		self.max_size = 64
		if dev.speed == usb.util.SPEED_HIGH:
			self.max_size = 512
		elif dev.speed == usb.util.SPEED_SUPER:
			self.max_size = 1024

	def cmd(self, packet: bytes):
		if len(packet) > self.max_size:
			raise ValueError(f"Packet {packet} exceeds the 64-byte length limit.")
		self.dev.write(self.ep_out, packet, timeout=self.timeout)
		status = ""
		t0 = time.time()
		while time.time() - t0 < 10 * self.timeout:
			ret = self.dev.read(self.ep_in, 256, timeout=self.timeout)
			status = bytes(ret[:4])
			if status == b"INFO":
				print(f"(bootloader) {bytes(ret[4:256])}")
			elif status == b"TEXT":
				print(f"(bootloader) {bytes(ret[4:256])}", end="")
			elif status == b"FAIL":
				raise Exception(f"Fastboot fail with message: {bytes(ret[4:256])}")
			elif status == b"OKAY":
				logger.info("fastboot OKAY")
				return bytes(ret[4:])
			elif status == b"DATA":
				length = int("0x" + (bytes(ret[4:12]).decode("ascii")), base=16)
				logger.info(f"fastboot DATA length: {length}")
				return length
		raise Exception("Timeout while completing fastboot transaction")

	def response(self):
		t0 = time.time()
		while time.time() - t0 < 10 * self.timeout:
			ret = self.dev.read(self.ep_in, 256, timeout = self.timeout)
			status = bytes(ret[:4])
			if status in [b"INFO", b"TEXT"]:
				print(f"(bootloader) {bytes(ret[4:256])}", end="")
			elif status == b"FAIL":
				raise Exception(f"Fastboot fail with message: {bytes(ret[4:256])}")
			elif status == b"OKAY":
				logger.info("fastboot OKAY")
				return bytes(ret[4:])
		raise Exception("Timeout while completing fastboot transaction")

	def getvar(self, var: str):
		packet = b"getvar:" + var.encode("ascii") + b"\x00"
		ret = self.cmd(packet)
		print(f"(bootloader) {var} value {ret}")

	def download(self, path: str):
		with open(path, "rb") as file:
			blob = file.read(-1)
		packet = f"download:{len(blob):08x}".encode()
		self.cmd(packet)
		for chunk in utils.dnload_iter(blob, self.max_size):
			self.dev.write(self.ep_out, chunk, timeout=self.timeout)
		self.response()

	def erase(self, part: str):
		packet = f"erase:{part}\x00"
		self.cmd(packet)

	def flash(self, part: str):
		packet = f"flash:{part}\x00"
		self.cmd(packet)

	def boot(self):
		packet = "boot"
		self.cmd(packet)

	def fbcontinue(self):
		"""
		Can't name this 'continue' because Python
		"""
		packet = "continue"
		self.cmd(packet)

	def reboot(self):
		packet = "continue"
		self.cmd(packet)

	def reboot_bootloader(self):
		packet = "reboot-bootloader"
		self.cmd(packet)

	def powerdown(self):
		packet = "powerdown"
		self.cmd(packet)

	def ucmd(self, cmd: str):
		"""
		Execute an arbitrary U-Boot command and
		wait for it to complete.
		"""
		packet = f"UCmd:{cmd}\x00"
		self.cmd(packet)

	def acmd(self, cmd: str):
		"""
		Execute an arbitrary U-Boot command and
		do not wait for it to complete.
		"""
		packet = f"ACmd:{cmd}\x00"
		self.cmd(packet)

	def oem_run(self, cmd: str):
		"""
		Execute an arbitrary U-Boot command
		"""
		packet = f"oem run:{cmd}\x00"
		self.cmd(packet)

	def oem_format(self):
		"""
		Execute gpt write mmc <dev> $partitions
		<dev> is preconfigured in U-Boot
		"""
		packet = "oem format"
		self.cmd(packet)

	def oem_partconf(self, arg: str):
		"""
		Execute mmc partconf <dev> <arg> 0
		<dev> is preconfigured in U-Boot
		"""
		packet = f"oem partconf:{arg}\x00"
		self.cmd(packet)

	def oem_bootbus(self, arg: str):
		"""
		Execute mmc bootbus <dev> <arg> 0
		<dev> is preconfigured in U-Boot
		"""
		packet = f"oem bootbus:{arg}\x00"
		self.cmd(packet)

