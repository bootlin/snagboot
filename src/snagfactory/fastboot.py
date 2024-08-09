import os
import sys
import logging
import logging.handlers
from multiprocessing import Process
from math import ceil

from snagflash.fastboot import fastboot
from snagfactory.utils import SnagFactoryConfigError

DEFAULT_FB_BUFFER_SIZE = 0x7000000
MMC_LBA_SIZE = 512

def fb_config_bytes_to_lbas(num: int):
	if num % MMC_LBA_SIZE != 0:
		raise SnagFactoryConfigError(f"Value {num} is not a multiple of {MMC_LBA_SIZE} bytes!")

	return num // MMC_LBA_SIZE

class FastbootArgs:
	def __init__(self, d):
		for key, value in d.items():
			setattr(self, key, value)

def run_fastboot_task(args, log_queue):
	sys.stdout = open(os.devnull, 'w')
	sys.stderr = open(os.devnull, 'w')

	logger = logging.getLogger("snagflash")
	snagrecover_logger = logging.getLogger("snagrecover")
	snagrecover_logger.parent = logger

	logger.propagate = False
	logger.handlers.clear()
	log_handler = logging.handlers.QueueHandler(log_queue)
	log_formatter = logging.Formatter(f"%(asctime)s,%(msecs)03d [{args.port}][%(levelname)-8s] %(message)s", datefmt="%H:%M:%S")
	log_handler.setFormatter(log_formatter)
	logger.addHandler(log_handler)
	logger.setLevel(logging.INFO)

	try:
		fastboot(args)
	except Exception as e:
		logger.error(f"Caught exception from snagflash: {e}")
		sys.exit(-1)

	logger.handlers.clear()

class FastbootTask():
	def __init__(self, config: dict, num: int, globals: dict):
		self.name = type(self).__name__[12:].lower()
		self.config = config
		self.globals = globals
		self.args = None
		self.log_queue = None
		self.num = num
		self.resets_board = False
		self.pauses_board = False
		self.pause_action = ""
		self.cmds = []

	def get_cmds(self):
		pass

	def cmd_reset(self):
		self.cmds.append("reset")

	def cmd_run(self, cmd: str):
		self.cmds.append(f"oem_run:{cmd}")

	def cmd_setenv(self, name: str, value: str):
		self.cmd_run(f"setenv {name} {value}")

	def cmd_setexpr(self, name: str, expr: str):
		self.cmd_run(f"setexpr {name} {expr}")

	def cmd_download(self, image: str, section: tuple = None):
		cmd = f"download:{image}"

		if section is not None:
			offset,size = section
			cmd += f"#{offset}:{size}"

		self.cmds.append(cmd)

	def cmd_flash(self, target: str):
		self.cmds.append(f"flash:{target}")

	def cmd_format(self):
		self.cmds.append("oem_format")

	def attach(self, board):
		self.port = board.path
		self.log_queue = board.log_queue

		args = {
			"loglevel": "info",
			"timeout": 60000,
			"factory": True,
			"port": self.port,
			"fastboot_cmd": self.cmds,
		}

		self.args = FastbootArgs(args)

	def get_process(self):
		self.process = Process(target=run_fastboot_task, args=(self.args, self.log_queue))
		return self.process

	def flash_huge_image(self, image: str, part_name: str, part_start: int = None, image_offset: int = None):
		raise SnagFactoryConfigError(f"Image file {image} is larger than Fastboot buffer! Huge image flashing is not supported for the '{self.name}' task")

	def flash_to_part_offset(self, image: str, offset: int, part_name: str, part_start: int = None):
		raise SnagFactoryConfigError(f"Flashing to partition offsets is not supported for the '{self.name}' task!")

	def flash_image_to_part(self, image: str, part, part_start = None, image_offset = None):
		fb_buffer_size = self.globals.get("fb-buffer-size", DEFAULT_FB_BUFFER_SIZE)

		if fb_buffer_size % MMC_LBA_SIZE != 0:
			raise SnagFactoryConfigError(f"Specified fb_buffer_size is invalid! Must be a multiple of {MMC_LBA_SIZE}")

		if not os.path.exists(image):
			raise SnagFactoryConfigError(f"Specified image file {image} does not exist!")

		file_size = os.path.getsize(image)

		if file_size > fb_buffer_size:
			self.flash_huge_image(image, part, part_start, image_offset)
		elif image_offset is not None:
			self.flash_to_part_offset(image, image_offset, part, part_start)
		else:
			self.cmd_download(image)
			self.cmd_flash(part)

class FastbootMMCTask(FastbootTask):
	def __init__(self, config: dict, num: int, globals: dict):
		super().__init__(config, num, globals)

		target_device = self.globals["target-device"]
		if not target_device.startswith("mmc"):
			raise SnagFactoryConfigError(f"the '{self.name}' task is only supported on mmc backends")

		self.device_num = int(target_device[-1])

	def flash_to_part_offset(self, image: str, offset: int, part_name: str, part_start: int = None):
		"""
		Flash an image to an offset inside a partition. To achieve
		this, temporary Fastboot partition aliases are used.
		"""
		file_size = os.path.getsize(image)

		if part_start is None:
			self.cmd_run(f"gpt setenv mmc {self.device_num} {part_name}")
		else:
			self.cmd_setenv("gpt_partition_addr", f"0x{fb_config_bytes_to_lbas(part_start):x}")

		self.cmd_setexpr("snag_offset", '0x${gpt_partition_addr} + ' + f"0x{fb_config_bytes_to_lbas(offset):x}")

		self.cmd_setenv("fastboot_raw_partition_temp", '0x${snag_offset}' + f" 0x{ceil(file_size / MMC_LBA_SIZE):x}")
		self.cmd_download(image)
		self.cmd_flash("temp")

	def flash_huge_image(self, image: str, part_name: str, part_start: int = None, image_offset: int = None):
		"""
		Flash an image that doesn't fit inside the Fastboot RAM buffer.
		This is done by flashing the image in sections. Each section has
		to be written to a specific offset in the storage device. To
		achieve this, temporary Fastboot partition aliases are used.
		"""

		fb_buffer_size = fb_config_bytes_to_lbas(self.globals.get("fb-buffer-size", DEFAULT_FB_BUFFER_SIZE))
		file_size = os.path.getsize(image)

		nchunks = file_size // (fb_buffer_size * MMC_LBA_SIZE)
		remainder = file_size % (fb_buffer_size * MMC_LBA_SIZE)

		if part_start is None:
			self.cmd_run(f"gpt setenv mmc {self.device_num} {part_name}")
		else:
			self.cmd_setenv("gpt_partition_addr", f"0x{fb_config_bytes_to_lbas(part_start):x}")

		if image_offset is not None:
			self.cmd_setexpr("gpt_partition_addr", '0x${gpt_partition_addr} + ' + f"0x{fb_config_bytes_to_lbas(image_offset):x}")

		for i in range(0, nchunks):
			# setexpr interprets every number as a hexadecimal value
			# I've added '0x' prefixes just in case this changes for some reason
			self.cmd_setexpr("snag_offset", '0x${gpt_partition_addr} + ' + f"0x{i * fb_buffer_size:x}")
			self.cmd_setenv("fastboot_raw_partition_temp", '0x${snag_offset}' + f" 0x{fb_buffer_size:x}")
			offset = i * fb_buffer_size * MMC_LBA_SIZE
			size = fb_buffer_size * MMC_LBA_SIZE
			self.cmd_download(image, section=(offset, size))
			self.cmd_flash("temp")

		if remainder > 0:
			self.cmd_setexpr("snag_offset", '0x${gpt_partition_addr} + ' + f"0x{(nchunks * fb_buffer_size):x}")
			self.cmd_setenv("fastboot_raw_partition_temp", '0x${snag_offset}' + f" 0x{ceil(remainder / MMC_LBA_SIZE):x}")
			offset = nchunks * fb_buffer_size * MMC_LBA_SIZE
			self.cmd_download(image, section=(offset, remainder))
			self.cmd_flash("temp")


class FastbootTaskGPT(FastbootMMCTask):
	def flash_partition_images(self):
		part_index = 1

		for partition in self.config:
			if "image" not in partition:
				continue

			if "name" in partition:
				part_name = partition["name"]
			else:
				part_name = f"{self.device_num}:{part_index}"

			image_offset = partition.get("image-offset", None)

			self.flash_image_to_part(partition["image"], part_name, image_offset=image_offset)

	def flash_partition_table(self):
		partitions_env = ""

		for partition in self.config:
			if "size" not in partition or "name" not in partition:
				raise SnagFactoryConfigError("Invalid partition table entry found in config file, partition size and name must be specified!")

			for key, value in partition.items():
				if key == "image":
					continue

				partitions_env += f"{key}={value},"

			partitions_env = partitions_env.rstrip(",") + ";"

		self.cmd_setenv("partitions", f"'{partitions_env}'")
		self.cmd_format()
		self.cmd_run(f"part list mmc {self.device_num}")

	def get_cmds(self):
		self.flash_partition_table()
		self.flash_partition_images()

class FastbootTaskRun(FastbootTask):
	def get_cmds(self):
		return self.config

class FastbootTaskFlash(FastbootTask):
	def get_cmds(self):
		for entry in self.config:
			part = entry["part"]
			image = entry["image"]
			image_offset = entry.get("image-offset", None)

			self.flash_image_to_part(image, part, image_offset=image_offset)

class FastbootTaskVirtualPart(FastbootMMCTask):
	def get_cmds(self):
		for partition in self.config:
			name = partition["name"]
			start = fb_config_bytes_to_lbas(partition["start"])
			size = fb_config_bytes_to_lbas(partition["size"])
			raw_part = f"0x{start:x} 0x{size:x}"

			if "hwpart" in partition:
				raw_part += f" mmcpart {partition['hwpart']}"

			self.cmd_setenv(f"fastboot_raw_partition_{name}", raw_part)

class FastbootTaskReset(FastbootTask):
	def __init__(self, config: dict, num: int, globals: dict):
		super().__init__(config, num, globals)
		self.resets_board = True

	def get_cmds(self):
		self.cmd_reset()

class FastbootTaskPromptOperator(FastbootTask):
	def __init__(self, config: dict, num: int, globals: dict):
		super().__init__(config, num, globals)
		self.resets_board = config.get("reset-before", False)
		self.pauses_board = True

		if "prompt" not in config:
			raise SnagFactoryConfigError("Missing parameter 'prompt' for task 'prompt-operator'!")

		self.pause_action = config["prompt"]

	def get_cmds(self):
		if self.resets_board:
			self.cmd_reset()

class FastbootTaskEmmcHwpart(FastbootMMCTask):
	def __init__(self, config: dict, num: int, globals: dict):
		super().__init__(config, num, globals)
		self.resets_board = True
		self.pauses_board = not config.get("skip-pwr-cycle", False)
		self.pause_action = "please power-cycle the board"

		if "euda" not in config:
			raise SnagFactoryConfigError("Missing 'euda' configuration for emmc-hwpart task!")

	def get_cmds(self):
		euda = self.config["euda"]

		if "start" not in euda or "size" not in euda:
			raise SnagFactoryConfigError("Missing start and/or size parameters for emmc-hwpart euda section")

		euda_start = fb_config_bytes_to_lbas(euda["start"])
		euda_size = fb_config_bytes_to_lbas(euda["size"])

		self.cmd_setenv("hwpart_usr", f"user enh 0x{euda_start:x} 0x{euda_size:x} wrrel {'on' if euda.get('wrrel', False) else 'off'}")

		hwpart_args = '${hwpart_usr}'

		i = 1
		while f"gp{i}" in self.config:
			gp = self.config[f"gp{i}"]

			if "size" not in gp or "enh" not in gp:
				raise SnagFactoryConfigError(f"Missing size and/or enh parameters for emmc-hwpart gp{i} section")
			gp_size = fb_config_bytes_to_lbas(gp["size"])

			self.cmd_setenv(f"hwpart_gp{i}", f"gp{i} 0x{gp_size:x} {'enh' if gp['enh'] else ''} wrrel {'on' if gp.get('wrrel', False) else 'off'}")

			hwpart_args += ' ${' + f"hwpart_gp{i}" + '}'

			i += 1

		self.cmd_setenv("hwpart_args", hwpart_args)
		self.cmd_run('mmc hwpartition ${hwpart_args} check')
		self.cmd_run('mmc hwpartition ${hwpart_args} set')
		self.cmd_run('mmc hwpartition ${hwpart_args} complete')
		self.cmd_reset()

task_table = {
"gpt": FastbootTaskGPT,
"run": FastbootTaskRun,
"flash": FastbootTaskFlash,
"virtual-part": FastbootTaskVirtualPart,
"reset": FastbootTaskReset,
"prompt-operator": FastbootTaskPromptOperator,
"emmc-hwpart": FastbootTaskEmmcHwpart,
}

