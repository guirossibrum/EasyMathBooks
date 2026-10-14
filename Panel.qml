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
  property bool hydrated: false

  readonly property var tabs: [
    { name: "Sheet", icon: "󰃬" },
    { name: "Practice", icon: "󰔟" },
    { name: "Students", icon: "󰀉" },
    { name: "Progress", icon: "󰄨" }
  ]
  readonly property var settings: snap.settings || ({})
  readonly property var students: snap.students || []
  readonly property var levels: snap.levels || []
  readonly property var sessions: snap.sessions || []
  readonly property var stats: snap.stats || []
  readonly property var report: snap.report || ({ has_data: false })
  readonly property int problemCount: Number(snap.problem_count || 0)
  readonly property string sheetCode: String(levelValue || "1") + "-" + String(seedValue || 1)
  readonly property var lastSheet: snap.last_sheet || null
  readonly property string pdfPath: lastSheet && lastSheet.pdf_path ? String(lastSheet.pdf_path) : (snap.generated && snap.generated.pdf_path ? String(snap.generated.pdf_path) : "")
  readonly property string answersPath: lastSheet && lastSheet.answers_path ? String(lastSheet.answers_path) : (snap.generated && snap.generated.answers_path ? String(snap.generated.answers_path) : "")
  readonly property int elapsedSec: Math.max(0, Math.floor(((timerOn ? nowMs - timerStarted : 0) + timerBase) / 1000))
  readonly property int elapsedMin: Math.floor(elapsedSec / 60)
  readonly property int elapsedSecPart: elapsedSec % 60
  readonly property string studentName: {
    if (studentId === "") return ""
    for (var i = 0; i < students.length; i++) {
      if (String(students[i].id) === studentId) return String(students[i].name)
    }
    return ""
  }

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

  function refresh() { run("snapshot", hydrated ? selectionPayload() : ({})) }

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
    hydrated = true
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
        + " · " + data.saved.score + " / " + data.saved.score_max + " correct"
      resetTimer()
      scoreValue = 0
      notesText = ""
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

  function spinValue(field, fallback) {
    if (!field || !field.field) return fallback
    var spin = field.field
    var raw = String(spin.displayText || "")
    var n = parseInt(raw, 10)
    if (!isFinite(n)) n = Number(spin.value)
    if (!isFinite(n)) return fallback
    return n
  }

  function savePractice() {
    var payload = selectionPayload()
    payload.duration_seconds = elapsedSec
    payload.score = scoreValue
    payload.score_max = Math.max(problemCount, scoreValue)
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

  function setManualMinutes(minutes) {
    if (timerOn) pauseTimer()
    var m = Math.max(0, Number(minutes) || 0)
    var s = elapsedSec % 60
    timerBase = (m * 60 + s) * 1000
    nowMs = Date.now()
  }

  function setManualSeconds(seconds) {
    if (timerOn) pauseTimer()
    var m = Math.floor(elapsedSec / 60)
    var s = Math.max(0, Math.min(59, Number(seconds) || 0))
    timerBase = (m * 60 + s) * 1000
    nowMs = Date.now()
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

  function perExerciseLabel(row) {
    var n = Number(row && row.score_max)
    var s = Number(row && row.duration_seconds)
    if (!(n > 0) || !isFinite(s)) return ""
    var each = s / n
    var label
    if (each >= 60) label = formatDuration(Math.round(each)) + " / exercise"
    else if (Math.abs(each - Math.round(each)) < 0.05) label = Math.round(each) + "s / exercise"
    else label = each.toFixed(1) + "s / exercise"
    return " · " + label
  }

  function pctLabel(value) {
    if (value === null || value === undefined) return "—"
    var n = Number(value)
    if (!isFinite(n)) return "—"
    if (n === Math.round(n)) return Math.round(n) + "%"
    return n.toFixed(1) + "%"
  }

  function levelTitle(num) {
    for (var i = 0; i < levels.length; i++) {
      if (Number(levels[i].num) === Number(num)) return String(levels[i].title || "")
    }
    return ""
  }

  readonly property var reportCardItems: [
    {
      label: "Today",
      value: String(report.today_count || 0),
      detail: "sheets"
    },
    {
      label: "This week",
      value: String(report.week_count || 0),
      detail: report.week_skipped
        ? (report.week_skipped + (Number(report.week_skipped) === 1 ? " day skipped" : " days skipped"))
        : "this week"
    },
    {
      label: "Correct",
      value: pctLabel(report.accuracy_pct),
      detail: report.possible ? (report.correct + " / " + report.possible) : "no scores yet"
    },
    {
      label: "Streak",
      value: String(report.streak || 0),
      detail: Number(report.streak) === 1 ? "day" : "days"
    }
  ]

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
      else if (n === "practice" || n === "1") root.activeTab = 1
      else if (n === "students" || n === "2") root.activeTab = 2
      else if (n === "progress" || n === "3") root.activeTab = 3
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
            sourceComponent: root.activeTab === 1 ? practiceTab
              : (root.activeTab === 2 ? studentsTab
                : (root.activeTab === 3 ? progressTab : sheetTab))
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
          text: "Exercise"
          enabled: root.pdfPath !== ""
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.openPath(root.pdfPath)
        }
        Button {
          visible: root.answersOn
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

      Button {
        text: root.timerOn ? "Practice · " + root.formatDuration(root.elapsedSec) : "Time this sheet"
        iconText: "󰔟"
        bordered: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.activeTab = 1
      }
    }
  }

  Component {
    id: practiceTab
    Column {
      width: tabLoader.width
      spacing: Style.space(12)

      PanelSectionHeader {
        text: "Practice session"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      AppDropdown {
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

      Column {
        width: parent.width
        spacing: Style.spacing.labelGap
        Text {
          textFormat: Text.PlainText
          text: "Sheet"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
        }
        TextField {
          width: parent.width
          placeholderText: "2-2"
          text: root.codeDraft
          foreground: root.foreground
          onEditingFinished: root.applyCode(text)
          onAccepted: root.applyCode(text)
        }
      }

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: root.problemCount + " problems · start the timer, or type minutes and seconds after they finish."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
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
          iconText: root.timerOn ? "󰏤" : "󰐊"
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
        width: parent.width
        spacing: Style.space(10)

        NumberField {
          id: minutesField
          label: "Minutes"
          value: root.elapsedMin
          from: 0
          to: 599
          stepSize: 1
          fieldWidth: Style.space(110)
          foreground: root.foreground
          fontFamily: root.fontFamily
          onModified: function(v) { root.setManualMinutes(v) }
        }

        NumberField {
          id: secondsField
          label: "Seconds"
          value: root.elapsedSecPart
          from: 0
          to: 59
          stepSize: 1
          fieldWidth: Style.space(110)
          foreground: root.foreground
          fontFamily: root.fontFamily
          onModified: function(v) { root.setManualSeconds(v) }
        }
      }

      Row {
        spacing: Style.space(10)
        NumberField {
          id: scoreField
          label: "Correct"
          value: root.scoreValue
          from: 0
          to: Math.max(1, root.problemCount)
          fieldWidth: Style.space(110)
          foreground: root.foreground
          fontFamily: root.fontFamily
          onModified: function(v) { root.scoreValue = v }
        }
        Text {
          anchors.bottom: parent.bottom
          anchors.bottomMargin: Style.space(10)
          textFormat: Text.PlainText
          text: "/ " + root.problemCount + " problems"
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
        onClicked: {
          root.setManualMinutes(root.spinValue(minutesField, root.elapsedMin))
          root.setManualSeconds(root.spinValue(secondsField, root.elapsedSecPart))
          root.scoreValue = Math.max(0, root.spinValue(scoreField, root.scoreValue))
          root.notesText = notesField.text
          root.savePractice()
        }
      }

      Text {
        visible: root.studentId === ""
        width: parent.width
        textFormat: Text.PlainText
        text: "Pick a student to save time and how many were correct."
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
              root.activeTab = 3
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
        text: root.studentName !== "" ? root.studentName : "Progress"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      AppDropdown {
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

      Text {
        visible: root.studentId === ""
        width: parent.width
        textFormat: Text.PlainText
        text: "Pick a student to see sheets per day, skipped days, accuracy, and how times drop on each level."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Text {
        visible: root.studentId !== "" && !root.report.has_data
        width: parent.width
        textFormat: Text.PlainText
        text: "Save a practice session to see statistics."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Column {
        visible: root.report.has_data
        width: parent.width
        spacing: Style.space(12)

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: root.report.headline || ""
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        Row {
          id: cardRow
          width: parent.width
          spacing: Style.space(8)
          Repeater {
            model: root.reportCardItems
            BorderSurface {
              required property var modelData
              width: (cardRow.width - cardRow.spacing * 3) / 4
              implicitHeight: Style.space(72)
              radius: Style.cornerRadius
              color: Style.normalFillFor(root.foreground, root.accent)
              borderSpec: Border.controlSpec("normal", root.foreground, root.accent)

              Column {
                anchors.fill: parent
                anchors.margins: Style.space(8)
                spacing: Style.space(2)
                Text {
                  textFormat: Text.PlainText
                  text: modelData.label
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }
                Text {
                  textFormat: Text.PlainText
                  text: modelData.value
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.subtitle
                  font.bold: true
                }
                Text {
                  textFormat: Text.PlainText
                  text: modelData.detail
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                  width: parent.width
                }
              }
            }
          }
        }

        PanelSectionHeader {
          text: "Last 14 days"
          foreground: root.foreground
          fontFamily: root.fontFamily
        }

        Row {
          id: dayRow
          width: parent.width
          spacing: Style.space(4)
          Repeater {
            model: root.report.days || []
            Item {
              required property var modelData
              width: (dayRow.width - dayRow.spacing * 13) / 14
              height: Style.space(56)

              Rectangle {
                id: dayDot
                width: Math.min(parent.width - 2, Style.space(22))
                height: width
                radius: width / 2
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                color: {
                  if (modelData.count > 0) return root.accent
                  return "transparent"
                }
                opacity: modelData.before_start || modelData.future ? 0.35 : 1
                border.width: 1
                border.color: {
                  if (modelData.skipped) return root.urgent
                  if (modelData.count > 0) return root.accent
                  return root.dim
                }

                Text {
                  anchors.centerIn: parent
                  visible: modelData.count > 0
                  textFormat: Text.PlainText
                  text: String(modelData.count)
                  color: Color.background
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }
              }

              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                textFormat: Text.PlainText
                text: modelData.letter
                color: modelData.skipped ? root.urgent : root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }
          }
        }

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: root.report.range_skipped
            ? (root.report.range_skipped + (root.report.range_skipped === 1 ? " day skipped" : " days skipped")
              + " since they started · filled dots are sheets that day")
            : "Practiced every day in this window · filled dots are sheets that day"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        PanelSectionHeader {
          text: "Sheets per week"
          foreground: root.foreground
          fontFamily: root.fontFamily
        }

        Row {
          id: weekRow
          width: parent.width
          height: Style.space(72)
          spacing: Style.space(6)
          Repeater {
            model: root.report.weeks || []
            Item {
              required property var modelData
              width: (weekRow.width - weekRow.spacing * 7) / 8
              height: weekRow.height

              Rectangle {
                id: weekBar
                width: Math.max(Style.space(10), parent.width - Style.space(4))
                height: {
                  var maxW = Math.max(1, Number(root.report.max_week || 0))
                  var h = parent.height - Style.space(22)
                  if (!(modelData.count > 0)) return Style.space(3)
                  return Math.max(Style.space(6), h * modelData.count / maxW)
                }
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: weekLbl.top
                anchors.bottomMargin: Style.space(4)
                radius: Style.cornerRadius
                color: modelData.current ? root.accent : root.foreground
                opacity: modelData.current ? 1 : 0.35
              }

              Text {
                id: weekLbl
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                textFormat: Text.PlainText
                text: modelData.label
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }
          }
        }

        PanelSectionHeader {
          text: "Time per exercise"
          foreground: root.foreground
          fontFamily: root.fontFamily
        }

        Repeater {
          model: root.report.levels || []
          BorderSurface {
            required property var modelData
            width: parent.width
            implicitHeight: levelCol.implicitHeight + Style.space(24)
            radius: Style.cornerRadius
            color: Style.normalFillFor(root.foreground, root.accent)
            borderSpec: Border.controlSpec("normal", root.foreground, root.accent)

            Column {
              id: levelCol
              property var sparkPoints: modelData.spark || []
              x: Style.space(12)
              y: Style.space(12)
              width: parent.width - Style.space(24)
              spacing: Style.space(6)

              Text {
                width: parent.width
                textFormat: Text.PlainText
                text: "Level " + modelData.level + "  " + root.levelTitle(modelData.level)
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                font.bold: true
                elide: Text.ElideRight
              }

              Text {
                width: parent.width
                textFormat: Text.PlainText
                text: modelData.sessions + (modelData.sessions === 1 ? " sheet" : " sheets")
                  + " · best " + (modelData.best_pace_label || root.formatDuration(modelData.best_seconds))
                  + (modelData.accuracy_pct === null || modelData.accuracy_pct === undefined
                    ? ""
                    : " · " + root.pctLabel(modelData.accuracy_pct) + " correct")
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }

              Row {
                id: sparkRow
                width: parent.width
                height: Style.space(44)
                spacing: Style.space(3)
                Repeater {
                  model: levelCol.sparkPoints
                  Rectangle {
                    required property var modelData
                    required property int index
                    width: {
                      var n = Math.max(1, levelCol.sparkPoints.length)
                      return Math.max(4, (sparkRow.width - sparkRow.spacing * (n - 1)) / n)
                    }
                    height: Math.max(Style.space(4), sparkRow.height * Number(modelData.height || 0.2))
                    anchors.bottom: parent.bottom
                    radius: 2
                    color: root.accent
                    opacity: 0.35 + 0.65 * (1 - Number(modelData.height || 0.5))
                  }
                }
              }

              Text {
                width: parent.width
                textFormat: Text.PlainText
                text: modelData.pace_label
                color: modelData.trend === "slower" ? root.urgent : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                wrapMode: Text.WordWrap
              }
            }
          }
        }

        PanelSeparator { foreground: root.foreground }

        PanelSectionHeader {
          text: "Sessions"
          foreground: root.foreground
          fontFamily: root.fontFamily
        }
      }

      Repeater {
        model: root.studentId === "" ? [] : root.sessions
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
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              elide: Text.ElideRight
            }
            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: root.formatDuration(modelData.duration_seconds)
                + root.perExerciseLabel(modelData)
                + " · " + root.scoreLabel(modelData)
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
    }
  }
}
