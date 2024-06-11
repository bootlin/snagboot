from kivy.logger import Logger as kivy_logger
kivy_logger.setLevel("WARNING")
from kivy.app import App 
from kivy.uix.widget import Widget
from kivy.properties import (
    NumericProperty, ListProperty, ObjectProperty, StringProperty
)
from kivy.clock import Clock
from kivy.lang import Builder
import kivy.resources

from snagfactory.board import scan_for_boards, BoardPhase
from snagfactory.batch import read_config

import multiprocessing
import logging
import random
import os

import time

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
		self.board.update_state()
		self.phase = self.board.phase.name

		new_status = self.board.get_status()

		if new_status != "" and new_status.levelno > logging.DEBUG:
			print(f"status: {new_status}")
			self.status = new_status.msg

class SnagFactoryUI(Widget):
	widget_container = ObjectProperty(None)
	board_widgets = ListProperty([])
	verbose_log = ObjectProperty(None)
	running = NumericProperty(0)
	status = StringProperty("Scanning for boards...")

	def rescan(self):
		for board_widget in self.board_widgets:
			self.widget_container.remove_widget(board_widget)
			del board_widget

		self.board_widgets = []

		board_list = scan_for_boards(self.batch)

		for board in board_list:
			board_widget = SnagFactoryBoard()
			board_widget.attach_board(board, self)
			self.widget_container.add_widget(board_widget)
			self.board_widgets.append(board_widget)

		self.status = f"{len(self.board_widgets)} boards found"

	def update(self, dt):
		self.update_tick += 1

		if self.running > 0:

			nb_recovering = 0
			nb_flashing = 0
			nb_done = 0
			nb_failed = 0

			for board_widget in self.board_widgets:
				board_widget.update()
				phase = board_widget.board.phase
				if phase in [BoardPhase.FLASHING, BoardPhase.FLASHER]:
					nb_flashing += 1
				elif phase in [BoardPhase.ROM, BoardPhase.RECOVERING]:
					nb_recovering += 1
				elif phase == BoardPhase.DONE:
					nb_done += 1
				else:
					nb_failed += 1

			self.status = f"recovering: {nb_recovering}    flashing: {nb_flashing}    done: {nb_done}    failed: {nb_failed}"

			if self.verbose_log is not None:
				self.log_boxlayout.size_hint_x = 0.5

				board_widget = self.verbose_log
				board = board_widget.board

				self.log_board_path.text = board.path
				self.log_area.text = "\n".join(board.session_log[-LOG_VIEW_CAPACITY:])
		else:
			if self.update_tick % 5 == 0:
				self.rescan()


class SnagFactory(App):
	def build(self):
		batch = read_config("batch.yaml")

		Builder.load_file(os.path.dirname(__file__) + "/gui.kv")

		ui = SnagFactoryUI()
		ui.board_list = []
		ui.update_tick = 0
		ui.batch = batch

		ui.rescan()

		Clock.schedule_interval(ui.update, 1.0 / 2)
		return ui


def main():
	multiprocessing.set_start_method('spawn')
	kivy.resources.resource_add_path(os.path.dirname(__file__) + "/assets")
	SnagFactory().run()

