from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from unittest.mock import Mock

import store


@contextmanager
def permissive_umask():
    previous = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(previous)


class PrivateStorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.env = patch.dict(os.environ, XDG_DATA_HOME=str(self.base/'data'))
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def mode(self, path):
        return stat.S_IMODE(path.stat().st_mode)

    def test_new_database_is_private_despite_umask_022(self):
        with permissive_umask():
            store.init_db()
            store.add_student('Private Test')
        self.assertEqual(self.mode(store.data_dir()), 0o700)
        self.assertEqual(self.mode(store.db_path()), 0o600)

    def test_existing_data_is_secured_without_changing_records(self):
        store.init_db()
        student = store.add_student('Existing Test', 'female', 'flowers')
        store.add_session(student['id'], '1-1', 1, 1, '2026-10-13', 90,
                          score=25, score_max=25, notes='Private practice note')
        store.set_student_options(student['id'], {'notification_consent': True,
            'missed_reminder': True, 'missed_days': 5, 'reminder_time': '19:45'})
        before = (store.list_students(), store.list_sessions(student['id']))
        store.data_dir().chmod(0o755)
        store.db_path().chmod(0o644)
        # WAL sidecars exist while another connection has the database open.
        with sqlite3.connect(store.db_path()) as other:
            other.execute('PRAGMA journal_mode=WAL')
            other.execute('UPDATE students SET name=name')
            other.commit()
            sidecars = [Path(str(store.db_path())+suffix) for suffix in ('-wal', '-shm')]
            for path in sidecars:
                self.assertTrue(path.exists())
                path.chmod(0o644)
            with permissive_umask():
                store.init_db()
                store.init_db()
            self.assertEqual(self.mode(store.data_dir()), 0o700)
            for path in [store.db_path(), *sidecars]:
                self.assertEqual(self.mode(path), 0o600)
            self.assertEqual((store.list_students(), store.list_sessions(student['id'])), before)
        other.close()

    def test_legacy_copy_is_private_and_retains_the_original(self):
        legacy_root = self.base/'legacy-plugin'
        legacy = legacy_root/'data/easymath.db'
        legacy.parent.mkdir(parents=True)
        with sqlite3.connect(legacy) as conn:
            conn.execute('CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, created_at TEXT NOT NULL)')
            conn.execute("INSERT INTO students VALUES (1, 'Legacy Test', '2026-01-01')")
        conn.close()
        legacy.chmod(0o644)
        with patch.object(store, 'ROOT', legacy_root), permissive_umask():
            store.init_db()
            store.init_db()
        self.assertEqual(store.student_by_id(1)['name'], 'Legacy Test')
        self.assertTrue(legacy.exists())
        self.assertEqual(self.mode(legacy), 0o600)
        self.assertEqual(self.mode(store.db_path()), 0o600)
        self.assertEqual(self.mode(store.data_dir()), 0o700)

    def test_legacy_copy_includes_committed_wal_records(self):
        legacy_root = self.base/'legacy-plugin'
        legacy = legacy_root/'data/easymath.db'
        legacy.parent.mkdir(parents=True)
        other = sqlite3.connect(legacy)
        try:
            other.execute('PRAGMA journal_mode=WAL')
            other.execute('CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, created_at TEXT NOT NULL)')
            other.commit()
            other.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            other.execute("INSERT INTO students VALUES (1, 'WAL Test', '2026-01-01')")
            other.commit()
            self.assertGreater(Path(str(legacy)+'-wal').stat().st_size, 0)
            with patch.object(store, 'ROOT', legacy_root):
                store.init_db()
            self.assertEqual(store.student_by_id(1)['name'], 'WAL Test')
            self.assertEqual(list(store.data_dir().glob('.legacy-*')), [])
        finally:
            other.close()

    def test_rollback_journal_permissions_are_private(self):
        store.init_db()
        student = store.add_student('Journal Test')
        other = sqlite3.connect(store.db_path())
        try:
            other.execute("UPDATE students SET name='Changed Test' WHERE id=?", (student['id'],))
            journal = Path(str(store.db_path())+'-journal')
            self.assertEqual(self.mode(journal), 0o600)
            journal.chmod(0o644)
            secured = store.connect()
            secured.close()
            self.assertEqual(self.mode(journal), 0o600)
            other.rollback()
            self.assertEqual(store.student_by_id(student['id'])['name'], 'Journal Test')
        finally:
            other.close()

    def test_database_symlink_does_not_change_an_unrelated_file(self):
        unrelated = self.base/'unrelated'
        unrelated.write_text('Keep this file unchanged')
        unrelated.chmod(0o644)
        store.data_dir().mkdir(parents=True)
        store.db_path().symlink_to(unrelated)
        with self.assertRaises(OSError):
            store.connect()
        self.assertEqual(unrelated.read_text(), 'Keep this file unchanged')
        self.assertEqual(self.mode(unrelated), 0o644)


class PrivateProtocolTest(unittest.TestCase):
    def test_notification_uses_omarchy_service_without_process_arguments(self):
        from gi.repository import Gio
        from reminders import send_notification
        bus = Mock()
        with patch.object(Gio, 'bus_get_sync', return_value=bus), \
             patch('subprocess.run', side_effect=AssertionError('Never put notification text in argv')):
            send_notification('A week worth keeping', "Private Child's weekly report is ready.")
        args = bus.call_sync.call_args.args
        self.assertEqual(args[:4], ('org.freedesktop.Notifications',
            '/org/freedesktop/Notifications', 'org.freedesktop.Notifications', 'Notify'))
        values = args[4].unpack()
        self.assertEqual(values[3], 'A week worth keeping')
        self.assertEqual(values[4], "Private Child's weekly report is ready.")
        self.assertEqual(values[6]['omarchy-glyph'], '󰃬')
        self.assertEqual(args[7], 8000)

    def test_real_helper_accepts_stdin_and_rejects_payload_arguments(self):
        root = Path(__file__).resolve().parents[1]
        helper = str(root/'bin/easymath-cli')
        with TemporaryDirectory() as tmp:
            env = dict(os.environ, XDG_DATA_HOME=tmp, PYTHONDONTWRITEBYTECODE='1')
            payload = {'name': 'Private "☀" Test\nChild', 'gender': 'female', 'motif': 'flowers'}
            result = subprocess.run([helper, 'add-student'], input=json.dumps(payload),
                                    env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertTrue(data['ok'])
            self.assertEqual(data['student']['name'], payload['name'])
            result = subprocess.run([helper, 'add-student', json.dumps({'name': 'Argument Test'})],
                                    input='', env=env, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('stdin', json.loads(result.stdout)['error'])
            self.assertNotIn('Argument Test', result.stdout)

    def test_document_opener_uses_opaque_path_for_legacy_named_files(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            original = base/'Private Child'/'Private Child worksheet.pdf'
            original.parent.mkdir()
            original.write_bytes(b'%PDF-1.4\nFictional worksheet\n')
            commands = base/'bin'
            commands.mkdir()
            observed = base/'opener.json'
            stub = commands/'xdg-open'
            stub.write_text(f'''#!{sys.executable}
import json, sys
from pathlib import Path
Path({str(observed)!r}).write_text(json.dumps({{"argv": sys.argv[1:], "proc": Path('/proc/self/cmdline').read_bytes().decode().split('\\0')}}))
''')
            stub.chmod(0o700)
            env = dict(os.environ, XDG_DATA_HOME=str(base/'data'),
                       PATH=str(commands)+os.pathsep+os.environ['PATH'])
            result = subprocess.run([str(root/'bin/easymath-cli'), 'open-document'],
                                    input=json.dumps({'path': str(original)}), env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr+result.stdout)
            self.assertTrue(json.loads(result.stdout)['document_opened'])
            deadline = time.monotonic()+3
            while not observed.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(observed.exists(), 'Fake desktop opener did not run')
            data = json.loads(observed.read_text())
            self.assertEqual(len(data['argv']), 1)
            self.assertTrue(all('Private Child' not in arg for arg in data['proc']))
            viewed = Path(data['argv'][0])
            self.assertRegex(viewed.name, r'^[0-9a-f]{32}\.pdf$')
            self.assertEqual(viewed.read_bytes(), original.read_bytes())
            self.assertEqual(stat.S_IMODE(viewed.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(viewed.parent.stat().st_mode), 0o700)
            self.assertTrue(original.exists())
