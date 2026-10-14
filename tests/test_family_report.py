from contextlib import closing, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from datetime import date

import store
from report import render_report, THEMES


class FamilyReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.previous = os.environ.get('XDG_DATA_HOME')
        os.environ['XDG_DATA_HOME'] = self.tmp.name
        store.init_db()

    def tearDown(self):
        if self.previous is None:
            os.environ.pop('XDG_DATA_HOME', None)
        else:
            os.environ['XDG_DATA_HOME'] = self.previous
        self.tmp.cleanup()

    def test_profile_update_preserves_practice(self):
        student = store.add_student('Lily', 'female', 'flowers')
        store.add_session(student['id'], '1-1', 1, 1, '2026-10-13', 90, score=25, score_max=25)
        updated = store.update_student(student['id'], 'Lily Rose', 'female', 'unicorns')
        self.assertEqual(updated['motif'], 'unicorns')
        self.assertEqual(updated['name'], 'Lily Rose')
        self.assertEqual(len(store.list_sessions(student['id'])), 1)
        html = render_report(updated, store.list_sessions(student['id']), today=date(2026, 10, 13))
        self.assertIn('A little everyday magic', html)
        self.assertNotIn('Garden of growth', html)

    def test_gender_and_motif_validation(self):
        for gender, motif in [('unknown', 'flowers'), ('female', 'cars'), ('male', 'unicorns')]:
            with self.subTest(gender=gender, motif=motif), self.assertRaises(ValueError):
                store.add_student('Test', gender, motif)
        self.assertEqual(store.list_students(), [])

    def test_existing_students_are_preserved_by_migration(self):
        store.db_path().unlink()
        with closing(sqlite3.connect(store.db_path())) as conn:
            conn.execute('CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, created_at TEXT NOT NULL)')
            conn.execute("INSERT INTO students VALUES (1, 'Existing student', '2026-01-01')")
            conn.commit()
        store.init_db()
        store.init_db()
        student = store.student_by_id(1)
        self.assertEqual(student['name'], 'Existing student')
        self.assertIsNone(student['gender'])
        self.assertIsNone(student['motif'])
        html = render_report(student, [], today=date(2026, 10, 13))
        self.assertIn('Little steps, bright futures', html)

    def test_period_and_future_filtering_and_escaped_user_content(self):
        student = store.add_student('<script>alert(1)</script>', 'male', 'cars')
        for day, variant in [('2026-09-01', 1), ('2026-10-13', 2), ('2026-10-14', 3)]:
            store.add_session(student['id'], f'1-{variant}', 1, variant, day,
                              90, score=25, score_max=25, notes='<img src=x onerror=alert(1)>')
        rows = store.list_sessions(student['id'])
        recent = render_report(student, rows, today=date(2026, 10, 13))
        all_time = render_report(student, rows, period='all', today=date(2026, 10, 13))
        self.assertNotIn('<script>alert(1)</script>', recent)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', recent)
        self.assertNotIn('<img src=x', recent)
        self.assertNotIn('<td>2026-09-01</td>', recent)
        self.assertIn('<td>2026-09-01</td>', all_time)
        self.assertNotIn('<td>2026-10-14</td>', all_time)
        self.assertIn('window.print()', recent)
        self.assertIn('@media print', recent)
        self.assertNotIn('<link ', recent)
        self.assertNotIn('<script src=', recent)

    def test_all_six_motifs_render_with_no_data(self):
        for gender, motifs in store.MOTIFS.items():
            for motif in motifs:
                with self.subTest(motif=motif):
                    student = store.add_student(motif, gender, motif)
                    html = render_report(student, [], today=date(2026, 10, 13))
                    self.assertIn(THEMES[motif][0], html)
                    self.assertIn('Ready when you are.', html)
                    self.assertIn('<svg', html)
                    self.assertNotIn('None%', html)

    def test_cli_exports_a_self_contained_report(self):
        import cli
        student = store.add_student('Oliver', 'male', 'airplanes')
        output = StringIO()
        with redirect_stdout(output):
            rc = cli.main(['export-report', json.dumps({'student_id': student['id'], 'period': 'month'})])
        self.assertEqual(rc, 0)
        response = json.loads(output.getvalue())
        path = Path(response['report_document']['path'])
        self.assertTrue(path.is_relative_to(store.default_output_dir()))
        self.assertIn('Ready for new horizons', path.read_text())


    def test_invalid_period_rejected(self):
        student = store.add_student('Test')
        with self.assertRaises(ValueError):
            render_report(student, [], period='unknown')


if __name__ == '__main__':
    unittest.main()
