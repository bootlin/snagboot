import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Frame {
	id: "root"

	signal log_button_clicked

	Layout.minimumHeight: board_box.height

	Flow {
		id: board_box
		objectName: "board_box"
		property string soc_model
		anchors.margins: 5
		spacing: 10

		Text {
			objectName: "board_path"
			font.pointSize: 12
		}

		Text {
			objectName: "soc_model"
			font.pointSize: 12
		}

		Text {
			objectName: "progress_bar"
			font.pointSize: 12
		}

		Text {
			objectName: "phase"
			font.pointSize: 12
		}

		Text {
			objectName: "status"
			font.pointSize: 12
		}

		Button {
			objectName: "log_button"
			text: "show logs"
			font.pointSize: 12
			font.bold: true
			checkable: true

			onClicked: root.log_button_clicked()
		}
	}
}
