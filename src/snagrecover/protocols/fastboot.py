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

import os
import usb
import time
import tempfile
from typing import Optional, Union

from snagrecover import utils
from snagflash.android_sparse_file.utils import (
	split_streaming,
	split_streaming_raw,
	is_sparse_file,
)
from snagflash.android_sparse_file.sparse import MAGIC

import logging

logger = logging.getLogger("snagrecover")

MAX_LIBUSB_TRANSFER_SIZE = 0x40000

"""
See doc/android/fastboot-protocol.rst in the U-Boot sources
for more information on fastboot support in U-Boot.
"""

FASTBOOT_UNRECOGNIZED_CMD_RESPONSE = b"unrecognized command"

CHECK_OEM_RUN_CMD_SUPPORT = "oem run:version\x00"


class FastbootError(Exception):
	def __init__(self, message, data=None):
		self.message = message
		self.data = data
		super().__init__(self.message)

	def __str__(self):
		return f"Fastboot error: {self.message}"


class Fastboot:
	def __init__(self, dev: usb.core.Device, timeout: int = 10000):
		self.dev = dev
		cfg = dev.get_active_configuration()
		# select the first interface we find with a bulk in ep and a bulk out ep
		eps_found = False
		for intf in cfg.interfaces():
			ep_in, ep_out = None, None
			for ep in intf.endpoints():
				is_bulk = (
					ep.bmAttributes & usb.ENDPOINT_TYPE_MASK
				) == usb.ENDPOINT_TYPE_BULK
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
			raise FastbootError("No BULK IN/OUT endpoint pair found in device")
		self.ep_in = ep_in
		self.ep_out = ep_out
		self.timeout = timeout
		# when ep_out.write() is called, lower layers will take care of
		# splitting up the transfer into appropriately sized packets.
		# However, writing the entire image in one go causes memory
		# allocation issues in libusb for very large transfers.
		# Thus, the transfer is split up into preliminary chunks.
		# The maximum chunk size is chosen to match upper transfer
		# limits for some USB kernel syscalls.

		self.max_size = MAX_LIBUSB_TRANSFER_SIZE
		self.oem_run_basecmd = None

	def _is_cmd_supported(self, cmd: str) -> bool:
		try:
			self.cmd(cmd)
		except FastbootError as e:
			if e.data and FASTBOOT_UNRECOGNIZED_CMD_RESPONSE in e.data:
				return False
		return True

	def cmd(
		self, packet: Optional[bytes] = None, loglevel=logging.DEBUG
	) -> Union[bytes, int]:
		if packet is not None:
			self.dev.write(self.ep_out, packet, timeout=self.timeout)
		t0 = time.time()
		while time.time() - t0 < 10 * self.timeout:
			ret = self.dev.read(self.ep_in, 256, timeout=self.timeout)
			status = bytes(ret[:4])
			data = bytes(ret[4:256])
			if status in [b"INFO", b"TEXT"]:
				logger.log(loglevel, f"(bootloader) {data}")
			elif status == b"FAIL":
				raise FastbootError(f"Fastboot fail with message: {data}", data)
			elif status == b"OKAY":
				logger.log(loglevel, "fastboot OKAY")
				return data
			elif packet is not None and status == b"DATA":
				length = int("0x" + (data.decode("ascii")), base=16)
				logger.log(loglevel, f"fastboot DATA length: {length}")
				return length
		raise FastbootError("Timeout while completing fastboot transaction")

	def getvar(self, var: str):
		packet = b"getvar:" + var.encode("ascii") + b"\x00"
		ret = self.cmd(packet)
		logger.info(f"(bootloader) {var} value {ret}")
		return ret

	def send(self, blob: bytes, padding: int = 0):
		packet = f"download:{len(blob) + padding:08x}".encode()
		self.cmd(packet)
		for chunk in utils.dnload_iter(blob + b"\x00" * padding, self.max_size):
			self.dev.write(self.ep_out, chunk, timeout=self.timeout)
		self.cmd(loglevel=logging.INFO)

	def download(self, path: str, padding: int = 0):
		with open(path, "rb") as file:
			blob = file.read(-1)
			self.send(blob, padding)

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
		if self.oem_run_basecmd is None:
			# The support of OEM commands is depending on the configuration
			# u-boot was built with, so they need to be probed at runtime.
			# The command handler for oem run is actually ucmd in the sources,
			# therefore it's safe to use this as fallback.
			self.oem_run_basecmd = (
				"oem run"
				if self._is_cmd_supported(CHECK_OEM_RUN_CMD_SUPPORT)
				else "UCmd"
			)

		packet = f"{self.oem_run_basecmd}:{cmd}\x00"
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

	def reset(self):
		"""
		Run the 'reset' U-Boot command.
		This one requires special handling because
		getting the Fastboot gadget response will not be possible.
		"""
		packet = "oem run:reset\x00"

		self.dev.write(self.ep_out, packet, timeout=self.timeout)

	def get_max_download_size(self) -> int:
		"""
		Read the "max-download-size" Fastboot variable from U-Boot.
		Raises a FastbootError if it cannot be read, or if it is 0.
		"""
		try:
			maxsize = int(self.getvar("max-download-size"), 0)
		except Exception as e:
			raise FastbootError(
				"Failed to get fastboot max-download-size variable"
			) from e
		if maxsize == 0:
			raise FastbootError("Fastboot variable max-download-size is 0")
		return maxsize

	def split_and_flash(self, splitter, fname: str, part: str, maxsize: int):
		"""
		Split 'fname' into a series of android sparse fragments (each no
		bigger than 'maxsize') using the given 'splitter' generator
		function, then download and flash each fragment in turn to 'part'.

		'splitter' is expected to have the same signature/semantics as
		split_streaming()/split_streaming_raw(): splitter(path, dest, bufsize)
		is a generator yielding the path to each fragment file (dest, reused
		and overwritten for every fragment).

		Each split file is created, downloaded, flashed, and then reused for
		the next split. This allows processing of arbitrarily large images
		with constant memory usage.
		"""
		with tempfile.TemporaryDirectory() as tmp:
			temppath = os.path.join(tmp, "split.img")
			try:
				# Count total splits upfront for "split X/N" logging below
				total_splits = sum(1 for _ in splitter(fname, temppath, maxsize))

				split_count = 0
				logger.info(f"Starting streaming flash ({total_splits} split(s))...")

				for split_file in splitter(fname, temppath, maxsize):
					split_count += 1
					logger.info(
						f"Processing split {split_count}/{total_splits}: Downloading {split_file}"
					)
					try:
						self.download(split_file)
					except Exception as e:
						raise FastbootError(
							f"Failed to download split {split_count}/{total_splits}: {e}"
						) from e

					logger.info(
						f"Processing split {split_count}/{total_splits}: Flashing to {part}"
					)
					try:
						self.flash(part)
					except Exception as e:
						raise FastbootError(
							f"Failed to flash split {split_count}/{total_splits}: {e}"
						) from e

					logger.debug(
						f"Split {split_count}/{total_splits} completed successfully"
					)

				logger.info(
					f"Successfully flashed {split_count}/{total_splits} split file(s) to {part}"
				)
			except Exception as e:
				raise FastbootError(f"Streaming flash failed: {e}") from e

	def flash_sparse(self, args: str):
		"""
		Download and flash an android sparse file.
		If the file is too big, it's splitting into
		smaller android sparse files.
		"""
		maxsize = self.get_max_download_size()

		arg_list = args.split(":", 1)
		cnt = len(arg_list)
		if cnt != 2:
			raise FastbootError(
				f"Wrong arguments count {cnt}, expected 2. Given {args}"
			)
		fname = arg_list[0]
		if not os.path.exists(fname):
			raise FastbootError(f"File {fname} does not exist")

		# Verify the file is a valid Android sparse file by checking magic cookie
		try:
			if not is_sparse_file(fname):
				raise FastbootError(
					f"File {fname} is not a valid Android sparse file, "
					f"or is too small to be a valid sparse file. "
					f"Expected magic 0x{MAGIC:08X}"
				)
			logger.info(f"Verified {fname} is a valid Android sparse file")
		except IOError as e:
			raise FastbootError(f"Failed to read file {fname}: {e}") from e

		part = arg_list[1]

		self.split_and_flash(split_streaming, fname, part, maxsize)

	def flash_image(self, args: str):
		"""
		Download and flash an image file (raw binary or android sparse) to
		a partition, handling both formats transparently:

		1. Reads "max-download-size" from U-Boot (fails if unavailable or 0).
		2. If the file fits within max-download-size, downloads and flashes
		it directly, with no splitting required.
		3. If the file is bigger than max-download-size:
			- If it's an Android sparse file, it's split into smaller sparse
			fragments (reusing the same logic as flash_sparse()).
			- If it's a raw binary file, it's split by synthesizing a single
			logical RAW region covering the whole image, then splitting
			that into smaller sparse fragments the same way. This gives
			raw files automatic splitting support that they otherwise
			don't have with a plain download()+flash().

		Each emitted fragment (sparse or raw-derived) is downloaded and
		flashed in turn, with progress logged as "split X/N".
		"""
		arg_list = args.split(":", 1)
		cnt = len(arg_list)
		if cnt != 2:
			raise FastbootError(
				f"Wrong arguments count {cnt}, expected 2. Given {args}"
			)
		fname = arg_list[0]
		part = arg_list[1]

		if not os.path.exists(fname):
			raise FastbootError(f"File {fname} does not exist")

		maxsize = self.get_max_download_size()

		filesize = os.path.getsize(fname)

		if filesize <= maxsize:
			logger.info(
				f"File {fname} ({filesize} bytes) fits within "
				f"max-download-size (0x{maxsize:x}), flashing directly"
			)
			self.download(fname)
			self.flash(part)
			return

		if is_sparse_file(fname):
			logger.info(
				f"File {fname} is an Android sparse file, splitting to fit "
				f"max-download-size (0x{maxsize:x})"
			)
			self.split_and_flash(split_streaming, fname, part, maxsize)
		else:
			logger.info(
				f"File {fname} is a raw binary file, splitting into sparse "
				f"fragments to fit max-download-size (0x{maxsize:x})"
			)
			self.split_and_flash(split_streaming_raw, fname, part, maxsize)
