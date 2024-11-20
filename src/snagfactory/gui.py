from kivy.logger import Logger as kivy_logger
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.accordion import AccordionItem
from kivy.uix.button import Button
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.properties import (
    ListProperty, ObjectProperty, StringProperty, ColorProperty
)
from kivy.clock import Clock
from kivy.lang import Builder
import kivy.resources
import time
import yaml
from math import ceil
import sys

from snagfactory.session import SnagFactorySession
from snagfactory.config import SnagFactoryConfigError

import multiprocessing
import logging
factory_logger = logging.getLogger("snagfactory")

import os

LOG_VIEW_CAPACITY = 100
PROGBAR_TICKS = 20

class SnagFactoryPanelItem(TabbedPanelItem):
	content_text = StringProperty("")

class SnagFactoryBoardID(BoxLayout):
	usb_ids = StringProperty("")
	soc_model = StringProperty("")

class SnagFactorySoCFamily(TabbedPanel):
	name = StringProperty("")

	def set_config(self, fw_config: dict, tasks_config: dict):
		tabs = {}

		for key, value in fw_config.items():
			tabs[key] = yaml.dump(value)

		for key, value in tasks_config[0].items():
			tabs[key] = hex(value) if isinstance(value, int) else str(value)

		for config in tasks_config[1:]:
			tabs["task: " + config["task"]] = yaml.dump(config.get("args", ""))

		panel_items = [SnagFactoryPanelItem(text=key, content_text=value) for key,value in tabs.items()]

		for panel_item in panel_items:
			self.add_widget(panel_item)

		self.default_tab = panel_items[0]

class SnagFactoryFileDialog(FloatLayout):
	rootpath = StringProperty("")
	path = StringProperty("")
	sort_func = ObjectProperty(lambda files,fs_class: sorted(files))
	filters = ListProperty([])

	def handle_load(self):
		pass

class SnagFactoryErrorDialog(FloatLayout):
	msg = StringProperty("")
	filepath = StringProperty("")

class SnagFactoryBoard(Widget):
	path = StringProperty("")
	soc_model = StringProperty("")

	phase = StringProperty("")
	phase_color = ListProperty([0,1,0])
	progbar = StringProperty("|" + PROGBAR_TICKS * "-" + "|")
	status = StringProperty("")
	status_color = ListProperty([0,0,0])
	ui = ObjectProperty(None)

	phase_colors = {
		"ROM": [0.8,0.8,0.8],
		"RECOVERING": [0,0.2,0.8],
		"FLASHER": [0,0,1],
		"FLASHING": [0,0,1],
		"DONE": [0,1,0],
		"FAILURE": [1,0,0],
		"PAUSED": [1,0.5,0.5],
	}

	def show_verbose_log(self, btn):
		if self.ui.verbose_log_target == self.board.path:
			btn.background_color = [0.6, 0.76, 1]
			btn.text = "show logs"
			self.ui.hide_verbose_logs()
		else:
			btn.background_color = [0.3, 0.45, 1]
			btn.text = "hide logs"
			self.ui.verbose_log_target = self.board.path

	def attach_board(self, board, ui):
		self.board = board

		self.path = board.path
		self.soc_model = board.soc_model
		self.phase = board.phase.name
		self.status = ""
		self.ui = ui
		self.spinner_symbols = ["\\","-","/","|"]
		self.spinner_cur = 0
		self.resume_btn = None

	def unpause(self, event):
		self.board.paused = False
		self.board_box.remove_widget(self.resume_btn)
		self.resume_btn = None
		self.status_color = [0, 0, 0]

	def is_paused(self):
		return hasattr(self, "board") and self.board.paused

	def update(self):
		if self.is_paused() and self.resume_btn is None:
			self.status_color = [1, 0.5, 0.5]
			self.resume_btn = Button(text="resume",on_press=self.unpause, background_normal="", background_color=(0,1,0), size_hint_x=0.2)
			self.board_box.add_widget(self.resume_btn)

		self.status = self.board.status
		self.phase = self.board.phase.name
		if self.phase in ["FLASHING", "RECOVERING"]:
			self.spinner_cur = (self.spinner_cur + 1) % 4
			self.status = f"[{self.spinner_symbols[self.spinner_cur]}] " + self.status

		self.phase_color = __class__.phase_colors[self.phase]

		progress = self.board.progress
		num_prog_ticks = ceil(PROGBAR_TICKS * progress / 100)
		self.progbar = f"{ceil(progress)}% |" + num_prog_ticks * "#" + (PROGBAR_TICKS - num_prog_ticks) * "—" + "|"

class SnagFactoryUI(Widget):
	widget_container = ObjectProperty(None)
	board_widgets = ListProperty([])
	status = StringProperty("Scanning for boards...")
	phase_label = StringProperty("")
	phase_label_color = ColorProperty((0, 0, 0))

	def __init__(self, session):
		super().__init__()
		self.session = session
		self.session.update()
		self.verbose_log_target = None
		self.update_board_list()

	def view_board_list(self):
		self.main_page.page = 0

	def view_config(self):
		self.main_page.page = 1

	def dismiss_popup(self):
		self._popup.dismiss()

	def open_config_dialog(self):
		if self.session.phase == "running":
			return

		last_dir = self.session.read_session_store("last_config_dir")

		content = SnagFactoryFileDialog()
		content.rootpath = os.path.expanduser("~")
		content.path = last_dir if last_dir is not None else content.rootpath
		content.handle_load = self.load_config
		content.filters = ["*.yaml", "*.yml"]
		self._popup = Popup(title="Load file", content=content, size_hint=(0.9, 0.9))
		self._popup.open()

	def open_log_dialog(self):
		if self.session.phase == "running":
			return

		content = SnagFactoryFileDialog()
		content.rootpath = self.session.snagfactory_logs
		content.handle_load = self.load_log
		content.sort_func = lambda files,fs_class: sorted(files, reverse=True)
		self._popup = Popup(title="Load file", content=content, size_hint=(0.9, 0.9))
		self._popup.open()

	def load_config(self, filenames):
		try:
			session = SnagFactorySession(filenames[0])
			session.write_session_store("last_config_dir", os.path.dirname(filenames[0]))
		except SnagFactoryConfigError as e:
			self.dismiss_popup()

			content = SnagFactoryErrorDialog(filepath=filenames[0], msg=str(e))
			self._popup = Popup(title="Config error", content=content, size_hint=(0.7,0.7))
			self._popup.open()

			return

		self.session = session

		self.update_config_view()

		self.dismiss_popup()

	def load_log(self, filenames):
		if filenames == []:
			return

		self.session = SnagFactorySession(None)
		self.session.load_log(filenames[0])
		self.update_board_list()
		self.update_config_view()
		self.dismiss_popup()

	def update_config_view(self):
		soc_families_view = self.session_config.soc_families_view
		board_ids_view = self.session_config.board_ids_view

		board_ids_items = [widget for widget in board_ids_view.children if isinstance(widget, SnagFactoryBoardID)]
		for board_ids_item in board_ids_items:
			board_ids_view.remove_widget(board_ids_item)

		accordion_items = list(soc_families_view.children)
		for accordion_item in accordion_items:
			soc_families_view.remove_widget(accordion_item)

		for usb_ids,soc_model in self.session.config["boards"].items():
			board_ids_item = SnagFactoryBoardID(usb_ids=usb_ids, soc_model=soc_model)
			board_ids_view.add_widget(board_ids_item)

		for name,config in self.session.config["soc-models"].items():
			soc_model,sep,suffix = name.partition("-")

			if suffix == "firmware":
				continue

			fw_config = self.session.config["soc-models"][f"{soc_model}-firmware"]
			tasks_config = config

			accordion_item = AccordionItem(title=soc_model)
			soc_model_widget = SnagFactorySoCFamily(name=soc_model)
			soc_model_widget.set_config(fw_config, tasks_config)
			accordion_item.add_widget(soc_model_widget)
			soc_families_view.add_widget(accordion_item)

	def update_board_list(self):
		for board_widget in self.board_widgets:
			self.widget_container.remove_widget(board_widget)

		self.board_widgets = []

		self.session.update()

		for board in self.session.board_list:
			board_widget = SnagFactoryBoard()
			board_widget.attach_board(board, self)
			self.widget_container.add_widget(board_widget)
			self.board_widgets.append(board_widget)

		for board_widget in self.board_widgets:
			board_widget.update()

	def hide_verbose_logs(self):
		self.verbose_log_target = None
		self.log_area.text = ""
		self.log_boxlayout.size_hint_x = 0

	def start(self, btn):
		self.phase_label_color = (0, 0, 0)

		if self.session.phase == "scanning":
			self.phase_label = "running factory session"
			self.view_board_list()
			self.update_board_list()
			self.session.start()
			btn.background_normal = "rescan.png"
			btn.text = "rescan"
		elif self.session.phase == "logview":
			# Keep the same config file and start a new session
			self.phase_label_color = (0, 0, 1)
			new_session = SnagFactorySession(self.session.config_path)
			self.session = new_session
			btn.background_normal = "start.png"
			btn.text = "start"

	def update(self, dt):
		last_phase = self.session.phase
		self.session.update()
		self.phase_label_color = (0, 0, 0)

		if self.session.phase == "scanning":
			self.phase_label = ""
			self.update_board_list()
			self.status = f"{len(self.board_widgets)} boards found"
			self.hide_verbose_logs()
		elif self.session.phase == "running":
			ts = time.time()
			self.phase_label = "running factory session... |" + "  " * int(ts % 3) + "==" + "  " * int(3 - (ts % 3))  + "|"
			self.status = f"recovering: {self.session.nb_recovering}    flashing: {self.session.nb_flashing}    paused: {self.session.nb_paused}    done: {self.session.nb_done}    failed: {self.session.nb_failed}"

			for board_widget in self.board_widgets:
				board_widget.update()

		elif self.session.phase == "logview":
			self.phase_label_color = (0, 0, 1)
			if last_phase == "running":
				for board_widget in self.board_widgets:
					board_widget.update()

			self.phase_label = "viewing session logs: " + os.path.basename(self.session.logfile_path)
			self.status = f"done: {self.session.nb_done}    failed: {self.session.nb_failed}    other: {self.session.nb_other}"

		if self.session.phase != "scanning" and self.verbose_log_target is not None:

			self.log_boxlayout.size_hint_x = 0.5

			log_target = None
			for board_widget in self.board_widgets:
				if board_widget.board.path == self.verbose_log_target:
					log_target = board_widget.board
					break

			if log_target is not None:
				self.log_board_path.text = self.verbose_log_target
				self.log_area.text = "\n".join(log_target.session_log[-LOG_VIEW_CAPACITY:])


class SnagFactory(App):
	def call_ui(self, method: str, *args):
		if self.ui is None:
			return

		getattr(self.ui, method)(*args)

	def build(self):
		self.icon = os.path.dirname(__file__) + "/assets/lab_penguins.png"
		Builder.load_file(os.path.dirname(__file__) + "/gui.kv")
		Builder.load_file(os.path.dirname(__file__) + "/config.kv")

		session = SnagFactorySession(None)
		self.ui = SnagFactoryUI(session)

		Clock.schedule_interval(self.ui.update, 1.0 / 8)

		return self.ui


def main():
	multiprocessing.set_start_method('spawn')

	factory_logger.setLevel("INFO")
	kivy_logger.parent = factory_logger

	stdout_handler = logging.StreamHandler(sys.stdout)
	stdout_handler.setLevel(logging.WARNING)
	factory_logger.addHandler(stdout_handler)

	kivy.resources.resource_add_path(os.path.dirname(__file__) + "/assets")
	SnagFactory().run()

