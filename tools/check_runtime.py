#!/usr/bin/env python3
"""Exercise real QML Process handling against an isolated database, without opening apps."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from preview_ui import prepare_ui_component, ROOT

SCRIPT = r'''
    property int phase: 0
    property int ticks: 0
    property string firstReport: ""
    Timer {
      interval: 50; repeat: true; running: true
      onTriggered: {
        runner.ticks++
        if (runner.ticks > 300) { console.error("FAIL", "Helper did not settle", runner.phase); Qt.quit(); return }
        if (review.busy || review.commandQueue.length || review.testDocumentOpener.running) return
        try {
          if (runner.phase === 0) {
            review.applySnap(JSON.parse(fixture.text()))
            review.navigate("settings")
            review.navigate("reminders")
            review.run("set-student-options", {student_id: 1, missed_days: 4, reminder_time: "17:40"})
            review.run("set-student-options", {student_id: 1, show_timing: true})
            review.run("snapshot", {})
            review.run("snapshot", {})
            review.run("set-student-options", {student_id: 1, missed_days: 5, reminder_time: "19:25"})
          } else if (runner.phase === 1) {
            runner.check(review.selectedStudent.missed_days === 5 && review.selectedStudent.reminder_time === "19:25"
              && review.selectedStudent.show_timing === 1, "Queued saves must all be applied in order")
            runner.check(review.currentPage === "reminders", "Real reminder saves must not reset navigation")
            review.run("set-student-options", {student_id: 1, missed_days: 0})
          } else if (runner.phase === 2) {
            runner.check(review.lastError.indexOf("1–365") !== -1, "Failed helper must return a useful error")
            runner.check(review.currentPage === "reminders", "Failed save must preserve the page")
            review.editProfile(false)
            review.profileMotif = "unicorns"
            review.saveProfile(review.newStudentName)
            review.run("export-report", {student_id: 1})
          } else if (runner.phase === 3) {
            runner.check(review.currentPage === "reminders", "Profile save must return to its real caller")
            runner.check(review.selectedStudent.motif === "unicorns", "Real profile save must update motif")
            runner.firstReport = review.snap.report_document.path
            review.editProfile(false)
            review.profileMotif = "flowers"
            review.saveProfile(review.newStudentName)
            review.run("export-report", {student_id: 1})
          } else if (runner.phase === 4) {
            runner.check(review.snap.report_document.path !== runner.firstReport, "Changed motifs must create new report versions")
            runner.check(review.currentPage === "reminders", "Regeneration must preserve return context")
            review.switchRoot(0)
          } else if (runner.phase === 5) {
            var search = runner.findControl(review, "AppSearchableDropdown_")
            runner.check(search !== null, "Level picker must be present")
            search.open()
          } else if (runner.phase === 6) {
            var search = runner.findControl(review, "AppSearchableDropdown_")
            runner.check(search.menuOpen, "Level picker must open")
            search.testOptionList.currentIndex = 1
            search.testOptionList.selectCurrent()
            runner.check(review.levelValue === "2", "Choosing a level must update the app")
            review.levelValue = "1"
            runner.check(search.value === "1", "Level picker must follow subsequent app selection changes")
            review.refresh()
            runner.findControl(review, "AppDropdown_").open()
          } else if (runner.phase === 7) {
            var dropdown = runner.findControl(review, "AppDropdown_")
            runner.check(dropdown.menuOpen, "Student picker must open")
            dropdown.close()
            review.navigate("students")
            dropdown = runner.findControl(review, "AppDropdown_")
            var selector = dropdown.testOptionList
            runner.check(selector !== null, "Student menu must support selection")
            selector.currentIndex = 2
            selector.selectCurrent()
            runner.check(review.studentId === "2", "Selecting the second student must update the app")
            review.run("delete-student", {student_id: 2})
          } else if (runner.phase === 8) {
            var dropdown = runner.findControl(review, "AppDropdown_")
            runner.check(review.studentId === "" && dropdown.value === "",
              "Deleting the selected student must clear both app and dropdown selection")
            runner.check(dropdown.currentLabel() === review.studentOptions[0].label,
              "Deleted student must show the empty label, never its numeric ID")
            runner.check(review.students.length === 1 && review.students[0].id === 1,
              "Deleting one student must preserve the other")
            var selector = dropdown.testOptionList
            selector.currentIndex = 1
            selector.selectCurrent()
            runner.check(dropdown.currentLabel() === "Runtime Test", "Remaining student must show its name")
            review.run("delete-student", {student_id: 1})
          } else if (runner.phase === 9) {
            var dropdown = runner.findControl(review, "AppDropdown_")
            runner.check(review.students.length === 0 && review.studentId === "" && dropdown.value === "",
              "Deleting the last student must leave an empty selection: " + JSON.stringify([review.students.length, review.studentId, dropdown.value]))
            runner.check(dropdown.currentLabel() === review.studentOptions[0].label,
              "Empty student list must show the empty label")
            review.run("add-student", {name: 'Private "☀" Test\nChild', gender: "female", motif: "flowers"})
          } else if (runner.phase === 10) {
            runner.check(review.studentName === 'Private "☀" Test\nChild', "Names must round-trip over stdin")
            review.run("save-session", {student_id: Number(review.studentId), level: 1, variant: 1,
              duration_seconds: 123, score: 24, score_max: 25, notes: 'Private "☀" note\n'.repeat(8192)})
          } else {
            runner.check(review.lastError === "" && review.sessions.length === 1,
              "Large stdin request must finish and preserve the saved session")
            runner.check(review.sessions[0].notes === 'Private "☀" note\n'.repeat(8192).trim()
              && review.sessions[0].duration_seconds === 123 && review.sessions[0].score === 24,
              "Notes, timing and scores must round-trip over stdin without truncation")
            console.log("PASS REAL HELPER: stdin payloads, queued saves, invalid input, motif edits, report regeneration, Back context, dropdown overlays, and student deletion")
            Qt.quit()
          }
          runner.phase++
        } catch (error) { console.error("FAIL", error); Qt.quit() }
      }
    }
'''


def main():
    with TemporaryDirectory(prefix='easymath-runtime-') as tmp:
        base = Path(tmp)
        os.environ['XDG_DATA_HOME'] = str(base/'data')
        import store
        import cli
        store.init_db()
        student = store.add_student('Runtime Test', 'female', 'flowers')
        store.add_student('Second Test', 'male', 'cars')
        store.set_setting('student_id', student['id'])
        (base/'fixture.json').write_text(json.dumps(cli.snapshot()))
        prepare_ui_component(base, mock_helper=False, mock_open=False)
        component = base/'ReviewPanel.qml'
        component.write_text(component.read_text().replace('  id: root',
                             '  id: root\n  property alias testDocumentOpener: documentOpener', 1))
        commands = base/'bin'
        commands.mkdir()
        opened_log = base/'opened.jsonl'
        opener = commands/'xdg-open'
        opener.write_text(f'''#!{sys.executable}
import json, sys
from pathlib import Path
with Path({str(opened_log)!r}).open('a') as output:
    output.write(json.dumps(sys.argv[1:])+'\\n')
''')
        opener.chmod(0o700)
        dropdown = base/'AppDropdown.qml'
        dropdown.write_text(dropdown.read_text().replace('  id: root',
                            '  id: root\n  property alias testOptionList: optionList', 1))
        search = base/'AppSearchableDropdown.qml'
        search.write_text(search.read_text().replace('  id: root',
                         '  id: root\n  property alias testOptionList: resultList', 1))
        script = SCRIPT
        if '--missing-helper' not in sys.argv:
            spy = base/'helper-spy'
            argv_log = base/'argv.jsonl'
            spy.write_text(f'''#!{sys.executable}
import json, subprocess, sys
from pathlib import Path
with Path({str(argv_log)!r}).open('a') as output:
    output.write(json.dumps({{'argv': sys.argv[1:], 'proc': Path('/proc/self/cmdline').read_bytes().decode().split('\\0')}})+'\\n')
if len(sys.argv) != 2:
    raise SystemExit('FAIL: Only the command verb may be passed as an argument')
request = sys.stdin.read()
raise SystemExit(subprocess.run([{str(ROOT/'bin/easymath-cli')!r}, sys.argv[1]], input=request, text=True).returncode)
''')
            spy.chmod(0o700)
            component = base/'ReviewPanel.qml'
            component.write_text(component.read_text().replace(str(ROOT/'bin/easymath-cli'), str(spy)))
        if '--missing-helper' in sys.argv:
            component = base/'ReviewPanel.qml'
            component.write_text(component.read_text().replace(str(ROOT/'bin/easymath-cli'), str(base/'missing-helper')))
            script = r'''
    property int phase: 0
    property int ticks: 0
    Timer {
      interval: 50; repeat: true; running: true
      onTriggered: {
        runner.ticks++
        if (runner.ticks > 50) { console.error("FAIL", "Missing helper left the app busy"); Qt.quit(); return }
        if (runner.phase === 0) { runner.phase = 1; review.run("snapshot", {}); return }
        if (review.busy) return
        if (!review.lastError) { console.error("FAIL", "Missing helper must show an error"); Qt.quit(); return }
        console.log("PASS REAL HELPER: missing executable releases busy state and reports failure")
        Qt.quit()
      }
    }
'''
        (base/'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
  FloatingWindow {
    id: runner
    visible: true
    implicitWidth: 556; implicitHeight: 720
    function check(ok, message) { if (!ok) throw new Error(message) }
    function findControl(item, prefix) {
      if (String(item).indexOf(prefix) === 0) return item
      var children = item.children || []
      for (var i = 0; i < children.length; i++) {
        var found = findControl(children[i], prefix)
        if (found) return found
      }
      return null
    }
    ReviewPanel { id: review; anchors.fill: parent }
    FileView { id: fixture; path: '''+json.dumps(str(base/'fixture.json'))+''' }
'''+script+'''
  }
}''')
        (base/'runtime').mkdir(mode=0o700)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='basic',
                   QT_QUICK_BACKEND='software', XDG_RUNTIME_DIR=str(base/'runtime'), XDG_CACHE_HOME=str(base/'cache'))
        env['PATH'] = str(commands)+os.pathsep+env['PATH']
        env.pop('DISPLAY', None); env.pop('WAYLAND_DISPLAY', None)
        result = subprocess.run(['quickshell', '-p', str(base), '--no-color'], env=env,
                                capture_output=True, text=True, timeout=25)
        log = result.stdout+result.stderr
        if result.returncode or 'FAIL' in log or 'Binding loop' in log or 'PASS REAL HELPER' not in log:
            raise RuntimeError(log)
        if '--missing-helper' not in sys.argv:
            requests = [json.loads(line) for line in argv_log.read_text().splitlines()]
            assert len(requests) >= 15, 'Expected real helper requests to be inspected'
            for request in requests:
                assert len(request['argv']) == 1 and request['argv'][0] in cli.COMMANDS, request
                assert all('Private' not in arg and 'Runtime Test' not in arg and '{' not in arg
                           for arg in request['proc']), 'Private payload found in procfs arguments'
            print(f'PASS PRIVACY: inspected {len(requests)} live helper command lines; no JSON or child records in argv')
            opened = [json.loads(line) for line in opened_log.read_text().splitlines()]
            assert len(opened) == 2, 'Both motif reports must open through the real QML document process'
            for argv in opened:
                assert len(argv) == 1 and Path(argv[0]).parent == store.data_dir()/'viewing'
                assert 'Runtime Test' not in argv[0] and 'Private' not in argv[0]
                assert Path(argv[0]).read_text().startswith('<!doctype html>')
            print('PASS PRIVACY: both reports opened through opaque paths using a fake desktop opener')
        print(next(line for line in log.splitlines() if 'PASS REAL HELPER' in line))


if __name__ == '__main__':
    main()
