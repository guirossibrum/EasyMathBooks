import QtQuick
import QtQuick.Window
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
  property bool settingsOpen: false
  property string settingsPage: "print"
  property string profileId: ""
  property string profileGender: "female"
  property string profileMotif: "flowers"
  property string reportPeriod: "month"
  readonly property var genderOptions: [{value: "female", label: "Female"}, {value: "male", label: "Male"}]
  readonly property var motifOptions: profileGender === "female"
    ? [{value: "flowers", label: "Flowers"}, {value: "unicorns", label: "Unicorns"}, {value: "butterflies", label: "Butterflies"}]
    : [{value: "sports", label: "Sports"}, {value: "cars", label: "Cars"}, {value: "airplanes", label: "Airplanes"}]

  function editProfile(newProfile) {
    profileId = newProfile ? "" : studentId
    newStudentName = ""
    profileGender = "female"
    profileMotif = "flowers"
    if (!newProfile) {
      for (var i = 0; i < students.length; i++) {
        if (String(students[i].id) === profileId) {
          newStudentName = students[i].name
          profileGender = students[i].gender || "female"
          profileMotif = students[i].motif || (profileGender === "male" ? "sports" : "flowers")
        }
      }
    }
    settingsOpen = true
    settingsPage = "profile"
  }

  function saveProfile(name) {
    newStudentName = name
    run(profileId ? "update-student" : "add-student", {
      student_id: profileId ? Number(profileId) : "",
      name: name, gender: profileGender, motif: profileMotif
    })
  }
  property bool practiceMode: false
  property string nextSheetCode: ""

  function prepareNextSheet() {
    practiceMode = false
    if (nextSheetCode) applyCode(nextSheetCode)
  }
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
  property var createdSheet: null
  property int sessionPage: 0
  readonly property var recentSessions: sessions.slice(sessionPage * 3, sessionPage * 3 + 3)
  onStudentIdChanged: {
    createdSheet = null
    nextSheetCode = ""
    sessionPage = 0
    resetTimer()
    scoreValue = 0
    notesText = ""
  }

  function practiceCreatedSheet() {
    if (createdSheet) applyCode(createdSheet.code)
    practiceMode = true
    settingsOpen = false
    activeTab = 0
  }

  readonly property var tabs: [
    { name: "Worksheet", icon: "󰃬" },
    { name: "Progress", icon: "󰄨" }
  ]
  readonly property var students: snap.students || []
  readonly property var levels: snap.levels || []
  readonly property var sessions: snap.sessions || []
  readonly property var stats: snap.stats || []
  readonly property var report: snap.report || ({ has_data: false })
  readonly property int problemCount: Number(snap.problem_count || 0)
  readonly property string sheetCode: String(levelValue || "1") + "-" + String(seedValue || 1)
  readonly property var lastSheet: snap.last_sheet || null
  readonly property var currentPdfSheet: createdSheet && createdSheet.code === sheetCode ? createdSheet
    : (lastSheet && lastSheet.sheet_code === sheetCode ? lastSheet : null)
  readonly property string pdfPath: currentPdfSheet && currentPdfSheet.pdf_path ? String(currentPdfSheet.pdf_path) : ""
  readonly property string answersPath: currentPdfSheet && currentPdfSheet.answers_path ? String(currentPdfSheet.answers_path) : ""
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
    var out = [{ value: "", label: activeTab === 1 || practiceMode ? "Choose a student" : "Blank name line" }]
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
    if (!(level >= 1 && level <= 40) || !(seed >= 1 && seed <= 2147483646)) return null
    return { level: level, seed: seed }
  }

  function applyCode(text) {
    var parsed = parseCode(text)
    if (!parsed) {
      lastError = "Use a level from 1–40 and a positive sheet number, e.g. 1-502."
      return
    }
    if (String(parsed.level) === levelValue && parsed.seed === seedValue) return
    levelValue = String(parsed.level)
    seedValue = parsed.seed
    codeDraft = sheetCode
    lastError = ""
    scheduleRefresh()
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
    sessionPage = Math.min(sessionPage, Math.max(0, Math.ceil(sessions.length / 3) - 1))
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
      snap = Object.assign({}, data, { problem_count: data.generated.problem_count })
      createdSheet = data.generated
      nextSheetCode = sheetCode
      lastMessage = "Wrote " + data.generated.code + " · " + data.generated.problem_count + " problems"
      openPath(data.generated.pdf_path)
      practiceCreatedSheet()
    }
    if (data.report_document) openPath(data.report_document.path)
    if (data.profile_saved) { settingsPage = "students"; lastMessage = "Student profile saved" }
    if (data.student) {
      newStudentName = ""
      settingsOpen = false
      practiceMode = false
      activeTab = 0
    }
    if (data.saved) {
      lastMessage = "Saved " + data.saved.sheet_code + " in " + formatDuration(data.saved.duration_seconds)
        + " · " + data.saved.score + " / " + data.saved.score_max + " correct"
      resetTimer()
      scoreValue = 0
      notesText = ""
      practiceMode = false
      createdSheet = null
      nextSheetCode = ""
      activeTab = 1
    }
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
    if (studentId === "" || busy || problemCount < 1) return
    pauseTimer()
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
    nowMs = timerStarted
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

  function pctLabel(value) {
    if (value === null || value === undefined) return "—"
    var n = Number(value)
    if (!isFinite(n)) return "—"
    if (n === Math.round(n)) return Math.round(n) + "%"
    return n.toFixed(1) + "%"
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
        ? (report.week_skipped + (Number(report.week_skipped) === 1 ? " day without practice" : " days without practice"))
        : "sheets since Monday"
    },
    {
      label: "Accuracy · all time",
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
      root.settingsOpen = false
      if (n === "progress" || n === "3") root.activeTab = 1
      else {
        root.activeTab = 0
        root.practiceMode = n === "practice" || n === "1"
        root.settingsOpen = n === "students" || n === "2"
      }
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
    contentHeight: panel.fittedContentHeight(panelContent.implicitHeight)

    FocusScope {
      id: keyCatcher
      anchors.fill: parent
      focus: true
      Keys.onPressed: function(event) {
        if (root.confirmKind !== "") return
        if (event.key === Qt.Key_Escape) { root.close(); event.accepted = true }
        // Editors and focused controls handle their own keys first.
        if (Window.window && Window.window.activeFocusItem !== keyCatcher) return
        if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
          var dx = event.key === Qt.Key_Right ? 1 : -1
          root.activeTab = (root.activeTab + dx + root.tabs.length) % root.tabs.length
          event.accepted = true
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
          if (root.activeTab === 0 && !root.practiceMode && !root.settingsOpen && !root.busy) root.generateSheet()
          event.accepted = true
        } else if (event.key === Qt.Key_Space && root.practiceMode && !root.settingsOpen && root.activeTab === 0) {
          root.toggleTimer(); event.accepted = true
        }
      }

      Column {
        id: panelContent
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
          readonly property real tabWidth: (width - gearButton.implicitWidth - spacing * root.tabs.length) / root.tabs.length
          Repeater {
            model: root.tabs
            Button {
              focusable: true
              required property var modelData
              required property int index
              width: tabRow.tabWidth
              iconText: modelData.icon
              text: modelData.name
              fontSize: Style.font.caption
              foreground: root.foreground
              fontFamily: root.fontFamily
              selected: !root.settingsOpen && root.activeTab === index
              bordered: true
              horizontalPadding: Style.space(2)
              verticalPadding: Style.space(5)
              onClicked: { root.settingsOpen = false; root.activeTab = index }
            }
          }
          Button {
            id: gearButton
            focusable: true
            iconText: "⚙"
            tooltipText: "Print settings & students"
            selected: root.settingsOpen
            bordered: true
            foreground: root.foreground
            fontFamily: root.fontFamily
            onClicked: { root.settingsPage = "print"; root.settingsOpen = !root.settingsOpen }
          }

        }

        PanelSeparator { foreground: root.foreground }

        Item {
          id: tabBody
          width: parent.width
          height: tabLoader.implicitHeight

          Loader {
            id: tabLoader
            width: parent.width
            sourceComponent: root.settingsOpen ? (root.settingsPage === "profile" ? profileTab : (root.settingsPage === "students" ? studentsTab : (root.settingsPage === "reprint" ? reprintTab : (root.settingsPage === "history" ? historyTab : settingsTab))))
              : (root.activeTab === 1 ? progressTab : (root.practiceMode ? practiceTab : sheetTab))
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

      Button {
        visible: root.students.length === 0
        text: "Add your first student"
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.editProfile(true)
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

      BorderSurface {
        width: parent.width
        implicitHeight: sheetSummary.implicitHeight + Style.space(24)
        radius: Style.cornerRadius
        color: Style.normalFillFor(root.foreground, root.accent)
        borderSpec: Border.controlSpec("normal", root.foreground, root.accent)
        Column {
          id: sheetSummary
          x: Style.space(12)
          y: Style.space(12)
          width: parent.width - Style.space(24)
          spacing: Style.space(6)
          Text {
            text: "Ready to print · " + root.sheetCode
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.subtitle
            font.bold: true
          }
          Text {
            width: parent.width
            text: root.problemCount + " problems · " + (root.paperValue === "a4" ? "A4" : "Letter")
              + (root.examplesOn ? " · worked example" : "")
              + (root.answersOn ? " · answer key" : "")
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }

      Row {
        spacing: Style.space(8)
        Button {
          focusable: true
          text: root.busy ? "Creating…" : "Create & open worksheet"
          selected: true
          iconText: "󰈟"
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          enabled: !root.busy
          onClicked: root.generateSheet()
        }
        Button {
          focusable: true
          visible: root.pdfPath !== ""
          text: "Open PDF"
          tooltipText: root.createdSheet ? "Sheet " + root.createdSheet.code : "Sheet " + root.sheetCode
          enabled: root.pdfPath !== ""
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.openPath(root.pdfPath)
        }
        Button {
          focusable: true
          visible: root.answersPath !== ""
          text: "Answers"
          enabled: root.answersPath !== ""
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.openPath(root.answersPath)
        }
      }


      Button {
        focusable: true
        text: root.timerOn ? "Practice · " + root.formatDuration(root.elapsedSec)
          : (root.createdSheet ? "Record sheet " + root.createdSheet.code : "Record an existing worksheet")
        iconText: "󰔟"
        bordered: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.practiceCreatedSheet()
      }
    }
  }

  Component {
    id: settingsTab
    Column {
      width: tabLoader.width
      spacing: Style.space(12)
      PanelSectionHeader {
        text: "Print settings"
        foreground: root.foreground
        fontFamily: root.fontFamily
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
        label: "Include a worked example"
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



      Button {
        text: "Reprint by sheet code →"
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.settingsPage = "reprint"
      }
      Button {
        text: "Students & report motifs →"
        focusable: true
        bordered: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.settingsPage = "students"
      }
    }
  }

  Component {
    id: reprintTab
    Column {
      width: tabLoader.width
      spacing: Style.space(12)
      Button {
        text: "← Print settings"
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.settingsPage = "print"
      }
      PanelSectionHeader { text: "Reprint a worksheet"; foreground: root.foreground; fontFamily: root.fontFamily }
      Row {
        width: parent.width
        spacing: Style.space(10)

        NumberField {
          id: seedField
          label: "Sheet number"
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
        text: "The same sheet code always prints the same problems."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Button {
        text: "Use this sheet · " + root.sheetCode
        focusable: true
        bordered: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: { root.practiceMode = false; root.activeTab = 0; root.settingsOpen = false }
      }
    }
  }

  Component {
    id: practiceTab
    Column {
      width: tabLoader.width
      spacing: Style.space(10)

      Button {
        text: "← Prepare next worksheet"
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.prepareNextSheet()
      }

      PanelSectionHeader {
        text: "Record practice · " + root.sheetCode
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Row {
        spacing: Style.space(8)
        Button {
          text: "Open worksheet"
          focusable: true
          enabled: root.pdfPath !== ""
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.openPath(root.pdfPath)
        }
        Button {
          text: "Open answer key"
          focusable: true
          visible: root.answersPath !== ""
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.openPath(root.answersPath)
        }
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
          focusable: true
          text: root.timerOn ? "Pause" : "Start"
          iconText: root.timerOn ? "󰏤" : "󰐊"
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          onClicked: root.toggleTimer()
        }
        Button {
          focusable: true
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
        focusable: true
        text: "Save session"
        selected: true
        iconText: "󰄬"
        bordered: true
        enabled: root.studentId !== "" && !root.busy && root.problemCount > 0
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
      Button {
        text: "← Print settings"
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.settingsPage = "print"
      }
      AppDropdown {
        width: parent.width
        label: "Manage student"
        value: root.studentId
        options: root.studentOptions
        foreground: root.foreground
        fontFamily: root.fontFamily
        onChanged: function(v) { root.studentId = v; root.refresh() }
      }
      Button {
        text: "Edit name & report motif"
        enabled: root.studentId !== "" && !root.busy
        focusable: true
        bordered: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.editProfile(false)
      }
      Button {
        text: "Add a student"
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.editProfile(true)
      }
      PanelSeparator { foreground: root.foreground }
      Button {
        text: "Delete selected student"
        enabled: root.studentId !== "" && !root.busy
        focusable: true
        foreground: root.urgent
        fontFamily: root.fontFamily
        onClicked: root.confirmKind = "student"
      }
    }
  }

  Component {
    id: profileTab
    Column {
      width: tabLoader.width
      spacing: Style.space(12)
      Button {
        text: "← Students"
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.settingsPage = "students"
      }
      PanelSectionHeader { text: root.profileId ? "Student profile" : "New student"; foreground: root.foreground; fontFamily: root.fontFamily }
      TextField {
        id: profileName
        width: parent.width
        placeholderText: "Student name"
        text: root.newStudentName
        foreground: root.foreground
        onTextEdited: root.newStudentName = text
      }
      ButtonGroup {
        options: root.genderOptions
        value: root.profileGender
        foreground: root.foreground
        fontFamily: root.fontFamily
        onChanged: function(v) {
          root.profileGender = v
          root.profileMotif = v === "male" ? "sports" : "flowers"
        }
      }
      AppDropdown {
        width: parent.width
        label: "Report motif"
        value: root.profileMotif
        options: root.motifOptions
        foreground: root.foreground
        fontFamily: root.fontFamily
        onChanged: function(v) { root.profileMotif = v }
      }
      Text {
        width: parent.width
        text: "A personal touch for their printable math journey. You can change it anytime."
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
      Button {
        text: root.profileId ? "Save profile" : "Add student"
        enabled: String(root.newStudentName).trim() !== "" && !root.busy
        selected: true
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.saveProfile(profileName.text)
      }
    }
  }

  Component {
    id: historyTab
    Column {
      width: tabLoader.width
      spacing: Style.space(12)
      Button {
        text: "← Progress"
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: { root.settingsOpen = false; root.activeTab = 1 }
      }
      PanelSectionHeader { text: "Recent practice entries"; foreground: root.foreground; fontFamily: root.fontFamily }
      Repeater {
        model: root.recentSessions
        Item {
          required property var modelData
          width: parent.width
          implicitHeight: Style.space(58)
          Column {
            width: parent.width - deleteEntry.implicitWidth - Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(4)
            Text { width: parent.width; elide: Text.ElideRight; text: modelData.taken_at + " · Sheet " + modelData.sheet_code; color: root.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.body }
            Text { width: parent.width; elide: Text.ElideRight; text: root.formatDuration(modelData.duration_seconds) + " · " + root.scoreLabel(modelData) + " correct"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
          }
          PanelActionButton {
            id: deleteEntry
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            iconText: "󰧧"
            tooltipText: "Delete practice entry"
            foreground: root.foreground
            hoverColor: root.urgent
            fontFamily: root.fontFamily
            onClicked: { root.confirmSessionId = Number(modelData.id); root.confirmKind = "session" }
          }
        }
      }
      Row {
        spacing: Style.space(8)
        Button { text: "← Newer"; enabled: root.sessionPage > 0; focusable: true; foreground: root.foreground; fontFamily: root.fontFamily; onClicked: root.sessionPage-- }
        Button { text: "Older →"; enabled: (root.sessionPage + 1) * 3 < root.sessions.length; focusable: true; foreground: root.foreground; fontFamily: root.fontFamily; onClicked: root.sessionPage++ }
      }
    }
  }

  Component {
    id: progressTab
    Column {
      width: tabLoader.width
      spacing: Style.space(12)
      AppDropdown {
        width: parent.width
        label: "Student"
        value: root.studentId
        options: root.studentOptions
        foreground: root.foreground
        fontFamily: root.fontFamily
        onChanged: function(v) { root.studentId = v; root.refresh() }
      }
      Text {
        visible: !root.report.has_data
        width: parent.width
        text: root.studentId === "" ? "Choose a student to see their math journey." : "Every journey starts with one sheet. Their first saved practice will appear here."
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
      }
      Grid {
        id: overviewGrid
        visible: root.report.has_data
        width: parent.width
        columns: 2
        spacing: Style.space(8)
        Repeater {
          model: root.reportCardItems
          BorderSurface {
            required property var modelData
            width: (overviewGrid.width - overviewGrid.spacing) / 2
            implicitHeight: Style.space(78)
            radius: Style.cornerRadius
            color: Style.normalFillFor(root.foreground, root.accent)
            borderSpec: Border.controlSpec("normal", root.foreground, root.accent)
            Column {
              anchors.fill: parent
              anchors.margins: Style.space(8)
              spacing: Style.space(2)
              Text { text: modelData.label; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
              Text { text: modelData.value; color: root.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.subtitle; font.bold: true }
              Text { width: parent.width; text: modelData.detail; elide: Text.ElideRight; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
            }
          }
        }
      }
      PanelSeparator { foreground: root.foreground }
      PanelSectionHeader { text: "Their math journey · a family keepsake"; foreground: root.foreground; fontFamily: root.fontFamily }
      Text {
        width: parent.width
        text: "A happy, personal report to print, save as PDF, or put on the TV."
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
      ButtonGroup {
        options: [{value: "month", label: "Last 30 days"}, {value: "all", label: "All practice"}]
        value: root.reportPeriod
        foreground: root.foreground
        fontFamily: root.fontFamily
        onChanged: function(v) { root.reportPeriod = v }
      }
      Button {
        text: root.busy ? "Preparing report…" : "Open beautiful report"
        enabled: root.studentId !== "" && !root.busy
        selected: true
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.run("export-report", {student_id: Number(root.studentId), period: root.reportPeriod})
      }
      Button {
        text: "Change their report motif"
        enabled: root.studentId !== "" && !root.busy
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: root.editProfile(false)
      }
      Button {
        visible: root.studentId !== "" && root.sessions.length > 0
        text: "Review practice entries"
        focusable: true
        foreground: root.foreground
        fontFamily: root.fontFamily
        onClicked: { root.settingsPage = "history"; root.settingsOpen = true; root.sessionPage = 0 }
      }

    }
  }
}
