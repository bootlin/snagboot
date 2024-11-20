import yaml
import datetime
import time
import os
import platform
import queue
import re
import copy

import logging
factory_logger = logging.getLogger("snagfactory")

import snagrecover
from snagfactory.config import read_config
from snagfactory.board import Board, BoardPhase

import snagrecover.utils


log_header = """
snagfactory session {}
summary: {} done {} failed {} other
config:
{}
results:
{}
"""

default_config = {
"boards": {},
"soc-models": {},
}

class SnagFactorySession():
	MAX_LOG_SIZE = 1000

	def update(self):
		# Main state machine for factory session

		if self.phase == "scanning":
			if self.scan_tick == 0:
				self.scan_for_boards()

			self.scan_tick = (self.scan_tick + 1) % 8

		if self.phase == "running":
			self.nb_recovering = 0
			self.nb_flashing = 0
			self.nb_done = 0
			self.nb_failed = 0
			self.nb_paused = 0

			for board in self.board_list:
				board.update_state()

				phase = board.phase
				if phase in [BoardPhase.FLASHING, BoardPhase.FLASHER]:
					self.nb_flashing += 1
				elif phase in [BoardPhase.ROM, BoardPhase.RECOVERING]:
					self.nb_recovering += 1
				elif phase == BoardPhase.DONE:
					self.nb_done += 1
				elif phase == BoardPhase.PAUSED:
					self.nb_paused += 1
				else:
					self.nb_failed += 1

			if self.nb_recovering == 0 and self.nb_flashing == 0 and self.nb_paused == 0:
				self.nb_other = len(self.board_list) - self.nb_done - self.nb_failed
				self.close()

	def read_session_store(self, key: str):
		snagfactory_sessionstore = self.snagboot_data + "/snagfactory/sessionstore.yaml"

		if not os.path.exists(snagfactory_sessionstore):
			return None

		with open(snagfactory_sessionstore, "r") as file:
			session_store = yaml.safe_load(file)

		return session_store.get(key, None)

	def write_session_store(self, key: str, value):
		snagfactory_sessionstore = self.snagboot_data + "/snagfactory/sessionstore.yaml"

		session_store = {}

		if os.path.exists(snagfactory_sessionstore):
			with open(snagfactory_sessionstore, "r") as file:
				session_store = yaml.safe_load(file)

		session_store[key] = value

		with open(snagfactory_sessionstore, "w") as file:
			yaml.dump(session_store, file, default_flow_style=False)

	def __init__(self, config_path):
		self.config_path = config_path
		self.start_ts = time.time()
		self.scan_tick = 0

		if config_path is None:
			self.config = default_config
		else:
			self.config,self.pipelines = read_config(config_path)

		self.board_list = self.scan_for_boards()
		self.phase = "scanning"

		if platform.system() == "Windows":
			snagboot_data = os.getenv('APPDATA') + "/snagboot"
		else:
			snagboot_data = os.getenv('HOME') + "/.snagboot}"

		self.snagboot_data = snagboot_data
		self.snagfactory_logs = self.snagboot_data + "/snagfactory/logs"
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
		self.save_log()

	def scan_for_boards(self):
		self.board_list = []
		for (usb_ids, soc_model) in self.config["boards"].items():
			paths = snagrecover.utils.usb_addr_to_path(usb_ids, find_all=True)

			if paths is None:
				continue

			for path in paths:
				fw_config = self.config["soc-models"][f"{soc_model}-firmware"]
				tasks_config = self.config["soc-models"][f"{soc_model}-tasks"]
				board_pipeline = copy.deepcopy(self.pipelines[soc_model])
				self.board_list.append(Board(snagrecover.utils.prettify_usb_addr(path), soc_model, fw_config, tasks_config, usb_ids, board_pipeline))

	def format_session_logs(self):
		timestamp = datetime.datetime.fromtimestamp(self.start_ts)
		timezone = datetime.datetime.now().astimezone().tzname()

		board_list = self.board_list

		board_statuses = "\n".join([f"{board.usb_ids} at {board.path}: {board.phase.name}" for board in board_list])

		config = yaml.dump(self.config)

		header = log_header.format( \
		f"{timestamp.isoformat()} ({timezone})", \
		self.nb_done, self.nb_failed, self.nb_other, \
		"\t" + "\n\t".join(config.splitlines()), \
		board_statuses)

		session_log = "\nFACTORY LOG:\n\n"

		while not self.session_log.empty():
				session_log += "\n" + self.session_log.get().msg

		board_logs = ""

		for board in board_list:
			board_logs += f"\n\nBOARD LOG {board.path}:\n\n" + "\n".join(board.session_log)

		return header + session_log + board_logs

	def load_log_section(self, marker: str, logs: list):
		factory_logger.info(f"marker {marker}: logs {logs}")
		if marker == "summary:":
			pattern = re.compile("summary: (\d+) done (\d+) failed (\d+) other")
			match = pattern.match(logs[0])
			self.nb_done = int(match.groups()[0])
			self.nb_failed = int(match.groups()[1])
			self.nb_other = int(match.groups()[2])
		elif marker == "config:":
			# remove leading tab from each line
			config_yaml = "\n".join([line[1:] for line in logs[1:]])
			self.config = yaml.safe_load(config_yaml)
			print(self.config)
		elif marker == "results:":
			pattern = re.compile("([\w:]+) at ([\d\-\.]+): (\w+)")
			for log in logs[1:-1]:
				match = pattern.match(log)
				usb_ids = match.groups()[0]
				path = match.groups()[1]
				phase = BoardPhase[match.groups()[2]]
				soc_model = self.config["boards"][usb_ids]
				fw_config = self.config["soc-models"][f"{soc_model}-firmware"]
				tasks_config = self.config["soc-models"][f"{soc_model}-tasks"]
				mock_board = Board(path, soc_model, fw_config, tasks_config, usb_ids, [])
				mock_board.phase = phase
				self.board_dict[path] = mock_board
		elif marker == "BOARD LOG":
			pattern = re.compile("BOARD LOG ([\d\-\.]+):")
			match = pattern.match(logs[0])
			path = match.groups()[0]
			if path not in self.board_dict:
				raise KeyError(f"Log parsing error, no board with path {path} found in 'results' section")
			mock_board = self.board_dict[path]
			mock_board.session_log = logs[1:]

	def load_log(self, logfile_path):
		self.phase = "logview"
		self.logfile_path = logfile_path
		markers = ["summary:", "config:", "results:", "FACTORY LOG:", "BOARD LOG"]

		self.board_dict = {}

		with open(self.logfile_path, "r") as logfile:
			cur = []
			cur_marker = ""
			next_marker = markers[0]

			for line in logfile:
				if line.startswith(next_marker):
					self.load_log_section(cur_marker, cur)

					if markers != []:
						cur_marker = markers.pop(0)
						next_marker = markers[0] if markers != [] else cur_marker

					cur = [line]
				else:
					cur.append(line)

			self.load_log_section(cur_marker, cur)

			self.board_list = list(self.board_dict.values())


	def save_log(self):
		session_logs = self.format_session_logs()

		self.logfile_path = self.snagfactory_logs + "/" + datetime.datetime.fromtimestamp(self.start_ts).strftime("%y-%m-%dT%H-%M-%S")
		if os.path.exists(self.logfile_path):
			raise SystemError(f"logfile {self.logfile_path} already exists!")

		with open(self.logfile_path, "w") as logfile:
			logfile.write(session_logs)

		print(f"Session logs have been written to {self.logfile_path}")
