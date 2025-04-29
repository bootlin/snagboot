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
from snagrecover import utils
from snagflash.android_sparse_file.utils import split

import logging
logger = logging.getLogger("snagrecover")

MAX_LIBUSB_TRANSFER_SIZE = 0x40000

# Intel Keembay USB VID:PID
KEEMBAY_VID = 0x8087
KEEMBAY_PID_RECOVERY = 0x0b39
KEEMBAY_PID_FASTBOOT = 0xda00

"""
See doc/android/fastboot-protocol.rst in the U-Boot sources
for more information on fastboot support in U-Boot.
"""

class FastbootError(Exception):
	def __init__(self, message):
		self.message = message
		super().__init__(self.message)

	def __str__(self):
		return f"Fastboot error: {self.message}"

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

	def cmd(self, packet: bytes):
		self.dev.write(self.ep_out, packet, timeout=self.timeout)
		status = ""
		t0 = time.time()
		while time.time() - t0 < 10 * self.timeout:
			ret = self.dev.read(self.ep_in, 256, timeout=self.timeout)
			status = bytes(ret[:4])
			if status == b"INFO":
				logger.debug(f"(bootloader) {bytes(ret[4:256])}")
			elif status == b"TEXT":
				logger.debug(f"(bootloader) {bytes(ret[4:256])}", end="")
			elif status == b"FAIL":
				raise FastbootError(f"Fastboot fail with message: {bytes(ret[4:256])}")
			elif status == b"OKAY":
				logger.debug("fastboot OKAY")
				return bytes(ret[4:])
			elif status == b"DATA":
				length = int("0x" + (bytes(ret[4:12]).decode("ascii")), base=16)
				logger.debug(f"fastboot DATA length: {length}")
				return length
		raise FastbootError("Timeout while completing fastboot transaction")

	def response(self):
		t0 = time.time()
		while time.time() - t0 < 10 * self.timeout:
			ret = self.dev.read(self.ep_in, 256, timeout = self.timeout)
			status = bytes(ret[:4])
			if status in [b"INFO", b"TEXT"]:
				logger.info(f"(bootloader) {bytes(ret[4:256])}", end="")
			elif status == b"FAIL":
				raise FastbootError(f"Fastboot fail with message: {bytes(ret[4:256])}")
			elif status == b"OKAY":
				logger.info("fastboot OKAY")
				return bytes(ret[4:])
		raise FastbootError("Timeout while completing fastboot transaction")

	def getvar(self, var: str):
		packet = b"getvar:" + var.encode("ascii") + b"\x00"
		ret = self.cmd(packet)
		logger.info(f"(bootloader) {var} value {ret}")
		return ret

	def send(self, blob: bytes, padding: int = None):
		if padding is None:
			padding = 0

		packet = f"download:{len(blob) + padding:08x}".encode()
		self.cmd(packet)
		for chunk in utils.dnload_iter(blob + b"\x00" * padding, self.max_size):
			self.dev.write(self.ep_out, chunk, timeout=self.timeout)
		self.response()

	def download_section(self, path: str, offset: int, size: int, padding: int = None):
		with open(path, "rb") as file:
			file.seek(offset)
			blob = file.read(size)

		self.send(blob, padding)

	def download(self, path: str, padding: int = None):
		self.download_section(path, 0, -1, padding)

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
		
	def format(self):
		"""
		Format the device using oem format command.
		This is an alias for oem_format for compatibility with other tools.
		"""
		return self.oem_format()

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


	def flashall(self, args: str):
		"""
		Flash multiple images to their respective partitions.
		This is particularly useful for Keembay devices.
		
		Args:
			args: Comma-separated list of image files to flash
		"""
		images = args.split(',')
		if not images:
			raise FastbootError("No images provided for flashall")
		
		# Keembay partition mapping
		partition_img_mapping = {
			"boot.img": "boot_a",
			"system.img": "system_a",
			"syshash.img": "syshash_a",
			"data.img": "data",
			"factory.img": "factory",
		}
		
		# Secondary partition mapping for A/B partitioning
		secondary_mapping = {
			"boot.img": "boot_b",
			"system.img": "system_b",
			"syshash.img": "syshash_b",
		}
		
		# Format the device first
		try:
			self.oem_format()
			logger.info("Device formatted successfully")
		except Exception as e:
			logger.error(f"Failed to format device: {str(e)}")
			raise FastbootError("Failed to format device") from e
		
		# Flash each image to its respective partition
		for image in images:
			image_name = os.path.basename(image)
			if image_name not in partition_img_mapping:
				logger.warning(f"Unknown image type: {image_name}, skipping")
				continue
			
			part_name = partition_img_mapping[image_name]
			logger.info(f"Flashing {image} to partition {part_name}")
			
			try:
				# Download and flash the image
				self.download(image)
				self.flash(part_name)
				logger.info(f"Partition {part_name} flashed successfully")
				
				# Flash to secondary partition if applicable
				if image_name in secondary_mapping:
					secondary_part = secondary_mapping[image_name]
					logger.info(f"Flashing {image} to secondary partition {secondary_part}")
					self.download(image)
					self.flash(secondary_part)
					logger.info(f"Secondary partition {secondary_part} flashed successfully")
			except Exception as e:
				logger.error(f"Failed to flash {image_name}: {str(e)}")
				raise FastbootError(f"Failed to flash {image_name}") from e
		
		logger.info("All images flashed successfully")
	
	def flash_sparse(self, args: str):
		"""
		Download and flash an android sparse file.
		If the file is too big, it's splitting into
		smaller android sparse files.
		"""
		try:
			maxsize = int(self.getvar("max-download-size"), 0)
		except Exception as e:
			raise FastbootError("Failed to get fastboot max-download-size variable") from e
		if maxsize == 0:
			raise FastbootError("Fastboot variable max-download-size is 0")
		arg_list = args.split(':')
		cnt = len(arg_list)
		if cnt != 2:
			raise FastbootError(f"Wrong arguments count {cnt}, expected 2. Given {args}")
		fname = arg_list[0]
		if not os.path.exists(fname):
			raise FastbootError(f"File {fname} does not exist")
		part = arg_list[1]
		with tempfile.TemporaryDirectory() as tmp:
			temppath = os.path.join(tmp, 'sparse.img')
			try:
				splitfiles = split(fname, temppath, maxsize)
				logger.info(f"Split fastboot file into {len(splitfiles)} file(s)")
				for f in splitfiles:
					logger.info(f"Downloading {f}")
					try:
						self.download(f)
					except Exception as e:
						raise FastbootError(f"Failed to download: {e}") from e
					logger.info(f"Flashing {f}")
					try:
						self.flash(part)
					except Exception as e:
						raise FastbootError(f"Failed to flash: {e}") from e
			except Exception as e:
				raise FastbootError(f"{e}") from e


class FastbootDevice:
	"""
	A higher-level class for interacting with a device in fastboot mode.
	This class provides methods for common operations like flashing firmware.
	"""
	
	def __init__(self, usb_dev: usb.core.Device, timeout: int = 10000):
		"""
		Initialize a FastbootDevice instance.
		
		Args:
			usb_dev: The USB device in fastboot mode
			timeout: Timeout for USB operations in milliseconds
		"""
		self.usb_dev = usb_dev
		self.fastboot = Fastboot(usb_dev, timeout)
		self.serialno = None
		self._get_serial_number()
	
	def _get_serial_number(self):
		"""Get the device serial number."""
		try:
			self.serialno = self.usb_dev.serial_number
			if self.serialno:
				self.serialno = self.serialno.upper()
		except Exception as e:
			logger.warning(f"Failed to get serial number: {str(e)}")
			self.serialno = None
	
	def stage(self, fip_path: str):
		"""
		Stage a FIP (Firmware Image Package) to the device.
		This is specific to Intel Keembay devices.
		
		Args:
			fip_path: Path to the FIP file
		
		Returns:
			True if successful
		"""
		logger.info(f"Staging FIP to device with serial: {self.serialno}")
		
		# Download the FIP file to the device
		try:
			self.fastboot.download(fip_path)
			logger.info("FIP downloaded successfully")
			return True
		except Exception as e:
			logger.error(f"Failed to stage FIP: {str(e)}")
			raise
	
	def format(self):
		"""
		Format the device's storage.
		
		Returns:
			True if successful
		"""
		logger.info("Formatting device storage")
		try:
			self.fastboot.oem_format()
			logger.info("Device formatted successfully")
			return True
		except Exception as e:
			logger.error(f"Failed to format device: {str(e)}")
			raise
	
	def flash_partition(self, part_name: str, img_path: str):
		"""
		Flash an image to a specific partition.
		
		Args:
			part_name: Name of the partition to flash
			img_path: Path to the image file
		
		Returns:
			True if successful
		"""
		logger.info(f"Flashing {img_path} to partition {part_name}")
		try:
			# Download the image to the device
			self.fastboot.download(img_path)
			# Flash the downloaded image to the specified partition
			self.fastboot.flash(part_name)
			logger.info(f"Partition {part_name} flashed successfully")
			return True
		except Exception as e:
			logger.error(f"Failed to flash partition {part_name}: {str(e)}")
			raise
	
	def erase_partition(self, part_name: str):
		"""
		Erase a specific partition.
		
		Args:
			part_name: Name of the partition to erase
		
		Returns:
			True if successful
		"""
		logger.info(f"Erasing partition {part_name}")
		try:
			self.fastboot.erase(part_name)
			logger.info(f"Partition {part_name} erased successfully")
			return True
		except Exception as e:
			logger.error(f"Failed to erase partition {part_name}: {str(e)}")
			raise
	
	def reboot(self):
		"""
		Reboot the device.
		
		Returns:
			True if successful
		"""
		logger.info("Rebooting device")
		try:
			self.fastboot.reboot()
			logger.info("Device reboot initiated")
			return True
		except Exception as e:
			logger.error(f"Failed to reboot device: {str(e)}")
			raise
	
	def get_variable(self, var_name: str):
		"""
		Get a fastboot variable from the device.
		
		Args:
			var_name: Name of the variable to get
		
		Returns:
			The variable value as bytes
		"""
		try:
			return self.fastboot.getvar(var_name)
		except Exception as e:
			logger.error(f"Failed to get variable {var_name}: {str(e)}")
			raise
	
	def flashall(self, img_paths: list):
		"""
		Flash multiple images to their respective partitions.
		This is particularly useful for Keembay devices.
		
		Args:
			img_paths: List of image file paths to flash
		
		Returns:
			True if successful
		"""
		logger.info(f"Flashing multiple images to device with serial: {self.serialno}")
		
		try:
			# Convert list to comma-separated string
			img_paths_str = ','.join(img_paths)
			self.fastboot.flashall(img_paths_str)
			logger.info("All images flashed successfully")
			return True
		except Exception as e:
			logger.error(f"Failed to flash images: {str(e)}")
			raise
