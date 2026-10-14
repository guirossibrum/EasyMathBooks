from contextlib import redirect_stdout
from datetime import date, datetime
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cli
import store
from report import render_report
from reminders import check_reminders, due_reminders
from encouragement import MESSAGES, weekly_message
from generate import generate_one, LEVEL_BY_NUM, paper_size, plan_sheet


class WeeklyFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.previous = os.environ.get('XDG_DATA_HOME')
        os.environ['XDG_DATA_HOME'] = self.tmp.name
        store.init_db()
        self.student = store.add_student('Lily', 'female', 'flowers')
        self.sid = self.student['id']
        store.set_setting('student_id', self.sid)

    def tearDown(self):
        if self.previous is None:
            os.environ.pop('XDG_DATA_HOME', None)
        else:
            os.environ['XDG_DATA_HOME'] = self.previous
        self.tmp.cleanup()

    def add(self, day, level=1, variant=1, seconds=100, correct=30, total=30):
        return store.add_session(self.sid, f'{level}-{variant}', level, variant,
                                 day, seconds, score=correct, score_max=total)

    def command(self, name, payload):
        output = StringIO()
        with redirect_stdout(output):
            rc = cli.main([name, json.dumps(payload)])
        return rc, json.loads(output.getvalue())

    def test_weekly_results_across_levels_with_timing_hidden(self):
        self.add('2026-10-07', level=1, seconds=100)
        self.add('2026-10-13', level=2, seconds=200)
        self.add('2026-10-06', level=3)  # Outside the past seven days.
        html = render_report(self.student, store.list_sessions(self.sid), today=date(2026, 10, 13))
        self.assertIn('Oct 07 – Oct 13, 2026', html)
        self.assertIn('100%', html)
        self.assertIn('<strong>60</strong>', html)
        self.assertIn('Across 2 levels', html)
        self.assertIn('Addition: single digits (sums to 9)', html)
        self.assertIn('Addition: single digits (sums to 18)', html)
        self.assertNotIn('<td>Level 3</td>', html)
        self.assertNotIn('s / exercise', html)
        self.assertNotIn('<th>Time</th>', html)
        self.assertNotIn('slower', html)
        timed = render_report(self.student, store.list_sessions(self.sid), today=date(2026, 10, 13), show_timing=True)
        self.assertIn('s / exercise', timed)
        self.assertIn('<th>Time</th>', timed)

    def test_archived_weeks_and_boundary_dates(self):
        self.add('2026-10-04', variant=1)  # Sunday of the previous week.
        self.add('2026-10-05', variant=2)
        self.add('2026-10-11', variant=3)
        self.add('2026-10-12', variant=4)
        weeks = store.report_weeks(self.sid)
        self.assertEqual([w['start'] for w in weeks], ['2026-10-12', '2026-10-05', '2026-09-28'])
        html = render_report(self.student, store.list_sessions(self.sid), today=date(2026, 10, 13), week_start='2026-10-05')
        self.assertIn('<td>2026-10-05</td>', html)
        self.assertIn('<td>2026-10-11</td>', html)
        self.assertNotIn('<td>2026-10-04</td>', html)
        self.assertNotIn('<td>2026-10-12</td>', html)
        rc, result = self.command('export-report', {'student_id': self.sid, 'week_start': '2026-09-14'})
        self.assertEqual(rc, 1)
        self.assertFalse(result['ok'])
        with self.assertRaises(ValueError):
            render_report(self.student, [], week_start='2026-10-06')

    def test_reminders_default_off_and_require_consent(self):
        self.assertFalse(self.student['weekly_reminder'])
        self.assertFalse(self.student['missed_reminder'])
        self.assertFalse(self.student['notification_consent'])
        with self.assertRaises(ValueError):
            store.set_student_options(self.sid, {'weekly_reminder': True})
        s = store.set_student_options(self.sid, {'notification_consent': True, 'weekly_reminder': True})
        self.assertTrue(s['weekly_reminder'])
        self.assertFalse(s['missed_reminder'])
        s = store.set_student_options(self.sid, {'notification_consent': False})
        self.assertFalse(s['weekly_reminder'])
        self.assertFalse(s['missed_reminder'])

    def test_parent_day_count_and_time_and_daily_deduplication(self):
        self.add('2026-10-09')
        store.set_student_options(self.sid, {'notification_consent': True,
            'weekly_reminder': True, 'missed_reminder': True, 'missed_days': 3, 'reminder_time': '19:15'})
        sent = []
        sender = lambda title, body: sent.append((title, body))
        self.assertEqual(check_reminders(datetime(2026, 10, 12, 19, 14), sender), 0)
        self.assertEqual(check_reminders(datetime(2026, 10, 12, 19, 15), sender), 2)
        self.assertEqual(check_reminders(datetime(2026, 10, 12, 20), sender), 0)
        self.assertEqual(check_reminders(datetime(2026, 10, 13, 19, 15), sender), 1)
        self.add('2026-10-13', variant=2)
        self.assertEqual(check_reminders(datetime(2026, 10, 14, 19, 15), sender), 0)
        for opts in ({'missed_days': 0}, {'missed_days': 366}, {'reminder_time': '24:00'}, {'reminder_time': '8:00'}):
            with self.assertRaises(ValueError):
                store.set_student_options(self.sid, opts)

    def test_notification_failure_can_retry_and_one_day_threshold(self):
        self.add('2026-10-12')
        store.set_student_options(self.sid, {'notification_consent': True,
            'missed_reminder': True, 'missed_days': 1, 'reminder_time': '08:00'})
        def failed(*args):
            raise RuntimeError('notifications unavailable')
        now = datetime(2026, 10, 13, 8)
        self.assertEqual(check_reminders(now, failed), 0)
        self.assertEqual(check_reminders(now, lambda *args: None), 1)
        self.assertEqual(check_reminders(now, lambda *args: None), 0)

    def test_pending_reprint_keeps_original_paper_examples_and_problem_count(self):
        rc, first = self.command('generate', {'student_id': self.sid, 'level': 1, 'variant': 1, 'examples': False, 'paper': 'a4'})
        self.assertEqual(rc, 0)
        original_count = first['generated']['problem_count']
        store.set_setting('examples', '1')
        store.set_setting('paper', 'letter')
        self.assertEqual([r['sheet_code'] for r in store.pending_sheets(self.sid)], ['1-1'])
        rc, reprinted = self.command('reprint-pending', {'sheet_code': '1-1'})
        self.assertEqual(rc, 0)
        self.assertEqual(reprinted['generated']['problem_count'], original_count)
        last = store.latest_sheet('1-1', self.sid)
        self.assertEqual(last['paper'], 'a4')
        self.assertFalse(last['examples'])
        self.assertEqual(len(store.pending_sheets(self.sid)), 1)
        self.add('2026-10-13', total=original_count, correct=original_count)
        self.assertEqual(store.pending_sheets(self.sid), [])
        rc, result = self.command('reprint-pending', {'sheet_code': '1-1'})
        self.assertEqual(rc, 1)

    def test_all_motif_worksheets_preserve_the_problem_plan(self):
        level = LEVEL_BY_NUM[2]
        plain = generate_one(level, 1, self.tmp.name, paper_size('letter'), examples=False)
        for motif in ('flowers', 'unicorns', 'butterflies', 'sports', 'cars', 'airplanes'):
            themed = generate_one(level, 1, self.tmp.name, paper_size('letter'), examples=False, motif=motif)
            self.assertEqual(themed.problem_count, plain.problem_count)
            self.assertTrue(Path(themed.pdf_path).exists())
            self.assertNotEqual(themed.pdf_path, plain.pdf_path)
        self.assertEqual(len(MESSAGES), 52)
        self.assertEqual(len(set(MESSAGES)), 52)
        self.assertEqual(weekly_message(date(2026, 10, 13)), weekly_message(date(2026, 10, 14)))


if __name__ == '__main__':
    unittest.main()
