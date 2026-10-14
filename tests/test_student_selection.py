import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cli
import store


class StudentSelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.env = patch.dict(os.environ, XDG_DATA_HOME=self.tmp.name)
        self.env.start()
        store.init_db()
        self.student = store.add_student("Selection Test")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_delayed_selection_cannot_reselect_deleted_student(self):
        sid = self.student["id"]
        store.set_setting("student_id", sid)
        store.delete_student(sid)
        settings = cli.persist_selection({"student_id": sid}, cli.current_settings())
        self.assertIsNone(settings["student_id"])
        self.assertEqual(store.all_settings()["student_id"], "")
        self.assertEqual(cli.snapshot(settings)["students"], [])

    def test_snapshot_clears_stale_selection_consistently(self):
        store.set_setting("student_id", self.student["id"])
        stale = cli.current_settings()
        store.delete_student(self.student["id"])
        data = cli.snapshot(stale)
        self.assertIsNone(data["settings"]["student_id"])
        self.assertFalse(data["report"]["has_data"])

    def test_deleting_other_student_preserves_selection(self):
        other = store.add_student("Other Test")
        store.set_setting("student_id", self.student["id"])
        store.delete_student(other["id"])
        data = cli.snapshot()
        self.assertEqual(data["settings"]["student_id"], self.student["id"])
        self.assertEqual([s["name"] for s in data["students"]], ["Selection Test"])
