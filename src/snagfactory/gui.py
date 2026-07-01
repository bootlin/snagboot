# Check that required PySide6 version is installed
# PySide6 is an optional dependency for snagboot but snagfactory requires it
import sys
import os
import platform
import importlib.metadata
import importlib.resources
import packaging.requirements
import packaging.version

from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtCore import QObject, Slot, QUrl, QTimer
from PySide6.QtQml import QmlElement
from PySide6.QtQuick import QQuickItem
import signal
import functools

QML_IMPORT_NAME = "gui"
QML_IMPORT_MAJOR_VERSION = 1

UI_REFRESH_INTERVAL_MS = 1000 / 8
DEFAULT_SCREEN_DPI = 96

gui_dependencies = (
	importlib.resources.files("snagfactory")
	.joinpath("gui-requirements.txt")
	.read_text()
	.splitlines()
)
gui_reqs = [packaging.requirements.Requirement(req_str) for req_str in gui_dependencies]

for req in gui_reqs:
	dep_error = ""
	try:
		version = importlib.metadata.version(req.name)
		if version not in req.specifier:
			dep_error = (
				f"{req} is required by snagfactory but version {version} is installed"
			)
	except importlib.metadata.PackageNotFoundError:
		dep_error = (
			f"{req} is required by snagfactory but this package is not installed"
		)

	if dep_error != "":
		print(
			"please install the snagboot[gui] package variant to run snagfactory! e.g. pip install snagboot[gui]"
		)
		print(f"underlying cause: {dep_error}")
		sys.exit(1)

import time
import yaml
from math import ceil

from snagfactory.session import SnagFactorySession
from snagfactory.config import SnagFactoryConfigError

import multiprocessing
import logging

factory_logger = logging.getLogger("snagfactory")

LOG_VIEW_CAPACITY = 100
PROGBAR_TICKS = 20


class WidgetFactory:
	instance = None

	def __new__(cls):
		if cls.instance is None:
			cls.instance = super().__new__(cls)
			cls.instance.widgets = {}
			cls.instance.qml_path = str(
				importlib.resources.files("snagfactory").joinpath("qml").resolve()
			)
			cls.instance.components = {}
		return cls.instance

	def set_app(self, app):
		self.app = app
		self.engine = QQmlEngine(self.app)

	def load_component(self, kind: str):
		if kind in self.components:
			raise ValueError(
				f"Component {kind} was already loaded! Was load_component() called twice with the same parameter?"
			)

		component = QQmlComponent(
			self.engine, QUrl.fromLocalFile(os.path.join(self.qml_path, f"{kind}.qml"))
		)
		if component.errors() != []:
			raise ValueError(
				f"Failed to load QML component {kind}! {component.errorString()}"
			)
			self.app.quit()

		self.components[kind] = component

	def spawn(self, parent: QObject, kind: str, properties: dict, top_level=False):
		obj = self.components[kind].createObject(parent, properties=properties)
		if obj is None:
			factory_logger.error(f"Failed to create QML object {kind}!")
			if not top_level:
				self.app.quit()

		return obj

	def cleanup(self):
		self.app = None
		self.components = []
		__class__.instance = None


class SnagBoardHandler:
	def __init__(self, widget, board):
		self.widget = widget
		self.path = ""
		self.soc_model = ""
		self.log = False

		self.progbar = "|" + PROGBAR_TICKS * "-" + "|"

		self.status = ""
		self.spinner_symbols = ["◰", "◳", "◲", "◱"]
		self.spinner_cur = 0
		self.resume_btn = None

		self.board_path = self.widget.findChild(QObject, "board_path")
		self.soc_model = self.widget.findChild(QObject, "soc_model")
		self.progress_bar = self.widget.findChild(QObject, "progress_bar")
		self.phase = self.widget.findChild(QObject, "phase")
		self.status = self.widget.findChild(QObject, "status")
		self.board_box = self.widget.findChild(QObject, "board_box")
		self.log_button = self.widget.findChild(QObject, "log_button")

		self.board = board

		self.board_path.setProperty("text", board.path)
		self.soc_model.setProperty("text", board.soc_model)
		self.phase.setProperty("text", board.phase.name)
		self.phase.setProperty("color", "green")
		self.status.setProperty("text", board.status)
		self.status.setProperty("color", "black")

	def set_log_enabled(self, enabled: bool):
		if enabled != self.log:
			if enabled:
				self.log_button.setProperty("text", "logs displayed")
			else:
				self.log_button.setProperty("text", "show logs")
				self.log_button.setProperty("checked", False)

		self.log = enabled

	def log_was_enabled(self):
		return self.log_button.property("checked") and not self.log

	def set_width(self, width):
		self.board_box.setWidth(width)

	phase_colors = {
		"ROM": "grey",
		"RECOVERING": "darkblue",
		"FLASHER": "blue",
		"FLASHING": "blue",
		"DONE": "green",
		"FAILURE": "red",
		"PAUSED": "orange",
	}

	def unpause(self):
		self.resume_btn.setParentItem(None)
		self.resume_btn = None
		self.board.paused = False
		self.status.setProperty("color", "black")

	def is_paused(self):
		return hasattr(self, "board") and self.board.paused

	def update_ui(self):
		board = self.board

		if self.is_paused() and self.resume_btn is None:
			self.status.setProperty("color", "orange")
			self.resume_btn = WidgetFactory().spawn(
				self.board_box, "SnagUnpauseButton", {}
			)
			self.resume_btn.clicked.connect(self.unpause)

		self.phase.setProperty("text", board.phase.name)
		if board.phase.name in ["FLASHING", "RECOVERING"]:
			self.spinner_cur = (self.spinner_cur + 1) % 4
			self.status.setProperty(
				"text", f"{self.spinner_symbols[self.spinner_cur]} {board.status}"
			)
		else:
			self.status.setProperty("text", board.status)

		self.phase.setProperty("color", __class__.phase_colors[board.phase.name])

		progress = self.board.progress
		num_prog_ticks = ceil(PROGBAR_TICKS * progress / 100)
		self.progress_bar.setProperty(
			"text",
			(
				f"{ceil(progress)}% |"
				+ num_prog_ticks * "#"
				+ (PROGBAR_TICKS - num_prog_ticks) * "—"
				+ "|"
			),
		)


@QmlElement
class SnagBoardListHandler(QQuickItem):
	def __init__(self):
		super().__init__()
		self.log_target = ""
		self.board_handlers = []

	@Slot()
	def cleanup_ui(self):
		self.board_area.widthChanged.disconnect(self.resize_width)

		num_widgets = len(self.board_handlers)
		while num_widgets > 0:
			board_handler = self.board_handlers.pop(-1)

			board_widget = board_handler.widget
			board_widget.log_button_clicked.disconnect(self.log_button_pressed)
			board_widget.setParentItem(None)
			board_widget.setParent(None)

			num_widgets -= 1

	@Slot()
	def resize_width(self):
		new_width = self.board_area.width()
		for board_handler in self.board_handlers:
			board_handler.set_width(new_width)

	@Slot()
	def complete(self):
		self.log_area = self.findChild(QObject, "log_area")
		self.log_target_label = self.findChild(QObject, "log_target_label")
		self.board_area = self.findChild(QObject, "board_area")

		self.board_area.widthChanged.connect(self.resize_width)

	def update_board_widgets(self):
		for board_handler in self.board_handlers:
			board_handler.update_ui()

	def update_board_list(self, session) -> int:
		self.cleanup_ui()

		self.board_area.widthChanged.connect(self.resize_width)

		for board in session.board_list:
			board_widget = WidgetFactory().spawn(self.board_area, "SnagBoard", {})
			board_widget.log_button_clicked.connect(self.log_button_pressed)

			board_handler = SnagBoardHandler(board_widget, board)
			board_handler.set_width(self.board_area.width())
			board_handler.set_log_enabled(False)
			self.board_handlers.append(board_handler)

		self.update_board_widgets()

		return len(self.board_handlers)

	@Slot()
	def log_button_pressed(self):
		for board_handler in self.board_handlers:
			if board_handler.log_was_enabled():
				self.log_target = board_handler.board.path
				board_handler.set_log_enabled(True)
			else:
				board_handler.set_log_enabled(False)

	@Slot()
	def update_verbose_logs(self):
		if self.log_target == "":
			return

		board = None

		for board_handler in self.board_handlers:
			if board_handler.board.path == self.log_target:
				board = board_handler.board
				break

		if board is not None:
			self.log_target_label.setProperty("text", self.log_target)
			self.log_area.setProperty(
				"text", "\n".join(board.session_log[-LOG_VIEW_CAPACITY:])
			)


def sigint_handler(sig, frame, window=None):
	window.close()


class SnagFactoryApp(QGuiApplication):
	def __init__(self):
		super().__init__()

		self.session = SnagFactorySession(None)
		self.phase_text = "standby"
		self.status_text = ""
		self.config_view_items = []

		WidgetFactory().set_app(self)

		WidgetFactory().load_component("SnagMainWindow")
		WidgetFactory().load_component("SnagBoardID")
		WidgetFactory().load_component("SnagTabButton")
		WidgetFactory().load_component("SnagConfigEntry")
		WidgetFactory().load_component("SnagConfigTab")
		WidgetFactory().load_component("SnagConfigField")
		WidgetFactory().load_component("SnagUnpauseButton")
		WidgetFactory().load_component("SnagBoard")

		qml_path = importlib.resources.files("snagfactory").joinpath("qml").resolve()
		self.window = WidgetFactory().spawn(self, "SnagMainWindow", {}, top_level=True)
		self.window.setMinimumWidth(700)
		self.window.setMinimumHeight(500)

		if self.window is None:
			WidgetFactory().cleanup()
			raise ValueError("Failed to create main window!")

		self.lastWindowClosed.connect(self.cleanup)
		signal.signal(
			signal.SIGINT, functools.partial(sigint_handler, window=self.window)
		)

		self.setWindowIcon(QIcon(os.path.join(qml_path, "lab_penguins.ico")))

		self.quit_dialog = self.window.findChild(QObject, "quit_dialog")
		self.error_dialog = self.window.findChild(QObject, "error_dialog")
		self.file_dialog = self.window.findChild(QObject, "file_dialog")
		self.board_list = self.window.findChild(QObject, "board_list")
		self.main_page = self.window.findChild(QObject, "main_page")
		self.start_button = self.window.findChild(QObject, "start_button")
		self.phase_label = self.window.findChild(QObject, "phase_label")
		self.status_label = self.window.findChild(QObject, "status_label")
		self.config_label = self.window.findChild(QObject, "config_label")

		self.start_button.clicked.connect(self.start_button_pressed)
		self.window.findChild(QObject, "logs_button").clicked.connect(
			self.log_button_pressed
		)
		self.window.findChild(QObject, "configs_button").clicked.connect(
			self.configs_button_pressed
		)
		self.window.findChild(QObject, "config_button").clicked.connect(
			self.view_config
		)
		self.window.findChild(QObject, "boards_button").clicked.connect(
			self.view_board_list
		)

		self.refresh_timer = QTimer(self)
		self.refresh_timer.setSingleShot(True)
		self.refresh_timer.timeout.connect(self.update_ui)
		self.refresh_timer.start(UI_REFRESH_INTERVAL_MS)

		self.board_ids_area = self.window.findChild(QObject, "board_ids_area")
		self.soc_families_tab_bar = self.window.findChild(
			QObject, "soc_families_tab_bar"
		)
		self.soc_families_view = self.window.findChild(QObject, "soc_families_view")

		placeholder_item = WidgetFactory().spawn(
			self.board_ids_area, "SnagConfigField", {}
		)
		placeholder_item.findChild(QObject, "field_label").setProperty(
			"text", "No configuration file loaded yet."
		)

		self.config_view_items.append(placeholder_item)

		self.ui_running = True
		self.window.closing.connect(self.stop_ui)
		self.window.confirm_quit.connect(self.confirm_quit)
		self.window.open_file.connect(self.open_file)

		self.window.showMaximized()

	@Slot()
	def start_button_pressed(self):
		self.phase_label_color = "black"

		if self.session.phase == "scanning":
			self.phase_text = "running factory session"
			self.view_board_list()
			self.board_list.update_board_list(self.session)
			self.session.start()
			self.start_button.background_normal = "rescan.png"
			self.start_button.text = "rescan"
		elif self.session.phase == "logview":
			# Keep the same config file and start a new session
			self.phase_label_color = "blue"
			new_session = SnagFactorySession(self.session.config_path)
			self.session = new_session
			self.start_button.background_normal = "start.png"
			self.start_button.text = "start"

	@Slot()
	def view_board_list(self):
		self.main_page.setProperty("currentIndex", 0)

	@Slot()
	def view_config(self):
		self.main_page.setProperty("currentIndex", 1)

	@Slot()
	def update_ui(self):
		last_phase = self.session.phase
		self.session.update()
		self.phase_label_color = "black"

		if self.session.phase == "scanning":
			self.phase_text = "scanning for boards..."
			board_count = self.board_list.update_board_list(self.session)
			self.status_text = f"{board_count} boards found"
		elif self.session.phase == "running":
			ts = time.time()
			self.phase_text = (
				"running factory session... |"
				+ "  " * int(ts % 3)
				+ "=="
				+ "  " * int(3 - (ts % 3))
				+ "|"
			)
			self.status_text = f"recovering: {self.session.nb_recovering}    flashing: {self.session.nb_flashing}    paused: {self.session.nb_paused}    done: {self.session.nb_done}    failed: {self.session.nb_failed}"

			self.board_list.update_board_widgets()

		elif self.session.phase == "logview":
			self.phase_label_color = "blue"
			if last_phase == "running":
				self.board_list.update_board_widgets()

			self.phase_text = "viewing session logs: " + os.path.basename(
				self.session.logfile_path
			)
			self.status_text = f"done: {self.session.nb_done}    failed: {self.session.nb_failed}    other: {self.session.nb_other}"
		else:
			self.phase_text = "standby"

		if self.session.phase != "scanning":
			self.board_list.update_verbose_logs()

		self.phase_label.setProperty("text", self.phase_text)
		self.phase_label.setProperty("color", self.phase_label_color)
		self.status_label.setProperty("text", self.status_text)

		if self.ui_running:
			self.refresh_timer.start(UI_REFRESH_INTERVAL_MS)

	@Slot()
	def log_button_pressed(self):
		self.file_dialog.setProperty("usage", "logs")
		self.file_dialog.setProperty(
			"currentFolder", QUrl.fromLocalFile(self.session.snagfactory_logs)
		)
		self.file_dialog.setProperty("nameFilters", [])
		self.file_dialog.open()

	@Slot()
	def configs_button_pressed(self):
		self.file_dialog.setProperty("usage", "config")

		last_dir = self.session.read_session_store("last_config_dir")
		user_home = os.path.expanduser("~")
		file_path = last_dir if last_dir is not None else user_home
		self.file_dialog.setProperty("currentFolder", QUrl.fromLocalFile(file_path))
		self.file_dialog.setProperty("nameFilters", ["YAML files (*.yml *.yaml)"])
		self.file_dialog.open()

	@Slot()
	def confirm_quit(self):
		self.quit_dialog.setProperty("title", "Quit Snagfactory")
		self.quit_dialog.setProperty(
			"text", "Are you sure you want to close Snagfactory?"
		)
		self.quit_dialog.open()

	@Slot()
	def stop_ui(self):
		self.ui_running = False
		self.refresh_timer.stop()

		timeout = 10
		start = time.monotonic()
		while self.refresh_timer.isActive():
			if time.monotonic() - start > timeout:
				factory_logger.error("Refresh timer did not stop in time!")

			time.sleep(0.5)

		self.board_list.cleanup_ui()

	@Slot()
	def cleanup(self):
		self.window.destroy()
		self.window = None
		WidgetFactory().cleanup()

	@Slot(str, str)
	def open_file(self, file_path, usage):
		if platform.system() == "Windows":
			prefix = "file:///"
		else:
			prefix = "file://"

		if usage == "config":
			self.load_config(file_path.removeprefix(prefix))
		elif usage == "logs":
			self.load_log(file_path.removeprefix(prefix))

	def load_config(self, filename):
		max_error_length = 80

		self.session.write_session_store("last_config_dir", os.path.dirname(filename))
		try:
			session = SnagFactorySession(filename)
		except SnagFactoryConfigError as e:
			self.error_dialog.setProperty("title", "Config error")

			error = str(e)
			if len(error) <= max_error_length - 3:
				self.error_dialog.setProperty("informativeText", error)
				self.error_dialog.setProperty("detailedText", "")
			else:
				self.error_dialog.setProperty(
					"informativeText", error[:max_error_length] + "..."
				)
				self.error_dialog.setProperty("detailedText", error)

			self.error_dialog.open()

			return

		self.session = session

		self.update_config_view(self.session)
		self.config_label.setProperty("text", f"config: {os.path.basename(filename)}")

	def load_log(self, filename):
		self.session = SnagFactorySession(None)
		self.session.load_log(filename)
		self.board_list.update_board_list(self.session)
		self.update_config_view(self.session)
		self.config_label.setProperty("text", "config: none")

	@Slot()
	def cleanup_config_view(self):
		num_widgets = len(self.config_view_items)
		while num_widgets > 0:
			widget = self.config_view_items.pop(-1)
			widget.setParentItem(None)
			widget.setParent(None)
			del widget

			num_widgets -= 1

	def update_config_view(self, session):
		self.cleanup_config_view()

		soc_models = []

		for usb_ids, soc_model in session.config["boards"].items():
			if soc_model not in soc_models:
				soc_models.append(soc_model)

			board_ids_item = WidgetFactory().spawn(
				self.board_ids_area,
				"SnagBoardID",
				{"usb_ids": usb_ids, "soc_model": soc_model},
			)
			self.config_view_items.append(board_ids_item)

		soc_models_config = session.config["soc-models"]
		for soc_model in soc_models:
			# Config validation ensures that these keys exist
			fw_config = soc_models_config[f"{soc_model}-firmware"]
			tasks_config = soc_models_config[f"{soc_model}-tasks"]

			tab_button = WidgetFactory().spawn(
				self.soc_families_tab_bar, "SnagTabButton", {"text": soc_model}
			)
			self.config_view_items.append(tab_button)
			self.create_soc_model_widget(
				self.soc_families_view, soc_model, fw_config, tasks_config
			)

	def create_soc_model_widget(self, parent, soc_model, fw_config, tasks_config):
		soc_model_widget = WidgetFactory().spawn(parent, "SnagConfigEntry", {})
		self.config_view_items.append(soc_model_widget)

		tabs = []
		for key, value in fw_config.items():
			tabs.append((key, yaml.dump(value)))

		globals = {"global variables": tasks_config[0]}

		i = 0
		for config in tasks_config[1:]:
			if "task" in config:
				for key, value in globals["global variables"].items():
					globals["global variables"][key] = (
						hex(value) if isinstance(value, int) else value
					)

				tabs.append(
					(
						f"task #{i}",
						"task: "
						+ config["task"]
						+ "\n\n"
						+ yaml.dump(config.get("args", ""))
						+ yaml.dump(globals),
					)
				)

				i += 1
			else:
				globals["global variables"].update(config)

		for key, value in tabs:
			item = WidgetFactory().spawn(
				soc_model_widget.findChild(QObject, "entry_tab_bar"),
				"SnagConfigTab",
				{"text": key},
			)
			self.config_view_items.append(item)

			item = WidgetFactory().spawn(
				soc_model_widget.findChild(QObject, "entry_field"),
				"SnagConfigField",
				{},
			)
			item.findChild(QObject, "field_label").setProperty("text", value)

			self.config_view_items.append(item)

		return soc_model_widget


def gui():
	multiprocessing.set_start_method("spawn")

	factory_logger.setLevel(logging.INFO)

	stdout_handler = logging.StreamHandler(sys.stdout)
	stdout_handler.setLevel(logging.WARNING)
	factory_logger.addHandler(stdout_handler)

	app = SnagFactoryApp()

	exit_code = app.exec()

	app.shutdown()
	sys.exit(exit_code)


if __name__ == "__main__":
	multiprocessing.freeze_support()
	gui()
