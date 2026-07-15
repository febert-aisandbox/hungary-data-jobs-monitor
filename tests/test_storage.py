import tempfile, unittest
from profession_monitor.models import Job
from profession_monitor.storage import Store

def job(job_id="1"):
    return Job(job_id, f"https://example/{job_id}", "Data Analyst", "ACME", "Budapest", "", "", "SQL Python")

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db")
        self.store = Store(self.tmp.name)

    def tearDown(self): self.store.close(); self.tmp.close()

    def test_first_sighting_is_new_and_repeat_is_not_duplicate(self):
        r1 = self.store.record_successful_run({"q": [job()]}, expected_queries=1)
        r2 = self.store.record_successful_run({"q": [job()]}, expected_queries=1)
        self.assertEqual(r1.new_ids, ["1"])
        self.assertEqual(r2.new_ids, [])
        self.assertEqual(self.store.active_count(), 1)

    def test_two_distinct_daily_misses_expire_but_partial_and_same_day_runs_do_not(self):
        self.store.record_successful_run({"q": [job()]}, expected_queries=1, observed_at="2026-07-15T06:00:00+00:00")
        self.store.record_partial_run({"q": [job("2")]})
        self.assertEqual(self.store.active_count(), 1)
        self.store.record_successful_run({"q": []}, expected_queries=1, observed_at="2026-07-16T06:00:00+00:00")
        self.store.record_successful_run({"q": []}, expected_queries=1, observed_at="2026-07-16T07:00:00+00:00")
        self.assertEqual(self.store.active_count(), 1)
        result = self.store.record_successful_run({"q": []}, expected_queries=1, observed_at="2026-07-17T06:00:00+00:00")
        self.assertEqual(result.expired_ids, ["1"])
        self.assertEqual(self.store.active_count(), 0)

    def test_partial_run_does_not_create_or_reactivate_jobs(self):
        self.store.record_partial_run({"q": [job()]}, expected_queries=1)
        self.assertEqual(self.store.active_count(), 0)

    def test_query_overlap_deduplicates(self):
        self.store.record_successful_run({"a": [job()], "b": [job()]}, expected_queries=2)
        self.assertEqual(self.store.active_count(), 1)

    def test_successful_run_can_be_reconstructed_and_report_persisted(self):
        run=self.store.record_successful_run({"q": [job()]},1,observed_at="2026-07-15T06:00:00+00:00")
        rebuilt=self.store.latest_success_on("2026-07-15")
        self.assertEqual(rebuilt.new_ids,run.new_ids)
        payload={"report_date":"2026-07-15","active_total":1}
        self.store.save_report(run.run_id,payload)
        self.assertEqual(self.store.report_on("2026-07-15"),payload)

if __name__ == "__main__": unittest.main()
