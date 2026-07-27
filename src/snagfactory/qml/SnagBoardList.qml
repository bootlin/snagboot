import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import gui

SnagBoardListHandler {
	id: board_list_handler
	objectName: "board_list"
	property string log_target: ""

	ColumnLayout {
		anchors.fill: parent

		Frame {
			Layout.preferredWidth: parent.width

			Text {
				objectName: "board_status_label"
				font.pointSize: 15
			}
		}

		SplitView {
			Layout.fillHeight: true
			Layout.preferredWidth: parent.width
			handle: Rectangle {
				implicitWidth: 4
				implicitHeight: 4
				color: "darkgrey"
			}

			ScrollView {
				objectName: "board_area"
				contentWidth: availableWidth
				SplitView.minimumWidth: boards_area_title.width
				SplitView.fillWidth: true

				ColumnLayout {
					Text {
						id: boards_area_title
						text: "Scanned boards"
						font.pointSize: 14
					}

					ColumnLayout {
						objectName: "board_layout"
					}
				}
			}

			Pane {
				id: log_pane
				SplitView.minimumWidth: log_area_title.width
				SplitView.preferredWidth: 300

				ColumnLayout {
					height: parent.height

					Label {
						id: log_area_title
						text: "Detailed logs"
						font.pointSize: 14
					}

					Label {
						objectName: "log_target_label"
						text: ""
						font.pointSize: 12
					}

					ScrollView {
						contentWidth: availableWidth
						ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
						Layout.fillHeight: true
						Layout.preferredWidth: log_pane.width

						Text {
							objectName: "log_area"
							width: log_pane.width
							wrapMode: Text.WordWrap
							font.pointSize: 14
						}
					}
				}
			}
		}
	}

	Component.onCompleted: board_list_handler.complete()
}
