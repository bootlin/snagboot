import yaml
import datetime
import time
import os
import platform
import queue

import logging
factory_logger = logging.getLogger("snagfactory")

import snagrecover
from snagfactory.batch import read_config
from snagfactory.board import Board, BoardPhase

import snagrecover.utils


log_header = """
snagfactory session {}
summary: {} done {} failed {} other
batch:
{}
results:
{}
"""

class SnagFactorySession():
	MAX_LOG_SIZE = 1000

	def update(self):
		# Main state machine for factory session

		if self.phase == "running":
			self.nb_recovering = 0
			self.nb_flashing = 0
			self.nb_done = 0
			self.nb_failed = 0

			for board in self.board_list:
				board.update_state()

				phase = board.phase
				if phase in [BoardPhase.FLASHING, BoardPhase.FLASHER]:
					self.nb_flashing += 1
				elif phase in [BoardPhase.ROM, BoardPhase.RECOVERING]:
					self.nb_recovering += 1
				elif phase == BoardPhase.DONE:
					self.nb_done += 1
				else:
					self.nb_failed += 1

				if self.nb_recovering == 0 and self.nb_flashing == 0:
					self.close()

	def __init__(self, batch_path: str):
		self.start_ts = time.time()
		self.batch = read_config(batch_path)
		self.board_list = self.scan_for_boards()
		self.phase = "scanning"

		if platform.system() == "Windows":
			snagboot_data = os.getenv('APPDATA') + "/snagboot"
		else:
			snagboot_data = os.getenv('HOME') + "/.snagboot}"

		self.snagfactory_logs = snagboot_data + "/snagfactory/logs"
		if not os.path.exists(self.snagfactory_logs):
			os.makedirs(self.snagfactory_logs)


	def start(self):
		if self.phase != "scanning":
			return

		self.session_log = queue.Queue(__class__.MAX_LOG_SIZE)
		log_handler = logging.handlers.QueueHandler(self.session_log)
		log_formatter = logging.Formatter("%(asctime)s,%(msecs)03d [%(levelname)-8s] %(message)s", datefmt="%H:%M:%S")
		log_handler.setFormatter(log_formatter)
		factory_logger.addHandler(log_handler)
		factory_logger.info("Start")

		self.phase = "running"

	def close(self):
		self.phase = "logview"
		self.save()

	def scan_for_boards(self):
		self.board_list = []
		for (usb_id, soc_model) in self.batch["boards"].items():
			paths = snagrecover.utils.parse_usb_addr(usb_id, find_all=True)

			if paths is None:
				continue

			for path in paths:
				self.board_list.append(Board(snagrecover.utils.prettify_usb_addr(path), soc_model, self.batch["soc_families"][soc_model]))

	def format_session_logs(self):
		timestamp = datetime.datetime.fromtimestamp(self.start_ts)
		timezone = datetime.datetime.now().astimezone().tzname()

		board_list = self.board_list

		board_statuses = "\n".join([f"{board.path}: {board.phase.name}" for board in board_list])

		batch = yaml.dump(self.batch)

		header = log_header.format( \
		f"{timestamp.isoformat()} ({timezone})", \
		self.nb_done, self.nb_failed, (len(board_list) - self.nb_done - self.nb_failed), \
		"\t" + "\n\t".join(batch.splitlines()), \
		board_statuses)

		session_log = "\nFACTORY LOG:\n\n"

		while not self.session_log.empty():
				session_log += "\n" + self.session_log.get().msg

		board_logs = ""

		for board in board_list:
			board_logs += f"\n\nBOARD LOG {board.path}\n\n" + "\n".join(board.session_log)

		return header + session_log + board_logs

	def save(self):
		session_logs = self.format_session_logs()

		self.logfile_path = self.snagfactory_logs + "/" + datetime.datetime.fromtimestamp(self.start_ts).strftime("%y-%m-%dT%H-%M-%S")
		if os.path.exists(self.logfile_path):
			raise SystemError(f"logfile {self.logfile_path} already exists!")

		with open(self.logfile_path, "w") as logfile:
			logfile.write(session_logs)

		print(f"Session logs have been written to {self.logfile_path}")
