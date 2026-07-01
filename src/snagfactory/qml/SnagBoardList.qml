import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import gui

SnagBoardListHandler {
	id: board_list_handler
	objectName: "board_list"
	property string log_target: ""

	SplitView {
		anchors.fill: parent

		ScrollView {
			SplitView.minimumWidth: boards_area_title.width
			SplitView.minimumHeight: parent.height
			SplitView.preferredWidth: parent.width * 0.5

			contentWidth: availableWidth

			ColumnLayout {
				width: parent.width

				Text {
					id: boards_area_title
					text: "Scanned boards"
					font.pointSize: 14
				}

				ColumnLayout {
					id: board_area
					objectName: "board_area"
					width: parent.width - 5
				}
			}
		}

		ColumnLayout {
			property string board_path: ""
			SplitView.minimumHeight: parent.height
			SplitView.minimumWidth: log_area_title.width
			SplitView.fillWidth: true

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
				Layout.fillHeight: true
				width: parent.width

				contentWidth: availableWidth

				Text {
					objectName: "log_area"
					width: parent.width - 5
					wrapMode: Text.WordWrap
					font.pointSize: 12
				}
			}
		}
	}

	Component.onCompleted: board_list_handler.complete()
}
