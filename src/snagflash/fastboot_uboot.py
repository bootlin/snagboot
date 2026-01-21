import re
import yaml
import logging
import functools
import random
import os
import sys
from math import ceil

logger = logging.getLogger("snagflash")

from snagflash.bmaptools.BmapCopy import Bmap

MMC_LBA_SIZE = 512


class SnagflashCmdError(Exception):
	pass


class SnagflashFastbootUboot:
	help_text = """snagflash extended Fastboot mode
syntax: <cmd> <arg1> <arg2> ...
commands:

exit : exit snagflash
quit : exit snagflash
help : show this help text

set <var> <value>: set the value of an environment variable
print <var>: print the value of an environment variable

run <fastboot_cmd>: run a Fastboot command given in Snagflash format

gpt <partitions>: write a GPT partition table to the specified mmc device

flash <image_path> <image_offset> [<partition_name>]
	Write the file at <image_path> to an MTD device or partition.
	Required environment variables:
		- target
		- fb-addr
		- eraseblk-size (only for MTD targets)

	Optional environment variables:
		- fb-size

	If a file named "<image_path>.bmap" exists, snagflash will automatically
	parse it and flash only the block ranges described.
	partition_name: the name of a GPT or MTD partition, or a hardware partition specified
	by "hwpart <number>"

Environment variables:

target: target device for flashing commands
	must be an mmc or mtd device identifier
	e.g. mmc0, mmc1, etc. or spi-nand0, nand0, etc.

fb-addr: address in memory of the Fastboot buffer

eraseblk-size: size in bytes of an erase block on the target Flash device

fb-size: size in bytes of the Fastboot buffer, this can only be used to reduce
         the U-Boot Fastboot buffer size, not increase it.
"""

	op_pattern = r"[\w\-]+"
	cmd_pattern = re.compile("^(" + op_pattern + r")(.*)$")

	def __init__(self, fast):
		self.fast = fast
		self.env = {}
		self.checked = False

	def err(self, msg: str):
		print(f"CLI Error: {msg}")

	def cmd_exit(self, args: str):
		print("Leaving interactive snagflash session...")
		self.stop = True

	def cmd_quit(self, args: str):
		self.cmd_exit()

	def cmd_help(self, args: str):
		print(__class__.help_text)

	def cmd_print(self, args: str):
		if args == "":
			print(yaml.dump(self.env))

		pattern = re.compile(r"^([\w\-]+)$")

		if (match := pattern.match(args)) is None:
			raise SnagflashCmdError("invalid characters or multiple args in command")

		var = match.groups()[0]
		if var not in self.env:
			raise SnagflashCmdError(f"undefined variable {var}")

		print(self.env[var])

	def cmd_set(self, args: str):
		pattern = re.compile(r"^([\w\-]+)\s+([\w\-]+)$")

		if (match := pattern.match(args)) is None:
			print(args)
			raise SnagflashCmdError("invalid characters or number of args in command")

		var = match.groups()[0]
		value = match.groups()[1]

		print(f"setting '{var}' to '{value}'")
		self.env[var] = value

	def cmd_run(self, cmd: str):
		cmd = cmd.split(":", 1)
		cmd, args = cmd[0], cmd[1:]
		cmd = cmd.replace("-", "_")
		if cmd == "continue":
			cmd = "fbcontinue"

		if not hasattr(self.fast, cmd):
			raise SnagflashCmdError(f"Undefined Fastboot command {cmd}")

		logger.info(f"Sending command {cmd} with args {args}")
		ret = getattr(self.fast, cmd)(*args)
		print(f"ret: {ret}")

	def request_env(self, var: str):
		if var not in self.env:
			raise SnagflashCmdError(f"please set the '{var}' environment variable")

		return self.env[var]

	def cmd_gpt(self, args: str):
		partitions = args

		target = self.request_env("target")

		if not target.startswith("mmc"):
			raise SnagflashCmdError("GPT partitioning not supported for MTD targets")

		device_num = int(target[-1])
		self.cmd_run(f"oem_run:gpt write mmc {device_num} '{partitions}'")
		self.cmd_run(f"oem_run:part list mmc {device_num}")

	def get_fb_size(self):
		"""
		Get the download buffer size from the Fastboot variables.
		Reduce it if the "fb-size" Snagflash variable is set.
		"""

		self.fb_size = int(self.fast.getvar("downloadsize"), 16)

		if self.fb_size == 0:
			raise ValueError(
				f"Invalid Fastboot buffer size {self.fb_size}! Please check Fastboot gadget parameters!"
			)

		if "fb-size" in self.env:
			new_fb_size = int(self.env["fb-size"], 0)

			if new_fb_size > self.fb_size:
				raise ValueError(
					f"Cannot increase Fastboot buffer size! Default size is 0x{self.fb_size:x}, requested size is 0x{new_fb_size:x}"
				)

			self.fb_size = new_fb_size

		logger.debug(f"Fastboot buffer size is 0x{self.fb_size:x}")

	def preflash_checks(self):
		"""
		Run a few checks:
		- fb-addr and target are defined
		- Fastboot buffer address seems correct
		"""
		if self.checked:
			return

		logger.info("Running pre-flash checks...")

		fb_addr = int(self.request_env("fb-addr"), 0)

		self.request_env("target")

		fast = self.fast

		pattern = random.randint(0, 255)
		fast.send(pattern.to_bytes(1, "little"))

		fast.oem_run(f"mw.b 0x{(fb_addr + 1):x} 0x{pattern:x} 1")
		try:
			fast.oem_run(f"cmp.b 0x{fb_addr:x} 0x{(fb_addr + 1):x} 1")
		except Exception:
			raise ValueError(
				f"The given value for fb-addr: 0x{fb_addr:x} seems incorrect! comparison of written check pattern failed"
			) from None

		self.checked = True

	def cmd_flash(self, args: str):
		self.preflash_checks()

		self.get_fb_size()

		path, sep, rest = args.partition(" ")
		path = path.strip('"').strip('"')
		rest = rest.strip(" ")

		if " " in rest:
			offset, sep, part = rest.partition(" ")
			part = part.strip(" ")
		else:
			offset = rest
			part = None

		offset = int(offset, 0)

		logger.info(f"Flashing file {path}")

		target = self.request_env("target")

		if target.startswith("mmc"):
			device_num = int(target[-1])
			flash_func = functools.partial(
				self.flash_mmc,
				offset=offset,
				device_num=device_num,
				part=part,
			)
		else:
			if part is None:
				part = target

			flash_func = functools.partial(self.flash_mtd, part=part)

		bmap_path = path + ".bmap"

		ranges = []
		if os.path.exists(bmap_path):
			logger.info("Found a bmap file, listing sparse ranges...")

			# Verify bmap checksums and get list of ranges
			with open(path, "rb") as image_file:
				with open(bmap_path, "r") as bmap_file:
					bmap = Bmap(image_file, bmap_file)
					list(bmap._get_data(verify=True))

					for start, end, _ in bmap._get_block_ranges():
						range_offset = bmap.block_size * start
						size = (end - start + 1) * bmap.block_size
						ranges.append((size, range_offset))
		else:
			ranges.append((os.path.getsize(path), 0))

		multi_ranges = len(ranges) > 1
		with open(path, "rb") as image_file:
			i = 0
			for size, range_offset in ranges:
				if multi_ranges:
					logger.info(f"Flashing sparse range {i}/{len(ranges)}")
				image_file.seek(range_offset)
				flash_func(
					file=image_file,
					file_size=size,
					offset=offset + range_offset,
				)
				i += 1

	def flash_range(
		self, file, flash_func, file_size: int, dst_offset: int, align: int
	):
		fb_addr = int(self.request_env("fb-addr"), 0)
		fb_size_aligned = (self.fb_size // align) * align

		file_bytes_flashed = 0
		while file_bytes_flashed < file_size:
			bytes_remaining = file_size - file_bytes_flashed
			read_size = min(bytes_remaining, fb_size_aligned)

			logger.debug(f"range start 0x{file.tell():x} read size 0x{read_size:x}")

			blob = file.read(read_size)
			bytes_read = len(blob)

			if bytes_read == 0:
				break

			padding = align * ceil(bytes_read / align) - bytes_read
			blob += b"\x00" * padding

			logger.debug(
				f"send size 0x{bytes_read + padding:x} dst offset 0x{dst_offset + file_bytes_flashed:x}"
			)

			flash_func(
				fb_addr,
				blob,
				dst_offset + file_bytes_flashed,
			)

			file_bytes_flashed += bytes_read

			logger.info(
				f"flashed {file_bytes_flashed}/{file_size if file_size < sys.maxsize else '?'} bytes"
			)

		if file_size < sys.maxsize and file_bytes_flashed < file_size:
			raise ValueError(
				f"Truncated flash, only {file_bytes_flashed} bytes were flashed instead of {file_size} bytes"
			)

	def flash_mtd_section(
		self,
		fb_addr: int,
		blob: bytes,
		dest_offset: int,
		part: str,
	):
		fast = self.fast
		dest_size = len(blob)

		logger.debug(
			f"erasing flash area part {part} offset 0x{dest_offset:x} size 0x{dest_size:x}..."
		)
		fast.oem_run(f"mtd erase {part} 0x{dest_offset:x} 0x{dest_size:x}")

		logger.debug("flashing file range")
		fast.send(blob)
		fast.oem_run(
			f"mtd write {part} 0x{fb_addr:x} 0x{dest_offset:x} 0x{dest_size:x}"
		)

	def flash_mtd(self, file, offset: int, part: str, file_size: int):
		logger.info("Flashing to MTD device...")

		eraseblk_size = int(self.request_env("eraseblk-size"), 0)

		if offset % eraseblk_size != 0:
			raise SnagflashCmdError(
				f"offset 0x{offset:x} is not aligned with an eraseblock"
			)

		self.flash_range(
			file,
			functools.partial(self.flash_mtd_section, part=part),
			file_size,
			offset,
			eraseblk_size,
		)

	def flash_mmc_section(
		self,
		fb_addr: int,
		blob: bytes,
		dest_offset: int,
	):
		fast = self.fast

		if dest_offset % MMC_LBA_SIZE != 0:
			raise ValueError(
				f"Given offset {dest_offset} is not aligned with a {MMC_LBA_SIZE}-byte LBA!"
			)

		fast.send(blob)
		fast.oem_run(
			f"mmc write 0x{fb_addr:x} 0x{dest_offset // MMC_LBA_SIZE:x} 0x{len(blob) // MMC_LBA_SIZE:x}"
		)

	def flash_mmc(
		self,
		file,
		offset: int,
		device_num: int,
		file_size: int,
		part: str = None,
	):
		logger.info("Flashing to MMC device...")

		fast = self.fast

		if offset % MMC_LBA_SIZE != 0:
			raise ValueError(
				f"Given offset {offset} is not aligned with a {MMC_LBA_SIZE}-byte LBA!"
			)

		if part is None:
			logger.debug(f"setting MMC device to {device_num}")
			fast.oem_run(f"mmc dev {device_num}")
			part_start = 0
		elif "hwpart" in part:
			hwpart, sep, hwpart_num = part.partition(" ")
			hwpart_num = int(hwpart_num.strip(" "))
			logger.debug(f"setting MMC device to {device_num} {hwpart_num}")
			fast.oem_run(f"mmc dev {device_num} {hwpart_num}")
			part_start = 0
		else:
			logger.debug(f"setting MMC device to {device_num}")
			fast.oem_run(f"mmc dev {device_num}; part list mmc {device_num}")
			logger.debug("fetching partition start")
			fast.oem_run(
				f"gpt setenv mmc {device_num} {part};setenv fastboot.part_start $"
				+ "{gpt_partition_addr}"
			)
			part_start = int(fast.getvar("part_start"), 16) * MMC_LBA_SIZE

		self.flash_range(
			file,
			self.flash_mmc_section,
			file_size,
			part_start + offset,
			MMC_LBA_SIZE,
		)

	def run(self, cmds: list):
		for cmd in cmds:
			cmd = cmd.strip()

			if cmd == "" or cmd[0] == "#":
				continue

			logger.info(f"running command {cmd}")
			match = __class__.cmd_pattern.match(cmd)
			if match is None:
				raise ValueError("Invalid input syntax")

			cur_cmd = match.groups()[0]
			if not hasattr(self, f"cmd_{cur_cmd.replace('-', '_')}"):
				raise ValueError("Invalid command {cmd}")

			args = match.groups()[1].strip(" ")
			if args is None:
				args = ""

			getattr(self, f"cmd_{cur_cmd.replace('-', '_')}")(args)

	def start(self):
		self.stop = False

		while not self.stop:
			cmd = input("snagflash > ")

			match = __class__.cmd_pattern.match(cmd)
			if match is None:
				self.err("Invalid input syntax, type 'help' for help")
				continue

			cur_cmd = match.groups()[0]
			if not hasattr(self, f"cmd_{cur_cmd.replace('-', '_')}"):
				self.err(f"Invalid command {cur_cmd}, type 'help' for help")
				continue

			args = match.groups()[1].strip(" ")
			if args is None:
				args = ""

			try:
				getattr(self, f"cmd_{cur_cmd.replace('-', '_')}")(args)
			except SnagflashCmdError as e:
				self.err(f"{cur_cmd} failed, {str(e)}")
				continue
