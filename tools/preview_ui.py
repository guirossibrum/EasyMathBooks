#!/usr/bin/env python3
"""Render actual UI components with isolated demo data; check workflow transitions.

Run with the project's venv Python. Requires Quickshell and the installed Omarchy
shell UI kit. Replaces only the desktop window host and external side effects.
Does not load the live plugin, open PDFs, or read/write real student records.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHECKS = r'''
function check(value, message) {
  if (!value) throw new Error(message)
}
function verifyFlow(data) {
  var generated = JSON.parse(JSON.stringify(data))
  generated.settings.variant = 16
  generated.generated = { code: "1-15", problem_count: 25,
    pdf_path: "/demo/1-15.pdf", answers_path: "/demo/1-15-answers.pdf" }
  review.applySnap(generated)
  demoWindow.check(review.practiceMode && review.activeTab === 0, "Create must enter practice")
  demoWindow.check(review.sheetCode === "1-15", "Practice must use the generated code, not the next seed")
  demoWindow.check(review.nextSheetCode === "1-16", "Next print selection must be preserved")
  review.applySnap(data)
  demoWindow.check(review.pdfPath === "/demo/1-15.pdf", "PDF must survive snapshot refresh")
  review.prepareNextSheet()
  demoWindow.check(!review.practiceMode && review.sheetCode === "1-16", "Back must prepare next sheet")
  demoWindow.check(review.pdfPath === "", "Another sheet must not open the previous PDF")
  review.practiceCreatedSheet()
  review.timerBase = 90000
  review.scoreValue = 24
  review.savePractice()
  demoWindow.check(review.demoCommand.cmd === "save-session", "Save must call the helper")
  demoWindow.check(review.demoCommand.payload.variant === 15, "Save must use the practiced sheet")
  demoWindow.check(review.demoCommand.payload.duration_seconds === 90, "Save must keep elapsed time")
  demoWindow.check(review.demoCommand.payload.score === 24, "Save must keep the score")
  var saved = JSON.parse(JSON.stringify(data))
  saved.settings.variant = 16
  saved.saved = { sheet_code: "1-15", duration_seconds: 90, score: 24, score_max: 25 }
  review.applySnap(saved)
  demoWindow.check(review.activeTab === 1 && !review.practiceMode, "Successful save must show Progress")
  demoWindow.check(review.elapsedSec === 0 && review.scoreValue === 0, "Successful save must reset practice")
  demoWindow.check(review.createdSheet === null, "Completed sheet must not remain the practice shortcut")
  demoWindow.check(review.parseCode("41-1") === null && review.parseCode("1-0") === null,
    "Invalid codes must be rejected")
  review.applySnap(data)
  review.activeTab = 0
  review.lastMessage = ""
  console.log("PASS: create → practice → next sheet → save → progress; code and PDF identity")
}
'''


def main():
    with TemporaryDirectory(prefix="easymath-ui-") as tmp:
        base = Path(tmp)
        # Set this before importing storage; all fixture records live in tmp.
        os.environ["XDG_DATA_HOME"] = str(base / "data")
        import store
        import cli
        import shutil
        demo_db = ROOT / "output/ui-review/demo/easymathbooks/easymath.db"
        if not demo_db.exists():
            subprocess.run([sys.executable, str(ROOT / "tools/create_demo.py")], check=True)
        store.db_path().parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(demo_db, store.db_path())
        store.init_db()
        (base / "fixture.json").write_text(json.dumps(cli.snapshot()))
        for name in ("Commons", "Ui"):
            (base / name).symlink_to(Path("/usr/share/omarchy/shell") / name)
        for name in ("AppDropdown.qml", "AppSearchableDropdown.qml"):
            (base / name).write_text((ROOT / name).read_text())
        source = (ROOT / "Panel.qml").read_text()
        source = source.replace('Panel {\n  id: root', '''Rectangle {
  id: root
  color: Color.popups.background
  property var bar: null
  property bool opened: true
  property string moduleName
  property string ipcTarget
  property bool manageIpc
  property var demoCommand: ({})
  function open() { opened = true }
  function close() { opened = false }
  function toggle() { opened = !opened }''', 1)
        a = source.index('  function run(cmd, payload) {')
        b = source.index('  function scheduleRefresh()', a)
        source = source[:a] + '''  function run(cmd, payload) {
    demoCommand = {cmd: cmd, payload: payload}
  }

''' + source[b:]
        source = source.replace('  function refresh() { run("snapshot", hydrated ? selectionPayload() : ({})) }',
                                '  function refresh() {}')
        source = source.replace('    Quickshell.execDetached(["xdg-open", path])', '')
        source = source.replace('  Component.onCompleted: refresh()', '')
        source = source.replace('  property bool hydrated: false', '  readonly property real demoContentHeight: panelContent.implicitHeight\n  property bool hydrated: false')
        a = source.index('  KeyboardPanel {')
        b = source.index('\n', source.index('    contentHeight:', a))
        source = source[:a] + '  Item {\n    id: panel\n    anchors.fill: parent\n' + source[b:]
        source = source.replace('    anchors.fill: parent\n    bar: root.bar\n    text: "󰃬"',
                                '    visible: false\n    bar: root.bar\n    text: "󰃬"')
        (base / "ReviewPanel.qml").write_text(source)
        (base / "shell.qml").write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
ShellRoot {
  FloatingWindow {
    id: demoWindow
    visible: true
    implicitWidth: 556
    implicitHeight: Number(Quickshell.env("REVIEW_HEIGHT"))
    color: Color.popups.background
    ReviewPanel { id: review; anchors.fill: parent; anchors.margins: 18 }
    FileView { id: fixture; path: "''' + str(base / "fixture.json") + '''" }
''' + CHECKS + '''
    Timer {
      interval: 1800; running: true
      onTriggered: {
        try {
          var data = JSON.parse(fixture.text())
          review.applySnap(data)
          demoWindow.verifyFlow(data)
          review.activeTab = Number(Quickshell.env("REVIEW_TAB") || 0)
          review.settingsOpen = Quickshell.env("REVIEW_SETTINGS") === "1"
          review.settingsPage = Quickshell.env("REVIEW_PAGE") || "print"
          if (review.settingsPage === "profile") review.editProfile(false)
          if (Quickshell.env("REVIEW_PRACTICE") === "1") {
            data.settings.variant = 16
            data.generated = {code: "1-15", problem_count: 25,
              pdf_path: "/demo/1-15.pdf", answers_path: "/demo/1-15-answers.pdf"}
            review.applySnap(data)
          }
          capture.start()
        } catch (error) { console.error("FAIL", error); Qt.quit() }
      }
    }
    Timer {
      id: capture; interval: 500
      onTriggered: {
        if (review.demoContentHeight > review.height) {
          console.error("FAIL", "Page does not fit", review.demoContentHeight, review.height)
          Qt.quit(); return
        }
        review.grabToImage(function(result) {
        result.saveToFile(Quickshell.env("REVIEW_OUTPUT")); Qt.quit()
        })
      }
    }
  }
}''')
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="basic",
                   QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(base / "runtime"),
                   XDG_CACHE_HOME=str(base / "cache"))
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        (base / "runtime").mkdir(mode=0o700)
        out = ROOT / "docs/ui-review"
        out.mkdir(parents=True, exist_ok=True)
        scenes = [
            ("worksheet", 436, {}),
            ("practice", 676, {"REVIEW_PRACTICE": "1"}),
            ("settings", 676, {"REVIEW_SETTINGS": "1"}),
            ("progress", 676, {"REVIEW_TAB": "1"}),
            ("students", 536, {"REVIEW_SETTINGS": "1", "REVIEW_PAGE": "students"}),
            ("profile", 536, {"REVIEW_SETTINGS": "1", "REVIEW_PAGE": "profile"}),
            ("reprint", 436, {"REVIEW_SETTINGS": "1", "REVIEW_PAGE": "reprint"}),
            ("history", 536, {"REVIEW_SETTINGS": "1", "REVIEW_PAGE": "history"}),
        ]
        for name, height, options in scenes:
            image = out / f"{name}.png"
            image.unlink(missing_ok=True)
            result = subprocess.run(["quickshell", "-p", str(base), "--no-color"],
                                    env=dict(env, REVIEW_HEIGHT=str(height),
                                             REVIEW_OUTPUT=str(image), **options),
                                    capture_output=True, text=True, timeout=20)
            log = result.stdout + result.stderr
            if result.returncode or "FAIL" in log or not image.exists():
                raise RuntimeError(log)
            print(f"PASS {name}: workflow checks and QML render → {image.relative_to(ROOT)}")
        print("Demo only: desktop popup placement, compositor focus, and physical printing require a live check.")


if __name__ == "__main__":
    main()
