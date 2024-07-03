from kivy.logger import Logger as kivy_logger
kivy_logger.setLevel("WARNING")
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.properties import (
    ListProperty, ObjectProperty, StringProperty
)
from kivy.clock import Clock
from kivy.lang import Builder
import kivy.resources

from snagfactory.session import SnagFactorySession

import multiprocessing
import logging
factory_logger = logging.getLogger("snagfactory")

import os

LOG_VIEW_CAPACITY = 100

class SnagFactoryBoard(Widget):
	path = StringProperty("")
	soc_model = StringProperty("")
	phase = StringProperty("")
	status = StringProperty("")
	ui = ObjectProperty(None)

	def attach_board(self, board, ui):
		self.board = board

		self.path = board.path
		self.soc_model = board.soc_model
		self.phase = board.phase.name
		self.status = "nothing here for now"
		self.ui = ui

	def update(self):
		self.phase = self.board.phase.name

		new_status = self.board.get_status()

		if new_status != "" and new_status.levelno > logging.DEBUG:
			print(f"status: {new_status}")
			self.status = new_status.msg

class SnagFactoryUI(Widget):
	widget_container = ObjectProperty(None)
	board_widgets = ListProperty([])
	verbose_log = ObjectProperty(None)
	status = StringProperty("Scanning for boards...")
	phase_label = StringProperty("")

	def dismiss_popup(self):
		self._popup.dismiss()

	def open_log_dialog(self):
		content = LoadLogDialog(load_log=self.load_log, cancel_load_log=self.dismiss_popup)
		self._popup = Popup(title="Load file", content=content, size_hint=(0.9, 0.9))
		self._popup.open()

	def load_log(self, path, filename):
		print("WIP")

	def cancel_load_log(self):
		print("WIP")

	def update_board_list(self):
		for board_widget in self.board_widgets:
			self.widget_container.remove_widget(board_widget)

		self.board_widgets = []

		self.session.scan_for_boards()

		for board in self.session.board_list:
			board_widget = SnagFactoryBoard()
			board_widget.attach_board(board, self)
			self.widget_container.add_widget(board_widget)
			self.board_widgets.append(board_widget)

		self.status = f"{len(self.board_widgets)} boards found"

	def start(self):
		self.phase_label = "running batch: batch.yaml"
		self.update_board_list()
		self.session.start()

	def update(self, dt):

		self.session.update()

		if self.session.phase == "scanning":
			self.update_board_list()
		elif self.session.phase == "running":

			for board_widget in self.board_widgets:
				board_widget.update()

			self.status = f"recovering: {self.session.nb_recovering}    flashing: {self.session.nb_flashing}    done: {self.session.nb_done}    failed: {self.session.nb_failed}"

		elif self.session.phase == "logview":
			self.phase_label = "viewing session logs: " + os.path.basename(self.session.logfile_path)
		if self.session.phase != "scanning" and self.verbose_log is not None:
			self.log_boxlayout.size_hint_x = 0.5

			board_widget = self.verbose_log
			board = board_widget.board

			self.log_board_path.text = board.path
			self.log_area.text = "\n".join(board.session_log[-LOG_VIEW_CAPACITY:])

class SnagFactory(App):
	def build(self):
		Builder.load_file(os.path.dirname(__file__) + "/gui.kv")

		session = SnagFactorySession("batch.yaml")
		ui = SnagFactoryUI()
		ui.session = session

		ui.session.update()
		ui.update_board_list()

		Clock.schedule_interval(ui.update, 1.0 / 2)
		return ui


def main():
	multiprocessing.set_start_method('spawn')
	factory_logger.setLevel("INFO")
	kivy.resources.resource_add_path(os.path.dirname(__file__) + "/assets")
	SnagFactory().run()

