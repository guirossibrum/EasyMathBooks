import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui

// Same look as qs.Ui.Dropdown, but the menu is an Overlay item in this
// window instead of a QQC Popup. Nested Popups inside the Omarchy
// layer-shell panel swallow the second click on the trigger, so the
// menu never toggles closed.
Item {
  id: root

  property string label: ""
  property string value: ""
  property var options: []

  property color foreground: Color.popups.text
  property color background: Color.popups.background
  property color popupBorder: Color.popups.border
  property color accent: Color.accent
  readonly property var popupBorderSpec: Border.localOrSurfaceSpec("popups", "border", popupBorder, Color.popups.border, Style.normalBorderWidth)
  property string fontFamily: Style.font.family
  property int rowHeight: Style.spacing.controlHeight
  property int popupRowHeight: Style.spacing.popupRowHeight
  property bool showLabel: true
  property bool hasCursor: false

  property bool menuOpen: false
  readonly property bool popupOpen: menuOpen
  function open() { menuOpen = true }
  function close() { menuOpen = false }
  function toggle() { menuOpen = !menuOpen }

  signal changed(string value)
  signal hovered(bool isHovered)

  function optionValue(o) {
    return (o && typeof o === "object") ? String(o.value) : String(o)
  }
  function optionLabel(o) {
    return (o && typeof o === "object") ? String(o.label) : String(o)
  }
  function currentLabel() {
    for (var i = 0; i < options.length; i++) {
      if (optionValue(options[i]) === value) return optionLabel(options[i])
    }
    return value
  }

  implicitWidth: Style.spacing.dropdownWidth
  implicitHeight: showLabel && label !== "" ? rowHeight + Style.spacing.huge : rowHeight

  Column {
    anchors.fill: parent
    spacing: Style.spacing.labelGap

    Text {
      textFormat: Text.PlainText
      visible: root.showLabel && root.label !== ""
      text: root.label
      color: Qt.darker(root.foreground, 1.4)
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: true
    }

    BorderSurface {
      id: trigger
      width: parent.width
      height: root.rowHeight
      radius: Style.cornerRadius

      readonly property bool _focused: trigger.activeFocus
      readonly property bool _hot: triggerHover.hovered || root.hasCursor || root.menuOpen
      readonly property var _borderSpec: Border.controlSpec(_focused ? "focus" : (_hot ? "hover-cursor" : "normal"), root.foreground, root.accent)

      color: Style.controlFill(_focused, _hot, root.foreground, root.accent)
      borderSpec: _borderSpec
      activeFocusOnTab: true

      HoverHandler {
        id: triggerHover
        onHoveredChanged: root.hovered(hovered)
      }

      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
            || event.key === Qt.Key_Space || event.key === Qt.Key_Down) {
          root.toggle(); event.accepted = true
        } else if (event.key === Qt.Key_Escape && root.menuOpen) {
          root.close(); event.accepted = true
        }
      }

      Text {
        textFormat: Text.PlainText
        anchors.left: parent.left
        anchors.right: chevron.left
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: trigger.borderLeft + Style.spacing.controlPaddingX
        anchors.rightMargin: trigger.borderRight + Style.spacing.md
        text: root.currentLabel()
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        elide: Text.ElideRight
      }

      Text {
        id: chevron
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.rightMargin: trigger.borderRight + Style.spacing.controlGap
        text: root.menuOpen ? "󰅃" : "󰅀"
        color: Qt.darker(root.foreground, 1.2)
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
      }

      MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: {
          trigger.forceActiveFocus()
          root.toggle()
        }
      }
    }
  }

  Item {
    id: layer
    parent: root.Overlay.overlay ? root.Overlay.overlay : (root.Window.window ? root.Window.window.contentItem : root)
    visible: root.menuOpen && parent
    anchors.fill: parent
    z: 10000

    MouseArea {
      anchors.fill: parent
      onPressed: function(mouse) {
        var p = menuCard.mapFromItem(layer, mouse.x, mouse.y)
        var onMenu = p.x >= 0 && p.y >= 0 && p.x <= menuCard.width && p.y <= menuCard.height
        var t = trigger.mapFromItem(layer, mouse.x, mouse.y)
        var onTrigger = t.x >= 0 && t.y >= 0 && t.x <= trigger.width && t.y <= trigger.height
        if (onMenu) {
          mouse.accepted = false
          return
        }
        // Overlay sits above the trigger. Close here so the trigger does
        // not also receive the click and reopen.
        root.close()
        mouse.accepted = true
      }
    }

    BorderSurface {
      id: menuCard
      readonly property point origin: {
        if (!root.menuOpen || !layer.parent) return Qt.point(0, 0)
        return trigger.mapToItem(layer.parent, 0, trigger.height + Style.spacing.xxs)
      }
      x: origin.x
      y: origin.y
      width: trigger.width
      implicitHeight: Math.min(
        root.options.length * root.popupRowHeight + Math.max(0, root.options.length - 1) * Style.spacing.labelGap + Style.spacing.xxs,
        root.popupRowHeight * 8 + 7 * Style.spacing.labelGap + Style.spacing.xxs)
      color: root.background
      borderSpec: root.popupBorderSpec
      radius: Style.cornerRadius
      padding: Style.spacing.hairline
      leftPadding: Border.left(root.popupBorderSpec) + Style.spacing.hairline
      rightPadding: Border.right(root.popupBorderSpec) + Style.spacing.hairline
      topPadding: Border.top(root.popupBorderSpec) + Style.spacing.hairline
      bottomPadding: Border.bottom(root.popupBorderSpec) + Style.spacing.hairline

      ListView {
        id: optionList
        anchors.fill: parent
        anchors.topMargin: menuCard.topPadding
        anchors.bottomMargin: menuCard.bottomPadding
        anchors.leftMargin: menuCard.leftPadding
        anchors.rightMargin: menuCard.rightPadding
        spacing: Style.spacing.labelGap
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.options
        currentIndex: {
          for (var i = 0; i < root.options.length; i++)
            if (root.optionValue(root.options[i]) === root.value) return i
          return 0
        }

        function selectCurrent() {
          if (currentIndex < 0 || currentIndex >= root.options.length) return
          var v = root.optionValue(root.options[currentIndex])
          root.value = v
          root.changed(v)
          root.close()
        }

        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Escape) { root.close(); event.accepted = true }
          else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            selectCurrent(); event.accepted = true
          }
        }

        delegate: Rectangle {
          required property var modelData
          required property int index
          width: optionList.width
          height: root.popupRowHeight
          color: index === optionList.currentIndex
            ? Style.hoverFillFor(root.foreground, root.accent)
            : "transparent"

          Text {
            textFormat: Text.PlainText
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: Style.spacing.controlPaddingX
            anchors.rightMargin: Style.spacing.controlPaddingX
            text: root.optionLabel(modelData)
            color: index === optionList.currentIndex ? Style.hoverStateColor(root.foreground, root.accent) : root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            elide: Text.ElideRight
          }

          MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPositionChanged: optionList.currentIndex = parent.index
            onClicked: {
              optionList.currentIndex = parent.index
              optionList.selectCurrent()
            }
          }
        }
      }
    }
  }
}
