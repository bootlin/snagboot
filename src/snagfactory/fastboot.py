import os
import sys
import logging
import logging.handlers
from multiprocessing import Process

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

		fb_addr = self.require_global("fb-buffer-addr")
		fb_size = self.require_global("fb-buffer-size")
		self.target_device = self.require_global("target-device")

		self.cmds = [
			f"set fb-addr {fb_addr}",
			f"set fb-size {fb_size}",
			f"set target {self.target_device}",
		]

		if not self.target_device.startswith("mmc"):
			self.eraseblk_size = self.require_global("eraseblk-size")
			self.cmds.append(f"set eraseblk-size {self.eraseblk_size}")

	def require_global(self, var: str):
		if var not in self.globals:
			raise SnagFactoryConfigError(f"Missing '{var}' global parameter!")

		return self.globals[var]

	def get_cmds(self):
		pass

	def cmd_reset(self):
		self.cmds.append("run reset")

	def cmd_run(self, cmd: str):
		self.cmds.append(f"run oem_run:{cmd}")

	def cmd_setenv(self, name: str, value: str):
		self.cmd_run(f"setenv {name} {value}")

	def cmd_setexpr(self, name: str, expr: str):
		self.cmd_run(f"setexpr {name} {expr}")

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
			"fastboot_cmd": [],
			"interactive_cmds": self.cmds,
		}

		self.args = FastbootArgs(args)

	def get_process(self):
		self.process = Process(target=run_fastboot_task, args=(self.args, self.log_queue))
		return self.process

	def flash_partition_images(self):
		part_index = 1

		for partition in self.config:
			if "image" not in partition:
				continue

			if "name" in partition:
				part_name = partition["name"]
			else:
				part_name = f"{part_index}"

			image_offset = partition.get("image-offset", 0)
			image = partition["image"]

			self.cmds.append(f"flash {image} {image_offset} {part_name}")


class FastbootMTDTask(FastbootTask):
	def __init__(self, config: dict, num: int, globals: dict):
		super().__init__(config, num, globals)

		if self.target_device.startswith("mmc"):
			raise SnagFactoryConfigError(f"the '{self.name}' task is only supported on mtd backends")

class FastbootTaskMTDParts(FastbootMTDTask):
	def set_partition_table(self):
		partitions_env = f"mtdparts={self.target_device}:"

		for partition in self.config:
			if "size" not in partition or "name" not in partition:
				raise SnagFactoryConfigError("Invalid partition table entry found in config file, partition size and name must be specified!")

			size = int(partition["size"])
			name = partition["name"]

			if "start" in partition:
				start = int(partition["start"])
				partition_env = f"0x{size:x}@0x{start:x}({name})"
			else:
				partition_env = f"0x{size:x}({name})"

			if "ro" in partition and partition["ro"]:
				partition_env += "ro"

			partitions_env += partition_env + ","

		self.cmd_setenv("mtdparts", partitions_env.rstrip(",") + ";")
		# This does a quick check of the partition layout
		self.cmd_run("mtdparts")

	def get_cmds(self):
		self.set_partition_table()
		self.flash_partition_images()

class FastbootMMCTask(FastbootTask):
	def __init__(self, config: dict, num: int, globals: dict):
		super().__init__(config, num, globals)

		if not self.target_device.startswith("mmc"):
			raise SnagFactoryConfigError(f"the '{self.name}' task is only supported on mmc backends")

		self.device_num = int(self.target_device[-1])

class FastbootTaskGPT(FastbootMMCTask):
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

		self.cmds.append(f"gpt {partitions_env}")

	def get_cmds(self):
		self.flash_partition_table()
		self.flash_partition_images()

class FastbootTaskRun(FastbootTask):
	def get_cmds(self):
		self.cmds += [f"run {cmd}" for cmd in self.config]

class FastbootTaskFlash(FastbootTask):
	def get_cmds(self):
		for entry in self.config:
			part = entry.get("part", "")
			image = entry["image"]
			image_offset = entry.get("image-offset", 0)

			self.cmds.append(f"flash {image} {image_offset} {part}")

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
"mtd-parts": FastbootTaskMTDParts,
"run": FastbootTaskRun,
"flash": FastbootTaskFlash,
"reset": FastbootTaskReset,
"prompt-operator": FastbootTaskPromptOperator,
"emmc-hwpart": FastbootTaskEmmcHwpart,
}

