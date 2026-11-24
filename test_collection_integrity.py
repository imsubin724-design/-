import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cloud_daily as daily
from data_store import save_ranking, today_kst, validate_ranking


class CollectionIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = dict(daily.SOURCES[0])
        self.rows = [[rank, f"Product {rank}", f"/i/{rank}", "", ""] for rank in range(1, 7)]
        self.patches = [patch.object(daily, "ROOT", self.root),
                        patch.object(daily, "SOURCES", (self.source,)),
                        patch.object(daily, "COLLECTION_STATUS_PATH", self.root / "collection_status.json")]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def archive(self, rows=None):
        save_ranking(self.root / f"ranking_{today_kst()}.csv", rows or self.rows)
        save_ranking(self.root / "today.csv", rows or self.rows)

    def test_rejects_duplicates_without_overwriting_good_file(self):
        self.archive()
        before = (self.root / "today.csv").read_bytes()
        bad = [row[:] for row in self.rows]
        bad[1][2] = bad[0][2]
        with self.assertRaises(ValueError):
            save_ranking(self.root / "today.csv", bad)
        self.assertEqual(before, (self.root / "today.csv").read_bytes())

    def test_current_requires_archive_and_history_and_matching_ranks(self):
        self.archive()
        self.assertFalse(daily.source_is_current(self.source))
        daily.sync_trend_history()
        self.assertTrue(daily.source_is_current(self.source))
        save_ranking(self.root / "today.csv", list(reversed(self.rows)))
        self.assertTrue(daily.source_is_current(self.source))
        changed = [row[:] for row in self.rows]
        changed[0][2] = "/i/other"
        save_ranking(self.root / "today.csv", changed)
        self.assertFalse(daily.source_is_current(self.source))

    def test_retry_saves_and_verifies_history(self):
        calls = []
        def collect(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("Temporary site failure")
            self.archive()
        with patch.object(daily.subprocess, "run", side_effect=collect), patch.object(daily.time, "sleep"):
            result = daily.collect()
        self.assertEqual(2, len(calls))
        self.assertEqual("success", result[0]["status"])
        self.assertTrue(daily.source_is_current(self.source))

    def test_failed_collection_does_not_invent_today(self):
        save_ranking(self.root / "today.csv", self.rows)
        with patch.object(daily.subprocess, "run", side_effect=RuntimeError("Site failure")), patch.object(daily.time, "sleep"):
            result = daily.collect()
        self.assertEqual("failed", result[0]["status"])
        self.assertFalse(daily.source_is_current(self.source))
        self.assertIn("오늘 순위·누적 저장이 확인되지", daily.collection_notice())

    def test_recollection_replaces_ranks_and_keeps_saved_tags(self):
        self.archive()
        daily.sync_trend_history()
        history = daily.read_rows(self.root / "trend_history.csv")
        history[0]["color"] = "Saved color"
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=daily.HISTORY_FIELDS)
        writer.writeheader()
        writer.writerows(history)
        (self.root / "trend_history.csv").write_text(output.getvalue(), encoding="utf-8-sig")
        changed = [row[:] for row in self.rows]
        changed[1][2] = "/i/new"
        self.archive(changed)
        daily.sync_trend_history()
        daily.sync_trend_history()
        history = daily.read_rows(self.root / "trend_history.csv")
        validate_ranking(history)
        self.assertEqual("Saved color", history[0]["color"])
        self.assertTrue(daily.source_is_current(self.source))

    def test_partial_history_is_repaired_on_retry(self):
        self.archive()
        daily.sync_trend_history()
        path = self.root / "trend_history.csv"
        lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        path.write_text("".join(lines[:-1]), encoding="utf-8-sig")
        self.assertFalse(daily.source_is_current(self.source))
        daily.sync_trend_history()
        self.assertTrue(daily.source_is_current(self.source))

    def test_remote_save_failure_remains_visible_after_collection(self):
        self.archive()
        daily.sync_trend_history()
        with patch.dict(daily.os.environ, {"LENS_PERSISTENCE_STATUS": "failure"}):
            self.assertIn("GitHub 영구 저장 실패", daily.collection_notice())


if __name__ == "__main__":
    unittest.main()
