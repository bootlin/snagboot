import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import gui

ToolBar {
	ButtonGroup {
		id: main_view_toggle
	}

	RowLayout {
		anchors.fill: parent

		ToolButton {
			objectName: "start_button"

			height: parent.height
			Layout.alignment: Qt.AlignLeft
			Layout.minimumWidth: 30

			display: AbstractButton.IconOnly
			icon.source: "start.png"
			icon.width: Layout.minimumWidth
			icon.height: parent.height
			icon.color: "transparent"

			ToolTip.delay: 800
			ToolTip.visible: hovered
			ToolTip.text: "Start/stop factory session"
		}

		ToolSeparator {
		}

		ToolButton {
			objectName: "configs_button"

			height: parent.height
			Layout.alignment: Qt.AlignLeft
			Layout.minimumWidth: 30
			background.implicitHeight: parent.height

			display: AbstractButton.IconOnly
			icon.source: "load_config.png"
			icon.width: Layout.minimumWidth
			icon.height: parent.height
			icon.color: "transparent"

			ToolTip.delay: 800
			ToolTip.visible: hovered
			ToolTip.text: "Load configuration"
		}

		ToolSeparator {
		}

		ToolButton {
			objectName: "logs_button"

			height: parent.height
			Layout.alignment: Qt.AlignLeft
			Layout.minimumWidth: 30
			background.implicitHeight: parent.height

			display: AbstractButton.IconOnly
			icon.source: "view_logs.png"
			icon.width: Layout.minimumWidth
			icon.height: parent.height
			icon.color: "transparent"

			ToolTip.delay: 800
			ToolTip.visible: hovered
			ToolTip.text: "Load logs"
		}

		ToolSeparator {
		}

		Label {
			objectName: "config_label"
			text: "config: none"
		}

		ToolSeparator {
		}

		ToolButton {
			objectName: "boards_button"
			display: AbstractButton.IconOnly
			icon.source: "boards.png"
			icon.width: Layout.minimumWidth
			icon.height: parent.height
			icon.color: "transparent"

			height: parent.height
			Layout.alignment: Qt.AlignLeft
			Layout.minimumWidth: 30
			background.implicitHeight: parent.height

			ButtonGroup.group: main_view_toggle
			checkable: true

			ToolTip.delay: 800
			ToolTip.visible: hovered
			ToolTip.text: "View board list"
		}

		ToolButton {
			objectName: "config_button"
			display: AbstractButton.IconOnly
			icon.source: "config.png"
			icon.width: Layout.minimumWidth
			icon.height: parent.height
			icon.color: "transparent"

			height: parent.height
			Layout.alignment: Qt.AlignLeft
			Layout.minimumWidth: 30
			background.implicitHeight: parent.height

			ButtonGroup.group: main_view_toggle
			checkable: true

			ToolTip.delay: 800
			ToolTip.visible: hovered
			ToolTip.text: "View loaded configuration"
		}

		Label {
			text: ""

			Layout.fillWidth: true
		}
	}
}
