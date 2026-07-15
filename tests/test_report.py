import json, tempfile, unittest
from pathlib import Path
from profession_monitor.models import Job
from profession_monitor.storage import Store
from profession_monitor.report import build_snapshot, render_html, render_digest

class ReportTests(unittest.TestCase):
    def test_report_contains_metrics_jobs_and_machine_readable_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(str(Path(td)/"m.db"))
            j = Job("1", "https://profession.hu/allas/x-1", "Data Analyst", "ACME", "Budapest", "1-3 years", "Hibrid", "SQL Python Power BI")
            run = store.record_successful_run({"data analyst": [j]}, expected_queries=1)
            snap = build_snapshot(store, run, "https://example.test/")
            page = render_html(snap)
            digest = render_digest(snap)
            self.assertEqual(snap["active_total"], 1)
            self.assertEqual(snap["hybrid_remote_total"], 1)
            self.assertIn("Data Analyst", page)
            self.assertIn("SQL", page)
            self.assertIn("ACME", digest)
            self.assertLess(len(digest), 2500)
            json.dumps(snap)
            store.close()

if __name__ == "__main__": unittest.main()
