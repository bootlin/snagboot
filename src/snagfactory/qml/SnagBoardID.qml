import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
	property string usb_ids: ""
	property string soc_model: ""

	Label {
		text: parent.usb_ids
	}

	Label {
		text: "->"
	}

	Label {
		text: parent.soc_model
	}
}
