import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import gui

ColumnLayout {
	TabBar {
		width: parent.width
		objectName: "entry_tab_bar"
		id: bar
	}

	StackLayout {
		width: parent.width
		objectName: "entry_field"
		currentIndex: bar.currentIndex
	}
}
