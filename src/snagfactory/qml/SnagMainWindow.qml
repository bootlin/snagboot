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

	SnagToolbar {
		id: toolbar
		Layout.minimumWidth: parent.width
	}

	StackLayout {
		objectName: "main_page"

		width: parent.width - 5
		height: parent.height
		x: parent.x + 5

		ColumnLayout {
			Layout.minimumWidth: parent.width
			Layout.minimumHeight: parent.height

			Text {
				objectName: "phase_label"
				Layout.preferredWidth: parent.width
				text: "standby"
				font.pointSize: 15
			}

			Text {
				objectName: "status_label"
				Layout.preferredWidth: parent.width
				font.pointSize: 15
			}

			SnagBoardList {
				Layout.preferredWidth: parent.width
				Layout.fillHeight: true
			}
		}

		ColumnLayout {
            		objectName: "config_view"
			Layout.minimumWidth: parent.width
			Layout.minimumHeight: parent.height

			ColumnLayout {
				width: parent.width
				objectName: "board_ids_area"

				Label {
					text: "USB targets"
				}
			}

			TabBar {
				id: tab_bar
				objectName: "soc_families_tab_bar"
			}

			StackLayout {
            			objectName: "soc_families_view"
				Layout.fillHeight: true
				currentIndex: tab_bar.currentIndex
			}
		}
	}
}
