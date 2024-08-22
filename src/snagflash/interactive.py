import re
import yaml
import logging
import os
logger = logging.getLogger("snagflash")

from math import ceil

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

	def cmd_flash(self, args: str):
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
			self.flash_mmc(path, offset, device_num, file_size, 0, part)
		else:
			if part is None:
				part = target

			self.flash_mtd(path, offset, part, file_size, 0)

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
			logger.info(f"erasing flash area part {part} offset 0x{offset:x} size 0x{flash_size:x}...")
			fast.oem_run(f"mtd erase {part} 0x{offset:x} 0x{flash_size:x}")

			logger.info(f"flashing file {path}")
			fast.download_section(path, file_offset, file_size, padding=padding)
			fast.oem_run(f"mtd write {part} 0x{fb_addr:x} 0x{offset:x} 0x{flash_size:x}")
			return

		if fb_size % eraseblk_size != 0:
			logger.info("clipping fastboot buffer size to align it with an eraseblock...")
			fb_size = eraseblk_size * (fb_size // eraseblk_size)

		nchunks = flash_size // fb_size
		remainder = flash_size % fb_size

		for i in range(nchunks):
			logger.info(f"downloading section {i + 1}/{nchunks}")
			fast.download_section(path, file_offset, fb_size)
			logger.info(f"erasing flash area offset 0x{file_offset:x} size 0x{fb_size:x}...")
			fast.oem_run(f"mtd erase {part} {file_offset:x} {fb_size:x}")
			logger.info(f"writing section {i + 1}/{nchunks}")
			fast.oem_run(f"mtd write {part} 0x{fb_addr:x} 0x{file_offset:x} 0x{fb_size:x}")
			file_offset += fb_size

		if remainder > 0:
			logger.info("downloading remainder")
			fast.download_section(path, file_offset, remainder)
			logger.info(f"erasing flash area offset 0x{file_offset:x} size 0x{remainder:x}...")
			fast.oem_run(f"mtd erase {part} {file_offset:x} {remainder:x}")
			fast.oem_run(f"mtd write {part} 0x{fb_addr:x} 0x{file_offset:x} 0x{remainder:x}")

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
			logger.info(f"setting MMC device to {device_num}")
			fast.oem_run(f"mmc dev {device_num}")
			part_start = 0
		elif "hwpart" in part:
			hwpart,sep,hwpart_num = part.partition(" ")
			hwpart_num = int(hwpart_num.strip(" "))
			logger.info(f"setting MMC device to {device_num}")
			fast.oem_run(f"mmc dev {device_num} {hwpart_num}")
			part_start = 0
		else:
			logger.info(f"setting MMC device to {device_num}")
			fast.oem_run(f"mmc dev {device_num}; part list mmc {device_num}")
			logger.info("fetching partition start")
			fast.oem_run(f"gpt setenv mmc {device_num} {part};setenv fastboot.part_start $" + "{gpt_partition_addr}")
			part_start = int(fast.getvar("part_start"), 16)

		if file_size <= fb_size:
			logger.info(f"flashing file {path}")
			fast.download_section(path, file_offset, file_size)
			fast.oem_run(f"mmc write 0x{fb_addr:x} 0x{part_start + offset_lba:x} 0x{file_size_lba:x}")
			return

		logger.info("huge file detected, flashing in sections")
		nchunks = file_size // fb_size_aligned
		remainder = file_size % fb_size_aligned
		remainder_lba = ceil(remainder / MMC_LBA_SIZE)

		for i in range(nchunks):
			logger.info(f"flashing section {i + 1}/{nchunks}")
			target_offset = part_start + i * fb_size_lba
			fast.download_section(path, file_offset, fb_size_aligned)
			fast.oem_run(f"mmc write 0x{fb_addr:x} 0x{target_offset:x} 0x{fb_size_lba:x}")
			file_offset += fb_size_aligned

		if remainder > 0:
			logger.info("flashing remainder")
			target_offset = part_start + nchunks * fb_size_lba
			fast.download_section(path, file_offset, remainder)
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

