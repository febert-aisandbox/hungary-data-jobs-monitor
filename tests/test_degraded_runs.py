import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from profession_monitor.cli import main
from profession_monitor.delivery import decide_delivery
from profession_monitor.models import Job
from profession_monitor.report import build_snapshot
from profession_monitor.storage import Store


def job(job_id="1"):
    return Job(job_id, f"https://www.profession.hu/allas/data-analyst-{job_id}", "Data Analyst", "ACME", "Budapest", "", "", "SQL Python")


class DegradedRunTests(unittest.TestCase):
    def test_degraded_run_adds_observed_jobs_without_expiring_unobserved_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(str(Path(td) / "market.db"))
            store.record_successful_run({"good": [job("old")]}, 1, observed_at="2026-08-26T04:30:00+00:00")

            run = store.record_degraded_run({"good": [job("new")]}, 2, failed_searches=["broken"], observed_at="2026-08-28T04:30:00+00:00")

            self.assertEqual(run.status, "degraded")
            self.assertEqual(run.new_ids, ["new"])
            self.assertEqual(run.expired_ids, [])
            self.assertEqual({item["job_id"] for item in store.active_jobs()}, {"old", "new"})
            self.assertEqual(store.latest_reportable_on("2026-08-28").run_id, run.run_id)
            store.close()

    def test_snapshot_discloses_failed_searches_and_delivery_accepts_it(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(str(Path(td) / "market.db"))
            run = store.record_degraded_run({"good": [job()]}, 2, failed_searches=["broken"], observed_at="2026-08-28T04:30:00+00:00")

            snapshot = build_snapshot(store, run, failed_searches=["broken"], expected_queries=2)
            output = decide_delivery(datetime(2026, 8, 28, 7, 30, tzinfo=ZoneInfo("Europe/Budapest")), snapshot)

            self.assertEqual(snapshot["status"], "degraded")
            self.assertEqual(snapshot["completed_queries"], 1)
            self.assertEqual(snapshot["expected_queries"], 2)
            self.assertEqual(snapshot["failed_searches"], ["broken"])
            self.assertIn("Partial coverage", output)
            self.assertIn("1/2 searches", output)
            store.close()

    def test_degraded_coverage_survives_report_reconstruction_after_a_crash(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(str(Path(td) / "market.db"))
            run = store.record_degraded_run({"good": [job()]}, 2, failed_searches=["broken"], observed_at="2026-08-28T04:30:00+00:00")

            rebuilt = store.latest_reportable_on("2026-08-28")
            snapshot = build_snapshot(store, rebuilt)

            self.assertEqual(rebuilt.run_id, run.run_id)
            self.assertEqual(snapshot["completed_queries"], 1)
            self.assertEqual(snapshot["expected_queries"], 2)
            self.assertEqual(snapshot["failed_searches"], ["broken"])
            store.close()

    def test_delivery_rejects_degraded_snapshot_without_valid_coverage_counts(self):
        snapshot = {
            "report_date": "2026-08-28", "status": "degraded", "active_total": 1,
            "new_total": 1, "expired_total": 0, "junior_total": 0,
            "hybrid_remote_total": 0, "role_families": {}, "new_jobs": [],
        }

        output = decide_delivery(datetime(2026, 8, 28, 7, 30, tzinfo=ZoneInfo("Europe/Budapest")), snapshot)

        self.assertIn("report is not available", output)

    def test_delivery_rejects_degraded_snapshot_that_claims_expirations(self):
        snapshot = {
            "report_date": "2026-08-28", "status": "degraded", "active_total": 1,
            "new_total": 0, "expired_total": 1, "junior_total": 0,
            "hybrid_remote_total": 0, "role_families": {}, "new_jobs": [],
            "completed_queries": 1, "expected_queries": 2,
        }

        output = decide_delivery(datetime(2026, 8, 28, 7, 30, tzinfo=ZoneInfo("Europe/Budapest")), snapshot)

        self.assertIn("report is not available", output)

    def test_cli_publishes_degraded_report_when_at_least_one_query_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "searches.json"
            config.write_text(json.dumps({"queries": ["good", "broken"], "max_pages_per_query": 1, "delay_seconds": 0}))
            output = root / "docs"
            db = root / "market.db"
            with patch("profession_monitor.cli.collect_queries", return_value=({"good": [job()]}, ["broken: HTTPError: HTTP Error 404: Not Found"])):
                result = main(["--config", str(config), "--db", str(db), "--output", str(output), "--skip-robots-check"])

            snapshot = json.loads((output / "daily.json").read_text())
            self.assertEqual(result, 5)
            self.assertEqual(snapshot["status"], "degraded")
            self.assertEqual(snapshot["failed_searches"], ["broken"])

    def test_cli_retries_after_a_degraded_report_and_can_replace_it_with_full_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "searches.json"
            config.write_text(json.dumps({"queries": ["good", "broken"], "max_pages_per_query": 1, "delay_seconds": 0}))
            args = ["--config", str(config), "--db", str(root / "market.db"), "--output", str(root / "docs"), "--skip-robots-check"]
            results = [
                ({"good": [job("1")]}, ["broken: HTTPError: HTTP Error 404: Not Found"]),
                ({"good": [job("1")], "broken": []}, []),
            ]
            with patch("profession_monitor.cli.collect_queries", side_effect=results) as collect:
                first = main(args)
                second = main(args)

            snapshot = json.loads((root / "docs" / "daily.json").read_text())
            self.assertEqual(first, 5)
            self.assertEqual(second, 0)
            self.assertEqual(collect.call_count, 2)
            self.assertEqual(snapshot["status"], "success")

    def test_cli_publishes_at_most_once_per_budapest_date(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "searches.json"
            config.write_text(json.dumps({"queries": ["good", "broken"], "max_pages_per_query": 1, "delay_seconds": 0}))
            args = ["--config", str(config), "--db", str(root / "market.db"), "--output", str(root / "docs"), "--skip-robots-check", "--publish"]
            responses = [
                ({"good": [job("1")]}, ["broken: HTTPError: HTTP Error 404: Not Found"]),
                ({"good": [job("1")], "broken": [job("2")]}, []),
            ]
            with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}), \
                 patch("profession_monitor.cli.datetime") as clock, \
                 patch("profession_monitor.cli.collect_queries", side_effect=responses) as collect, \
                 patch("profession_monitor.cli._publish_artifacts", return_value={"commit": "test-commit"}) as publish:
                clock.now.return_value = datetime(2026, 8, 28, 7, 0, tzinfo=ZoneInfo("Europe/Budapest"))
                first = main(args)
                second = main(args)
                clock.now.return_value = datetime(2026, 8, 29, 7, 0, tzinfo=ZoneInfo("Europe/Budapest"))
                next_day = main(args)

            self.assertEqual(first, 5)
            self.assertEqual(second, 0)
            self.assertEqual(next_day, 0)
            self.assertEqual(collect.call_count, 2)
            self.assertEqual(publish.call_count, 2)

    def test_existing_published_report_counts_toward_daily_limit_after_upgrade(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "market.db"
            store = Store(str(db))
            run = store.record_degraded_run({"good": [job()]}, 2, failed_searches=["broken"], observed_at="2026-08-28T04:30:00+00:00")
            store.save_report(run.run_id, build_snapshot(store, run, failed_searches=["broken"], expected_queries=2))
            store.mark_published(run.run_id)
            store.close()
            config = root / "searches.json"
            config.write_text(json.dumps({"queries": ["good", "broken"], "max_pages_per_query": 1, "delay_seconds": 0}))
            args = ["--config", str(config), "--db", str(db), "--output", str(root / "docs"), "--skip-robots-check", "--publish"]
            with patch("profession_monitor.cli.datetime") as clock, \
                 patch("profession_monitor.cli.collect_queries") as collect, \
                 patch("profession_monitor.cli._publish_artifacts") as publish:
                clock.now.return_value = datetime(2026, 8, 28, 7, 0, tzinfo=ZoneInfo("Europe/Budapest"))
                result = main(args)

            self.assertEqual(result, 0)
            collect.assert_not_called()
            publish.assert_not_called()

    def test_publish_budget_is_consumed_before_uncertain_remote_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "searches.json"
            config.write_text(json.dumps({"queries": ["good", "broken"], "max_pages_per_query": 1, "delay_seconds": 0}))
            args = ["--config", str(config), "--db", str(root / "market.db"), "--output", str(root / "docs"), "--skip-robots-check", "--publish"]
            response = ({"good": [job()]}, ["broken: HTTPError: HTTP Error 404: Not Found"])
            with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}), \
                 patch("profession_monitor.cli.datetime") as clock, \
                 patch("profession_monitor.cli.collect_queries", return_value=response) as collect, \
                 patch("profession_monitor.cli._publish_artifacts", side_effect=RuntimeError("connection lost after request")) as publish:
                clock.now.return_value = datetime(2026, 8, 28, 7, 0, tzinfo=ZoneInfo("Europe/Budapest"))
                with self.assertRaisesRegex(RuntimeError, "connection lost"):
                    main(args)
                retry = main(args)

            self.assertEqual(retry, 0)
            self.assertEqual(collect.call_count, 1)
            self.assertEqual(publish.call_count, 1)


if __name__ == "__main__":
    unittest.main()
