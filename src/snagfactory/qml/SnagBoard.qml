import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Frame {
	id: "root"

	signal log_button_clicked

	Flow {
		id: board_box
		objectName: "board_box"
		property string soc_model
		anchors.margins: 5
		spacing: 10

		Text {
			objectName: "board_path"
			font.pointSize: 14
		}

		Text {
			objectName: "soc_model"
			font.pointSize: 14
		}

		Text {
			objectName: "progress_bar"
			font.pointSize: 14
		}

		Text {
			objectName: "phase"
			font.pointSize: 14
		}

		Text {
			objectName: "status"
			font.pointSize: 14
		}

		Button {
			objectName: "log_button"
			text: "show logs"
			font.pointSize: 14
			font.bold: true
			checkable: true

			onClicked: root.log_button_clicked()
		}
	}
}
