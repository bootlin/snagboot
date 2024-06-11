from snagrecover.utils import get_family
from multiprocessing import Process, Queue, Lock
import uuid
from snagflash.fastboot import fastboot
from snagrecover.utils import prettify_usb_addr, parse_usb_path
import sys
import os
import os.path
import snagrecover
import time
import logging
import logging.handlers
import random
from enum import Enum

MAX_LOG_RECORDS = 15000

class BoardPhase(Enum):
	FAILURE = -1
	ROM=0
	RECOVERING=1
	FLASHER=2
	FLASHING=3
	DONE=4

class Board():

	def __init__(self, usb_path: str, soc_model: str, config: dict):
		self.path = usb_path
		self.soc_model = soc_model
		self.soc_family = get_family(soc_model)
		self.task = None
		self.phase = BoardPhase.ROM
		self.firmware = config["firmware"]
		self.images = config["images"]
		self.uid = uuid.uuid4()

		self.log_queue = Queue(MAX_LOG_RECORDS)
		self.last_log = Queue(1)
		self.session_log = []



	def get_status(self):
		if not self.last_log.empty():
			return self.last_log.get()
		return ""

	def update_state(self):
		phase = self.phase
		print(self.uid, phase)

		# empty log queues or tasks can deadlock
		while not self.log_queue.empty():
			self.session_log.append(self.log_queue.get().msg)

		if phase == BoardPhase.ROM:
			config = get_recovery_config(self)
			self.task = Process(target=run_recovery, args=(config, self.soc_family, self.log_queue, self.last_log))
			self.task.start()
			self.phase = BoardPhase.RECOVERING
		elif phase == BoardPhase.FLASHER:
			args = get_fastboot_args(self)
			self.task = Process(target=run_flasher, args=(args, self.soc_family, self.log_queue, self.last_log))
			self.task.start()
			self.phase = BoardPhase.FLASHING
		elif phase in [BoardPhase.RECOVERING, BoardPhase.FLASHING]:
			exitcode = self.task.exitcode

			if exitcode == 0:
				self.task.join()
				if self.phase == BoardPhase.RECOVERING:
					self.phase = BoardPhase.FLASHER
				else:
					self.phase = BoardPhase.DONE
			elif (exitcode is not None and exitcode < 0) or not self.task.is_alive():
				self.phase = BoardPhase.FAILURE

		elif phase == BoardPhase.FAILURE:
			pass
		elif phase == BoardPhase.DONE:
			pass
		else:
			pass

class FastbootArgs:
	def __init__(self, d):
		for key, value in d.items():
			setattr(self, key, value)

def get_fastboot_args(board):
	images = board.images
	args = {
		"loglevel": "info",
		"timeout": 60000,
		"port": board.path,
		"fastboot_cmd": [],
	}

	for (target, image) in images.items():
		print(target, image)
		args["fastboot_cmd"] += [
			f"download:{image}",
			f"flash:{target}",
		]

	return FastbootArgs(args)

def get_recovery_config(board):
	return {
		"soc_model": board.soc_model,
		"soc_family": board.soc_family,
		"usb_path": parse_usb_path(board.path),
		"firmware": board.firmware,
		"loglevel": "info",
	}

def run_recovery(config, soc_family, log_queue, last_log):
	sys.stdout = open(os.devnull, "w")
	sys.stderr = open(os.devnull, "w")

	import snagrecover.config

	snagrecover.config.recovery_config = config
	logger = logging.getLogger("snagrecover")
	logger.propagate = False
	logger.handlers.clear()
	log_handler = logging.handlers.QueueHandler(log_queue)
	status_handler = logging.handlers.QueueHandler(last_log)
	logger.addHandler(log_handler)
	logger.addHandler(status_handler)
	logger.setLevel(logging.INFO)

	recovery = snagrecover.utils.get_recovery(soc_family)

	try:
		recovery()
	except Exception as e:
		logger.error(f"Caught exception from snagrecover: {e}")
		sys.exit(-1)

	logger.handlers.clear()

def run_flasher(args, soc_family, log_queue, last_log):
	sys.stdout = open(os.devnull, 'w')
	sys.stderr = open(os.devnull, 'w')

	logger = logging.getLogger("snagflash")
	snagrecover_logger = logging.getLogger("snagrecover")
	snagrecover_logger.parent = logger

	logger.propagate = False
	logger.handlers.clear()
	log_handler = logging.handlers.QueueHandler(log_queue)
	status_handler = logging.handlers.QueueHandler(last_log)
	logger.addHandler(log_handler)
	logger.addHandler(status_handler)
	logger.setLevel(logging.INFO)

	try:
		fastboot(args)
	except Exception as e:
		logger.error(f"Caught exception from snagflash: {e}")
		sys.exit(-1)

	logger.handlers.clear()

def scan_for_boards(batch):
	board_list = []
	for (usb_id, soc_model) in batch["boards"].items():
		paths = snagrecover.utils.parse_usb_addr(usb_id, find_all=True)

		if paths is None:
			continue

		for path in paths:
			board_list.append(Board(prettify_usb_addr(path), soc_model, batch["soc_families"][soc_model]))

	return board_list

