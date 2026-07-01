import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
	property string usb_ids: ""
	property string soc_model: ""

	Label {
		text: parent.usb_ids
		font.pointSize: 12
	}

	Label {
		text: "->"
		font.pointSize: 12
	}

	Label {
		text: parent.soc_model
		font.pointSize: 12
	}
}
