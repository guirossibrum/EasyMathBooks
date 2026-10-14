import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "grbrum.easymath"
  ipcTarget: "grbrum.easymath"
  manageIpc: false

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color accent: Color.accent
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string cli: String(Qt.resolvedUrl("bin/easymath-cli")).replace(/^file:\/\//, "")

  property var snap: ({})
  property string lastError: ""
  property string lastMessage: ""
  property bool busy: false
  property string pendingCmd: ""
  property var pendingPayload: ({})
  property int activeTab: 0
  property string studentId: ""
  property string levelValue: "1"
  property int seedValue: 1
  property string paperValue: "letter"
  property bool examplesOn: true
  property bool answersOn: true
  property string newStudentName: ""
  property string notesText: ""
  property int scoreValue: 0
  property bool timerOn: false
  property double timerBase: 0
  property double timerStarted: 0
  property double nowMs: Date.now()
  property string confirmKind: ""
  property int confirmSessionId: 0
  property string codeDraft: ""

  readonly property var tabs: [
    { name: "Sheet", icon: "󰃬" },
    { name: "Students", icon: "󰀉" },
    { name: "Progress", icon: "󰄨" }
  ]
  readonly property var settings: snap.settings || ({})
  readonly property var students: snap.students || []
  readonly property var levels: snap.levels || []
  readonly property var sessions: snap.sessions || []
  readonly property var stats: snap.stats || []
  readonly property int problemCount: Number(snap.problem_count || 0)
  readonly property string sheetCode: String(levelValue || "1") + "-" + String(seedValue || 1)
  readonly property var lastSheet: snap.last_sheet || null
  readonly property string pdfPath: lastSheet && lastSheet.pdf_path ? String(lastSheet.pdf_path) : (snap.generated && snap.generated.pdf_path ? String(snap.generated.pdf_path) : "")
  readonly property string answersPath: lastSheet && lastSheet.answers_path ? String(lastSheet.answers_path) : (snap.generated && snap.generated.answers_path ? String(snap.generated.answers_path) : "")
  readonly property int elapsedSec: Math.max(0, Math.floor(((timerOn ? nowMs - timerStarted : 0) + timerBase) / 1000))

  readonly property var studentOptions: {
    var out = [{ value: "", label: "Blank name line" }]
    for (var i = 0; i < students.length; i++)
      out.push({ value: String(students[i].id), label: String(students[i].name) })
    return out
  }
  readonly property var levelOptions: {
    var out = []
    for (var i = 0; i < levels.length; i++) {
      var lv = levels[i]
      out.push({ value: String(lv.num), label: String(lv.num) + "  " + String(lv.title || "") })
    }
    return out
  }
  readonly property var paperOptions: [
    { value: "letter", label: "Letter" },
    { value: "a4", label: "A4" }
  ]

  function pad(n) { return n < 10 ? "0" + n : String(n) }

  function formatDuration(seconds) {
    seconds = Math.max(0, Math.floor(Number(seconds) || 0))
    var m = Math.floor(seconds / 60)
    var s = seconds % 60
    var h = Math.floor(m / 60)
    m = m % 60
    if (h > 0) return h + ":" + pad(m) + ":" + pad(s)
    return m + ":" + pad(s)
  }

  function parseCode(text) {
    var m = String(text || "").trim().match(/^(\d+)\s*-\s*(\d+)$/)
    if (!m) return null
    var level = Number(m[1])
    var seed = Number(m[2])
    if (!(level >= 1) || !(seed >= 1)) return null
    return { level: level, seed: seed }
  }

  function applyCode(text) {
    var parsed = parseCode(text)
    if (!parsed) {
      lastError = "Sheet code looks like 1-502 (level-seed)."
      return
    }
    levelValue = String(parsed.level)
    seedValue = parsed.seed
    codeDraft = sheetCode
    lastError = ""
    refresh()
  }

  function selectionPayload() {
    return {
      student_id: studentId === "" ? "" : Number(studentId),
      level: Number(levelValue),
      variant: Number(seedValue),
      paper: paperValue,
      examples: examplesOn,
      answers: answersOn
    }
  }

  function run(cmd, payload) {
    if (busy) {
      pendingCmd = cmd
      pendingPayload = payload || ({})
      return
    }
    lastError = ""
    busy = true
    helper.command = [root.cli, cmd, JSON.stringify(payload || ({}))]
    helper.running = true
  }

  function scheduleRefresh() { snapWait.restart() }

  function refresh() { run("snapshot", selectionPayload()) }

  function generateSheet() { run("generate", selectionPayload()) }

  function openPath(path) {
    if (!path) {
      lastError = "Create the worksheet first."
      return
    }
    Quickshell.execDetached(["xdg-open", path])
  }

  function applySnap(data) {
    snap = data
    var s = data.settings || ({})
    if (s.student_id === null || s.student_id === undefined || s.student_id === "")
      studentId = ""
    else
      studentId = String(s.student_id)
    if (s.level) levelValue = String(s.level)
    if (s.variant) seedValue = Math.max(1, Number(s.variant))
    if (s.paper) paperValue = String(s.paper)
    if (s.examples !== undefined) examplesOn = !!s.examples
    if (s.answers !== undefined) answersOn = !!s.answers
    codeDraft = String(levelValue) + "-" + String(seedValue)
    if (data.generated && data.generated.pdf_path) {
      lastMessage = "Wrote " + data.generated.code + " · " + data.generated.problem_count + " problems"
      openPath(data.generated.pdf_path)
    }
    if (data.saved) {
      lastMessage = "Saved " + data.saved.sheet_code + " in " + formatDuration(data.saved.duration_seconds)
      resetTimer()
    }
  }

  function addStudent() {
    var name = String(newStudentName || "").trim()
    if (!name) {
      lastError = "Type a student name."
      return
    }
    run("add-student", { name: name })
    newStudentName = ""
  }

  function deleteCurrentStudent() {
    if (studentId === "") return
    confirmKind = "student"
  }

  function savePractice() {
    var payload = selectionPayload()
    payload.duration_seconds = elapsedSec
    payload.score = scoreValue
    payload.score_max = problemCount
    payload.notes = notesText
    payload.taken_at = snap.today || ""
    run("save-session", payload)
  }

  function startTimer() {
    if (timerOn) return
    timerStarted = Date.now()
    timerOn = true
  }

  function pauseTimer() {
    if (!timerOn) return
    timerBase += Date.now() - timerStarted
    timerOn = false
  }

  function resetTimer() {
    timerOn = false
    timerBase = 0
    timerStarted = 0
  }

  function toggleTimer() {
    if (timerOn) pauseTimer()
    else startTimer()
  }

  function scoreLabel(row) {
    if (row.score === null || row.score === undefined) return "—"
    if (row.score_max === null || row.score_max === undefined) return String(row.score)
    return row.score + " / " + row.score_max
  }

  function trendLabel(stat) {
    var first = stat && stat.first ? Number(stat.first.duration_seconds) : 0
    var last = stat && stat.last ? Number(stat.last.duration_seconds) : 0
    if (!(first > 0) || !(last > 0) || first === last) return "steady"
    return last < first ? "faster" : "slower"
  }

  onOpenedChanged: if (opened) {
    lastError = ""
    refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  Component.onCompleted: refresh()

  Timer {
    interval: 200
    running: root.opened && root.timerOn
    repeat: true
    onTriggered: root.nowMs = Date.now()
  }

  Timer {
    id: snapWait
    interval: 250
    repeat: false
    onTriggered: root.refresh()
  }

  Process {
    id: helper
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.busy = false
        var data = null
        try { data = JSON.parse(String(text || "").trim() || "{}") }
        catch (e) { root.lastError = "Could not read EasyMathBooks helper output."; return }
        if (!data.ok) {
          root.lastError = String(data.error || "That did not work.")
        } else {
          root.applySnap(data)
        }
        if (root.pendingCmd !== "") {
          var cmd = root.pendingCmd
          var payload = root.pendingPayload
          root.pendingCmd = ""
          root.pendingPayload = ({})
          root.run(cmd, payload)
        }
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text.trim() !== "") console.warn("easymath", text.trim())
    }
  }

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { root.refresh(); return "ok" }
    function tab(name: string): string {
      var n = String(name || "").toLowerCase()
      if (n === "sheet" || n === "0") root.activeTab = 0
      else if (n === "students" || n === "1") root.activeTab = 1
      else if (n === "progress" || n === "2") root.activeTab = 2
      root.open()
      return String(root.activeTab)
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰃬"
    tooltipText: "Easy Math Books — " + root.sheetCode
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) root.generateSheet()
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(520))
    contentHeight: panel.fittedContentHeight(Style.space(640))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: root.confirmKind !== ""

      onCloseRequested: {
        if (root.confirmKind !== "") root.confirmKind = ""
        else root.close()
      }
      onMoveRequested: function(dx, dy) {
        if (dx !== 0)
          root.activeTab = (root.activeTab + dx + root.tabs.length) % root.tabs.length
      }
      onActivateRequested: root.generateSheet()
      onTextKey: function(t) {
        if (t === "g" || t === "G") root.generateSheet()
        else if (t === " ") root.toggleTimer()
        else if (t === "s" || t === "S") root.savePractice()
        else if (t >= "1" && t <= String(root.tabs.length)) root.activeTab = parseInt(t) - 1
      }

      Column {
        anchors.fill: parent
        spacing: Style.space(10)

        PanelHero {
          width: parent.width
          title: "Easy Math Books"
          meta: root.busy ? "Working…" : (root.lastMessage !== "" ? root.lastMessage : "One page · sheet " + root.sheetCode)
          detail: root.sheetCode
          foreground: root.foreground
          fontFamily: root.fontFamily
          iconComponent: Component {
            Text {
              textFormat: Text.PlainText
              text: "󰃬"
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.display
            }
          }
        }

        Text {
          visible: root.lastError !== ""
          width: parent.width
          textFormat: Text.PlainText
          text: root.lastError
          color: root.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        Row {
          id: tabRow
          width: parent.width
          spacing: Style.space(4)
          readonly property real tabWidth: (width - spacing * (root.tabs.length - 1)) / root.tabs.length
          Repeater {
            model: root.tabs
            Button {
              required property var modelData
              required property int index
              width: tabRow.tabWidth
              iconText: modelData.icon
              text: modelData.name
              fontSize: Style.font.caption
              foreground: root.foreground
              fontFamily: root.fontFamily
              selected: root.activeTab === index
              bordered: true
              horizontalPadding: Style.space(2)
              verticalPadding: Style.space(5)
              onClicked: root.activeTab = index
            }
          }
        }

        PanelSeparator { foreground: root.foreground }

        Flickable {
          width: parent.width
          height: Math.max(80, parent.height - y)
          contentWidth: width
          contentHeight: tabLoader.implicitHeight
          clip: true
          boundsBehavior: Flickable.StopAtBounds
          flickableDirection: Flickable.VerticalFlick
          ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

          Loader {
            id: tabLoader
            width: parent.width
            sourceComponent: root.activeTab === 1 ? studentsTab : (root.activeTab === 2 ? progressTab : sheetTab)
          }
        }
      }

      ConfirmDialog {
        anchors.fill: parent
        opened: root.confirmKind !== ""
        message: root.confirmKind === "student"
          ? "Delete this student and their sessions?"
          : "Delete this practice session?"
        confirmText: "Delete"
        foreground: root.foreground
        background: Color.popups.background
        fontFamily: root.fontFamily
        onCanceled: root.confirmKind = ""
        onConfirmed: {
          if (root.confirmKind === "student")
            root.run("delete-student", { student_id: Number(root.studentId) })
          else if (root.confirmKind === "session")
            root.run("delete-session", { session_id: root.confirmSessionId })
          root.confirmKind = ""
        }
      }
    }
  }

  Component {
    id: sheetTab
    Column {
      width: tabLoader.width
      spacing: Style.space(12)

      AppDropdown {
        id: studentDrop
        width: parent.width
        label: "Student"
        value: root.studentId
        options: root.studentOptions
        foreground: root.foreground
        fontFamily: root.fontFamily
        onChanged: function(v) {
          root.studentId = v
          root.refresh()
        }
      }

      AppSearchableDropdown {
        id: levelDrop
        width: parent.width
        label: "Level"
        value: root.levelValue
        options: root.levelOptions
        placeholderText: "Search levels"
        foreground: root.foreground
        fontFamily: root.fontFamily
        onChanged: function(v) {
          root.levelValue = v
          root.codeDraft = root.sheetCode
          root.scheduleRefresh()
        }
      }

      Row {
        width: parent.width
        spacing: Style.space(10)

        NumberField {
          id: seedField
          label: "Seed"
          value: root.seedValue
          from: 1
          to: 2147483646
          stepSize: 1
          fieldWidth: Style.space(140)
          foreground: root.foreground
          fontFamily: root.fontFamily
          onModified: function(v) {
            root.seedValue = Math.max(1, v)
            root.codeDraft = root.sheetCode
            root.scheduleRefresh()
          }
        }

        Column {
          width: parent.width - seedField.implicitWidth - parent.spacing
          spacing: Style.spacing.labelGap

          Text {
            textFormat: Text.PlainText
            text: "Sheet code"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }

          TextField {
            id: codeField
            width: parent.width
            text: root.codeDraft
            placeholderText: "1-502"
            foreground: root.foreground
            onEditingFinished: root.applyCode(text)
            onAccepted: root.applyCode(text)
          }
        }
      }

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: "Any seed reprints the same one-page sheet. 1-1, 1-2, and 1-502 are three different level-1 worksheets."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      ButtonGroup {
        width: parent.width
        options: root.paperOptions
        value: root.paperValue
        foreground: root.foreground
        fontFamily: root.fontFamily
        onChanged: function(v) {
          root.paperValue = v
          root.refresh()
        }
      }

      Toggle {
        width: parent.width
        label: "Note box and hint digits"
        description: "Worked example on vertical sheets."
        checked: root.examplesOn
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: {
          root.examplesOn = !root.examplesOn
          root.refresh()
        }
      }

      Toggle {
        width: parent.width
        label: "Answer key PDF"
        checked: root.answersOn
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: {
          root.answersOn = !root.answersOn
          root.refresh()
        }
      }

      Row {
        spacing: Style.space(8)
        Button {
          text: root.busy ? "Creating…" : "Create worksheet"
          iconText: "󰈟"
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          enabled: !root.busy
          onClicked: root.generateSheet()
        }
        Button {
          text: "Open"
          enabled: root.pdfPath !== ""
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.openPath(root.pdfPath)
        }
        Button {
          text: "Answers"
          enabled: root.answersPath !== ""
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.openPath(root.answersPath)
        }
      }

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: root.problemCount + " problems on one page"
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      PanelSeparator { foreground: root.foreground }

      PanelSectionHeader {
        text: "Practice session"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Text {
        textFormat: Text.PlainText
        text: root.formatDuration(root.elapsedSec)
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.display
        font.bold: true
      }

      Row {
        spacing: Style.space(8)
        Button {
          text: root.timerOn ? "Pause" : "Start"
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.toggleTimer()
        }
        Button {
          text: "Reset"
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.resetTimer()
        }
      }

      Row {
        spacing: Style.space(10)
        NumberField {
          id: scoreField
          label: "Score"
          value: root.scoreValue
          from: 0
          to: Math.max(1, root.problemCount)
          fieldWidth: Style.space(100)
          foreground: root.foreground
          fontFamily: root.fontFamily
          onModified: function(v) { root.scoreValue = v }
        }
        Text {
          anchors.bottom: parent.bottom
          anchors.bottomMargin: Style.space(10)
          textFormat: Text.PlainText
          text: "/ " + root.problemCount
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }
      }

      TextField {
        id: notesField
        width: parent.width
        placeholderText: "Notes"
        text: root.notesText
        foreground: root.foreground
        onEditingFinished: root.notesText = text
      }

      Button {
        text: "Save session"
        iconText: "󰄬"
        bordered: true
        enabled: root.studentId !== "" && !root.busy
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.savePractice()
      }

      Text {
        visible: root.studentId === ""
        width: parent.width
        textFormat: Text.PlainText
        text: "Pick a student to save time and score."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }
    }
  }

  Component {
    id: studentsTab
    Column {
      width: tabLoader.width
      spacing: Style.space(12)

      PanelSectionHeader {
        text: "Students"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Row {
        width: parent.width
        spacing: Style.space(8)
        TextField {
          id: nameField
          width: parent.width - addBtn.implicitWidth - parent.spacing
          placeholderText: "New student name"
          text: root.newStudentName
          foreground: root.foreground
          onEditingFinished: root.newStudentName = text
          onAccepted: {
            root.newStudentName = text
            root.addStudent()
          }
        }
        Button {
          id: addBtn
          text: "Add"
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: {
            root.newStudentName = nameField.text
            root.addStudent()
          }
        }
      }

      Repeater {
        model: root.students
        delegate: BorderSurface {
          required property var modelData
          width: parent.width
          implicitHeight: Style.space(44)
          radius: Style.cornerRadius
          color: String(modelData.id) === root.studentId ? Style.selectedFillFor(root.foreground, root.accent) : "transparent"
          borderSpec: Border.controlSpec("normal", root.foreground, root.accent)

          MouseArea {
            anchors.fill: parent
            onClicked: {
              root.studentId = String(modelData.id)
              root.activeTab = 0
              root.refresh()
            }
          }

          Text {
            anchors.left: parent.left
            anchors.leftMargin: Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: modelData.name
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
          }

          PanelActionButton {
            anchors.right: parent.right
            anchors.rightMargin: Style.space(8)
            anchors.verticalCenter: parent.verticalCenter
            iconText: "󰧧"
            tooltipText: "Delete"
            foreground: root.foreground
            hoverColor: root.urgent
            fontFamily: root.fontFamily
            onClicked: {
              root.studentId = String(modelData.id)
              root.confirmKind = "student"
            }
          }
        }
      }

      Text {
        visible: root.students.length === 0
        width: parent.width
        textFormat: Text.PlainText
        text: "Add a student to record times and follow progress."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }
    }
  }

  Component {
    id: progressTab
    Column {
      width: tabLoader.width
      spacing: Style.space(12)

      PanelSectionHeader {
        text: root.studentId === "" ? "All sessions" : "Development"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Repeater {
        model: root.stats
        delegate: Column {
          required property var modelData
          width: parent.width
          spacing: Style.space(2)
          Text {
            width: parent.width
            textFormat: Text.PlainText
            text: "Level " + modelData.level + " · " + modelData.sessions + " sessions · best "
              + root.formatDuration(modelData.best_seconds)
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            font.bold: true
          }
          Text {
            width: parent.width
            textFormat: Text.PlainText
            text: modelData.last
              ? "Last " + modelData.last.sheet_code + " in " + root.formatDuration(modelData.last.duration_seconds)
                + " · " + root.trendLabel(modelData)
              : ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }

      PanelSeparator { visible: root.sessions.length > 0; foreground: root.foreground }

      Repeater {
        model: root.sessions
        delegate: Item {
          required property var modelData
          width: parent.width
          implicitHeight: Style.space(48)

          Column {
            anchors.left: parent.left
            anchors.right: delBtn.left
            anchors.rightMargin: Style.space(8)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(2)
            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: modelData.taken_at + "  " + modelData.sheet_code
                + (root.studentId === "" ? "  " + modelData.student_name : "")
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              elide: Text.ElideRight
            }
            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: root.formatDuration(modelData.duration_seconds) + " · " + root.scoreLabel(modelData)
                + (modelData.notes ? " · " + modelData.notes : "")
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }
          }

          PanelActionButton {
            id: delBtn
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            iconText: "󰧧"
            tooltipText: "Delete session"
            foreground: root.foreground
            hoverColor: root.urgent
            fontFamily: root.fontFamily
            onClicked: {
              root.confirmSessionId = Number(modelData.id)
              root.confirmKind = "session"
            }
          }
        }
      }

      Text {
        visible: root.sessions.length === 0
        width: parent.width
        textFormat: Text.PlainText
        text: "Saved practice times show up here."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }
    }
  }
}
