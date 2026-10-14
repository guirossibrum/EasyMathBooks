import os
import unittest
from datetime import date
from tempfile import TemporaryDirectory

import store


class ProgressReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        os.environ["XDG_DATA_HOME"] = self.tmp.name
        store.init_db()
        self.student = store.add_student("Test Kid")
        self.sid = self.student["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, taken, seconds, score, score_max=25, level=1, variant=1):
        return store.add_session(
            self.sid, f"{level}-{variant}", level, variant, taken,
            seconds, score=score, score_max=score_max,
        )

    def test_empty_student(self):
        report = store.progress_report(self.sid, today=date(2026, 10, 13))
        self.assertFalse(report["has_data"])
        self.assertEqual(report["today_count"], 0)
        self.assertIsNone(report["accuracy_pct"])

    def test_no_student(self):
        report = store.progress_report(None, today=date(2026, 10, 13))
        self.assertFalse(report["has_data"])

    def test_volume_skips_accuracy_and_speed(self):
        # Week of Monday 2026-10-05. Today is Friday 2026-10-09.
        self.add("2026-10-05", 180, 20, variant=1)  # Mon 3:00
        self.add("2026-10-06", 150, 22, variant=2)  # Tue 2:30
        self.add("2026-10-08", 135, 24, variant=3)  # Thu 2:15
        report = store.progress_report(self.sid, today=date(2026, 10, 9))

        self.assertTrue(report["has_data"])
        self.assertEqual(report["today_count"], 0)
        self.assertEqual(report["week_count"], 3)
        # First session Mon. Skipped Wed 7 and Fri 9 (today). Sat/Sun are future.
        self.assertEqual(report["week_skipped"], 2)
        self.assertEqual(report["correct"], 66)
        self.assertEqual(report["possible"], 75)
        self.assertEqual(report["accuracy_pct"], 88.0)
        # Last practice was yesterday (Thu), so streak is 1.
        self.assertEqual(report["streak"], 1)

        level = report["levels"][0]
        self.assertEqual(level["trend"], "faster")
        self.assertEqual(level["first_seconds"], 180)
        self.assertEqual(level["last_seconds"], 135)
        self.assertEqual(level["faster_pct"], 25)
        self.assertIn("25% faster", level["pace_label"])
        self.assertIn("/ exercise", level["pace_label"])
        self.assertEqual(len(level["spark"]), 3)
        self.assertGreater(level["spark"][0]["height"], level["spark"][-1]["height"])

        week_days = {d["weekday"]: d for d in report["week_days"]}
        self.assertEqual(week_days["Mon"]["count"], 1)
        self.assertTrue(week_days["Wed"]["skipped"])
        self.assertTrue(week_days["Fri"]["skipped"])
        self.assertFalse(week_days["Sat"]["skipped"])
        self.assertTrue(week_days["Sat"]["future"])

    def test_streak_includes_today(self):
        self.add("2026-10-07", 120, 25, variant=1)
        self.add("2026-10-08", 110, 25, variant=2)
        self.add("2026-10-09", 100, 25, variant=3)
        report = store.progress_report(self.sid, today=date(2026, 10, 9))
        self.assertEqual(report["streak"], 3)
        self.assertEqual(report["week_skipped"], 0)

    def test_days_before_first_session_are_not_skipped(self):
        self.add("2026-10-09", 90, 25, variant=1)
        report = store.progress_report(self.sid, today=date(2026, 10, 9))
        monday = report["week_days"][0]
        self.assertEqual(monday["weekday"], "Mon")
        self.assertTrue(monday["before_start"])
        self.assertFalse(monday["skipped"])

    def test_pace_uses_time_per_exercise(self):
        # Same 3:00 wall time: example page (25) vs full page (35).
        self.add("2026-10-05", 180, 25, score_max=25, variant=1)
        self.add("2026-10-06", 180, 35, score_max=35, variant=2)
        report = store.progress_report(self.sid, today=date(2026, 10, 6))
        level = report["levels"][0]
        self.assertAlmostEqual(level["first_each"], 180 / 25, places=3)
        self.assertAlmostEqual(level["last_each"], 180 / 35, places=3)
        self.assertEqual(level["trend"], "faster")
        self.assertGreater(level["spark"][0]["height"], level["spark"][1]["height"])
        self.assertIn("/ exercise", level["pace_label"])

    def test_pace_follows_sheet_number_not_save_order(self):
        self.add("2026-10-06", 180, 35, score_max=35, variant=2)
        self.add("2026-10-07", 150, 25, score_max=25, variant=1)
        report = store.progress_report(self.sid, today=date(2026, 10, 7))
        level = report["levels"][0]
        self.assertEqual([p["sheet_code"] for p in level["spark"]], ["1-1", "1-2"])
        self.assertAlmostEqual(level["first_each"], 150 / 25, places=3)
        self.assertAlmostEqual(level["last_each"], 180 / 35, places=3)


class ProgressPointerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        os.environ["XDG_DATA_HOME"] = self.tmp.name
        store.init_db()
        self.student = store.add_student("Test Kid")
        self.sid = self.student["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_student_starts_at_1_1(self):
        pointer = store.student_progress_pointer(self.sid)
        self.assertEqual(pointer, {"level": 1, "variant": 1})

    def test_next_seed_after_finished_sessions(self):
        store.add_session(self.sid, "1-1", 1, 1, "2026-10-01", 180, score=25, score_max=25)
        store.add_session(self.sid, "1-2", 1, 2, "2026-10-02", 150, score=25, score_max=25)
        pointer = store.student_progress_pointer(self.sid)
        self.assertEqual(pointer["level"], 1)
        self.assertEqual(pointer["variant"], 3)

    def test_highest_level_wins(self):
        store.add_session(self.sid, "1-4", 1, 4, "2026-10-01", 180, score=20, score_max=25)
        store.add_session(self.sid, "2-1", 2, 1, "2026-10-02", 200, score=18, score_max=20)
        pointer = store.student_progress_pointer(self.sid)
        self.assertEqual(pointer["level"], 2)
        self.assertEqual(pointer["variant"], 2)

    def test_generated_sheet_advances_seed(self):
        store.record_sheet("2-3", 2, 3, 20, "letter", True, "/tmp/a.pdf", None, self.sid)
        pointer = store.student_progress_pointer(self.sid)
        self.assertEqual(pointer["level"], 2)
        self.assertEqual(pointer["variant"], 4)

    def test_finished_level_beats_a_higher_generated_level(self):
        store.add_session(self.sid, "1-1", 1, 1, "2026-10-01", 90, score=25, score_max=25)
        store.record_sheet("2-3", 2, 3, 20, "letter", True, "/tmp/a.pdf", None, self.sid)
        pointer = store.student_progress_pointer(self.sid)
        self.assertEqual(pointer["level"], 1)
        self.assertEqual(pointer["variant"], 2)


class SaveSessionScoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        os.environ["XDG_DATA_HOME"] = self.tmp.name
        import importlib
        import cli
        importlib.reload(store)
        importlib.reload(cli)
        self.cli = cli
        store.init_db()
        self.student = store.add_student("Test Kid")
        self.sid = self.student["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_keeps_full_score(self):
        store.set_setting("student_id", self.sid)
        store.set_setting("level", 1)
        store.set_setting("variant", 1)
        rc = self.cli.cmd_save_session({
            "student_id": self.sid,
            "level": 1,
            "variant": 1,
            "duration_seconds": 90,
            "score": 25,
            "score_max": 25,
        })
        self.assertEqual(rc, 0)
        rows = store.list_sessions(self.sid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["score"], 25)
        self.assertEqual(rows[0]["score_max"], 25)
        self.assertEqual(store.get_setting("variant"), "2")

    def test_picking_student_jumps_to_next_seed(self):
        store.add_session(self.sid, "1-1", 1, 1, "2026-10-01", 90, score=25, score_max=25)
        store.set_setting("student_id", "")
        store.set_setting("level", 5)
        store.set_setting("variant", 9)
        settings = self.cli.persist_selection(
            {"student_id": self.sid, "level": 5, "variant": 9},
            self.cli.current_settings(),
        )
        self.assertEqual(settings["level"], 1)
        self.assertEqual(settings["variant"], 2)

    def test_snapshot_uses_recorded_problem_count(self):
        store.record_sheet("2-2", 2, 2, 35, "letter", False, "/tmp/x.pdf", None, self.sid)
        store.set_setting("student_id", self.sid)
        store.set_setting("level", 2)
        store.set_setting("variant", 2)
        store.set_setting("examples", "1")
        data = self.cli.snapshot(self.cli.current_settings())
        self.assertEqual(data["sheet_code"], "2-2")
        self.assertEqual(data["problem_count"], 35)


if __name__ == "__main__":
    unittest.main()

