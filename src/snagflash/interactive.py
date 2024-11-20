import re
import yaml
import logging
import functools
import random
import os
logger = logging.getLogger("snagflash")

from math import ceil

from snagflash.bmaptools.BmapCopy import Bmap

MMC_LBA_SIZE = 512

class SnagflashCmdError(Exception):
	pass

class SnagflashInteractive():
	help_text = """snagflash interactive mode
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
	The "fb-addr", "fb-size", and "target" environment
	variables are required. For MTD targets, the "eraseblk-size" variable
	is also required.
	partition_name: the name of a GPT or MTD partition, or a hardware partition specified
	by "hwpart <number>"

environment:

target: target device for flashing commands
	must be an mmc or mtd device identifier
	e.g. mmc0, mmc1, etc. or spi-nand0, nand0, etc.
fb-addr: address in memory of the Fastboot buffer
fb-size: size in bytes of the Fastboot buffer
eraseblk-size: size in bytes of an erase block on the target Flash device
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

	def preflash_checks(self):
		"""
		Run a few checks:
		- fb-addr, fb-size and target are defined
		- Fastboot buffer address seems correct
		"""
		if self.checked:
			return

		logger.info("Running pre-flash checks...")

		fb_addr = int(self.request_env("fb-addr"), 0)
		self.request_env("fb-size")
		self.request_env("target")

		fast = self.fast

		pattern = random.randint(0, 255)
		fast.send(pattern.to_bytes(1, "little"))

		fast.oem_run(f"mw.b 0x{(fb_addr + 1):x} 0x{pattern:x} 1")
		try:
			fast.oem_run(f"cmp.b 0x{fb_addr:x} 0x{(fb_addr + 1):x} 1")
		except Exception:
			raise ValueError(f"The given value for fb-addr: 0x{fb_addr:x} seems incorrect! comparison of written check pattern failed") from None

		self.checked = True

	def cmd_flash(self, args: str):
		self.preflash_checks()

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

		file_size = os.path.getsize(path)

		target = self.request_env("target")

		if target.startswith("mmc"):
			device_num = int(target[-1])
			flash_func = functools.partial(self.flash_mmc,
							path=path, offset=offset,
							device_num=device_num, part=part)
		else:
			if part is None:
				part = target

			flash_func = functools.partial(self.flash_mtd,
							path=path, part=part)

		bmap_path = path + ".bmap"
		if os.path.exists(bmap_path):
			logger.info("Found a bmap file, flashing in sparse mode")

			# Verify bmap checksums and get list of ranges
			with open(path, "rb") as image_file:
				with open(bmap_path, "r") as bmap_file:
					bmap = Bmap(image_file, bmap_file)
					list(bmap._get_data(verify=True))

					ranges = []
					for (start, end, _) in bmap._get_block_ranges():
						range_offset = bmap.block_size * start
						size = (end - start + 1) * bmap.block_size
						ranges.append((size, range_offset))

			i = 0
			for (size, range_offset) in ranges:
				logger.info(f"Flashing sparse range {i}/{len(ranges)}")
				flash_func(file_size=size, file_offset=range_offset, offset=offset + range_offset)
				i += 1
		else:
			logger.info("No bmap file found, flashing in non-sparse mode")
			flash_func(file_size=file_size, file_offset=0, offset=offset)

	def flash_mtd(self, path: str, offset: int, part: str, file_size: int, file_offset: int = 0):
		fast = self.fast

		fb_addr = int(self.request_env("fb-addr"), 0)
		fb_size = int(self.request_env("fb-size"), 0)
		eraseblk_size = int(self.request_env("eraseblk-size"), 0)

		if offset % eraseblk_size != 0:
			raise SnagflashCmdError(f"offset 0x{offset:x} is not aligned with an eraseblock")

		if file_size % eraseblk_size != 0:
			logger.info("padding file size to align it with an eraseblock...")
			padding = eraseblk_size - (file_size % eraseblk_size)
			flash_size = file_size + padding
		else:
			padding = None
			flash_size = file_size

		if flash_size <= fb_size:
			logger.debug(f"erasing flash area part {part} offset 0x{offset:x} size 0x{flash_size:x}...")
			fast.oem_run(f"mtd erase {part} 0x{offset:x} 0x{flash_size:x}")

			logger.info(f"flashing file {path} range start 0x{file_offset:x} size 0x{file_size}")
			fast.download_section(path, file_offset, file_size, padding=padding)
			fast.oem_run(f"mtd write {part} 0x{fb_addr:x} 0x{offset:x} 0x{flash_size:x}")
			return

		if fb_size % eraseblk_size != 0:
			logger.debug("clipping fastboot buffer size to align it with an eraseblock...")
			fb_size = eraseblk_size * (fb_size // eraseblk_size)

		nchunks = flash_size // fb_size
		remainder = flash_size % fb_size

		for i in range(nchunks):
			logger.info(f"downloading section {i + 1}/{nchunks}")
			fast.download_section(path, file_offset + i * fb_size, fb_size)

			target_offset = offset + i * fb_size
			logger.info(f"erasing flash area offset 0x{target_offset} size 0x{fb_size:x}...")
			fast.oem_run(f"mtd erase {part} {target_offset:x} {fb_size:x}")

			logger.info(f"writing section {i + 1}/{nchunks}")
			fast.oem_run(f"mtd write {part} 0x{fb_addr:x} 0x{target_offset:x} 0x{fb_size:x}")

		if remainder > 0:
			logger.info("downloading remainder")
			fast.download_section(path, file_offset + nchunks * fb_size, remainder)

			target_offset = offset + nchunks * fb_size
			logger.info(f"erasing flash area offset 0x{target_offset} size 0x{remainder:x}...")
			fast.oem_run(f"mtd erase {part} {target_offset:x} {remainder:x}")

			fast.oem_run(f"mtd write {part} 0x{fb_addr:x} 0x{target_offset:x} 0x{remainder:x}")

	def flash_mmc(self, path: str, offset: int, device_num: int, file_size: int, file_offset: int = 0, part: str = None):
		fast = self.fast

		fb_addr = int(self.request_env("fb-addr"), 0)
		fb_size = int(self.request_env("fb-size"), 0)

		if offset % MMC_LBA_SIZE != 0:
			raise ValueError(f"Given offset {offset} is not aligned with a {MMC_LBA_SIZE}-byte LBA!")

		fb_size_lba = fb_size // MMC_LBA_SIZE
		file_size_lba = ceil(file_size / MMC_LBA_SIZE)
		offset_lba = offset // MMC_LBA_SIZE

		fb_size_aligned = fb_size_lba * MMC_LBA_SIZE

		if part is None:
			logger.debug(f"setting MMC device to {device_num}")
			fast.oem_run(f"mmc dev {device_num}")
			part_start = 0
		elif "hwpart" in part:
			hwpart,sep,hwpart_num = part.partition(" ")
			hwpart_num = int(hwpart_num.strip(" "))
			logger.debug(f"setting MMC device to {device_num} {hwpart_num}")
			fast.oem_run(f"mmc dev {device_num} {hwpart_num}")
			part_start = 0
		else:
			logger.debug(f"setting MMC device to {device_num}")
			fast.oem_run(f"mmc dev {device_num}; part list mmc {device_num}")
			logger.debug("fetching partition start")
			fast.oem_run(f"gpt setenv mmc {device_num} {part};setenv fastboot.part_start $" + "{gpt_partition_addr}")
			part_start = int(fast.getvar("part_start"), 16)

		if file_size <= fb_size:
			logger.info(f"flashing file {path} range start 0x{file_offset:x} size 0x{file_size:x}")
			fast.download_section(path, file_offset, file_size)

			fast.oem_run(f"mmc write 0x{fb_addr:x} 0x{part_start + offset_lba:x} 0x{file_size_lba:x}")
			return

		logger.info("huge file detected, flashing in sections")
		nchunks = file_size // fb_size_aligned
		remainder = file_size % fb_size_aligned
		remainder_lba = ceil(remainder / MMC_LBA_SIZE)

		for i in range(nchunks):
			logger.info(f"flashing section {i + 1}/{nchunks}")
			target_offset = part_start + offset_lba + i * fb_size_lba
			fast.download_section(path, file_offset + i * fb_size_lba, fb_size_aligned)

			fast.oem_run(f"mmc write 0x{fb_addr:x} 0x{target_offset:x} 0x{fb_size_lba:x}")

		if remainder > 0:
			logger.info("flashing remainder")
			target_offset = part_start + offset_lba + nchunks * fb_size_lba
			fast.download_section(path, file_offset + nchunks * fb_size_lba, remainder)

			fast.oem_run(f"mmc write 0x{fb_addr:x} 0x{target_offset:x} 0x{remainder_lba:x}")

	def run(self, cmds: list):
		for cmd in cmds:
			logger.info(f"running command {cmd}")
			match = __class__.cmd_pattern.match(cmd)
			if match is None:
				raise ValueError("Invalid input syntax")

			cur_cmd = match.groups()[0]
			if not hasattr(self, f"cmd_{cur_cmd.replace('-','_')}"):
				raise ValueError("Invalid command {cmd}")

			args = match.groups()[1].strip(" ")
			if args is None:
				args = ""

			getattr(self, f"cmd_{cur_cmd.replace('-','_')}")(args)

	def start(self):
		self.stop = False

		while not self.stop:
			cmd = input("snagflash > ")

			match = __class__.cmd_pattern.match(cmd)
			if match is None:
				self.err("Invalid input syntax, type 'help' for help")
				continue

			cur_cmd = match.groups()[0]
			if not hasattr(self, f"cmd_{cur_cmd.replace('-','_')}"):
				self.err(f"Invalid command {cur_cmd}, type 'help' for help")
				continue

			args = match.groups()[1].strip(" ")
			if args is None:
				args = ""

			try:
				getattr(self, f"cmd_{cur_cmd.replace('-','_')}")(args)
			except SnagflashCmdError as e:
				self.err(f"{cur_cmd} failed, {str(e)}")
				continue

