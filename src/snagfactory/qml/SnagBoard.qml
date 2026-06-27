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
		}

		Text {
			objectName: "soc_model"
		}

		Text {
			objectName: "progress_bar"
		}

		Text {
			objectName: "phase"
		}

		Text {
			objectName: "status"
		}

		Button {
			objectName: "log_button"
			text: "show logs"
			font.bold: true
			checkable: true

			onClicked: root.log_button_clicked()
		}
	}
}
