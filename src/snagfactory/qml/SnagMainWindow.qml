import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import gui

ApplicationWindow {
	id: main_window
	visible: true
	title: "Snagfactory"
	color: "white"
	header: toolbar
	footer: status_bar

	signal confirm_quit
	signal open_file(string file, string usage)

	Shortcut {
		sequences: [StandardKey.Quit, StandardKey.Close]
		onActivated: main_window.confirm_quit()
	}

	MessageDialog {
		objectName: "quit_dialog"
		visible: false

		buttons: MessageDialog.Ok | MessageDialog.Cancel
		onAccepted: main_window.close()
	}

	MessageDialog {
		objectName: "error_dialog"
		visible: false
	}

	FileDialog {
		objectName: "file_dialog"
		visible: false
		property string usage: ""

		onAccepted: main_window.open_file(selectedFile, usage)
	}

	ToolBar {
		id: toolbar

		ButtonGroup {
			id: main_view_toggle
		}

		RowLayout {
			ToolButton {
				objectName: "start_button"
				text: "Start"

				ToolTip.delay: 800
				ToolTip.visible: hovered
				ToolTip.text: "Start/stop factory session"

				onClicked: boards_btn.click()
			}

			ToolButton {
				objectName: "configs_button"
				text: "Config"

				ToolTip.delay: 800
				ToolTip.visible: hovered
				ToolTip.text: "Load configuration"
			}

			ToolButton {
				objectName: "logs_button"
				text: "Logs"

				ToolTip.delay: 800
				ToolTip.visible: hovered
				ToolTip.text: "Load logs"
			}

			ToolSeparator {
			}

			Label {
				objectName: "config_label"
				text: "config: none"
				color: "darkgrey"
			}

			ToolSeparator {
			}

			ToolButton {
				id: boards_btn
				text: "Boards"

				ButtonGroup.group: main_view_toggle
				checkable: true
				checked: true
				onClicked: stack.pop()

				ToolTip.delay: 800
				ToolTip.visible: hovered
				ToolTip.text: "View board list"
			}

			ToolButton {
				text: "Config"

				ButtonGroup.group: main_view_toggle
				checkable: true
				onClicked: stack.push(config_view)

				ToolTip.delay: 800
				ToolTip.visible: hovered
				ToolTip.text: "View current configuration"
			}
		}
	}

	StackView {
		id: stack
		initialItem: board_view
		anchors.fill: parent
	}

	SnagBoardList {
		id: board_view
	}

	ColumnLayout {
		id: config_view
		visible: false

		ColumnLayout {
			objectName: "board_ids_area"
			Layout.preferredWidth: parent.width

			Label {
				text: "USB targets"
				font.pointSize: 15
			}
		}

		TabBar {
			id: tab_bar
			objectName: "soc_families_tab_bar"
			Layout.preferredWidth: parent.width
		}

		StackLayout {
			objectName: "soc_families_view"
			Layout.fillHeight: true
			Layout.preferredWidth: parent.width
			currentIndex: tab_bar.currentIndex
		}
	}

	Frame {
		id: status_bar

		Label {
			objectName: "status_label"
			text: "standby"
		}
	}
}
