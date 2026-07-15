import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from profession_monitor.delivery import decide_delivery


TZ=ZoneInfo("Europe/Budapest")
SNAPSHOT={
    "report_date":"2026-07-15","status":"success","active_total":12,"new_total":3,
    "expired_total":1,"junior_total":2,"hybrid_remote_total":4,
    "role_families":{"Data analyst":8,"Data engineer":4},"new_jobs":[],
    "site_url":"https://febert-aisandbox.github.io/hungary-data-jobs-monitor/"
}


class DeliveryTests(unittest.TestCase):
    def test_is_silent_outside_exact_local_delivery_minute(self):
        self.assertEqual(decide_delivery(datetime(2026,7,15,7,29,tzinfo=TZ),SNAPSHOT),"")
        self.assertEqual(decide_delivery(datetime(2026,7,15,7,31,tzinfo=TZ),SNAPSHOT),"")

    def test_delivers_fresh_report_at_0730_budapest(self):
        output=decide_delivery(datetime(2026,7,15,5,30,tzinfo=timezone.utc),SNAPSHOT)
        self.assertIn("Hungary data jobs",output)
        self.assertIn("Observed: **12**",output)

    def test_sends_stale_alert_at_delivery_time(self):
        output=decide_delivery(datetime(2026,7,15,7,30,tzinfo=TZ),None)
        self.assertIn("report is not available",output)

    def test_rejects_invalid_snapshot_shape_as_stale(self):
        output=decide_delivery(datetime(2026,7,15,7,30,tzinfo=TZ),[])
        self.assertIn("report is not available",output)

    def test_digest_never_renders_untrusted_role_or_job_fields(self):
        snapshot={**SNAPSHOT,"role_families":{"\\[Injected\\]\\(https://evil.example\\)":1},"new_jobs":[{"title":"Injected job","url":"https://profession.hu/x) [Injected](https://profession.hu/y","company":"x"}]}
        output=decide_delivery(datetime(2026,7,15,7,30,tzinfo=TZ),snapshot)
        self.assertNotIn("Injected",output)
        self.assertNotIn("evil.example",output)
        self.assertLessEqual(len(output),3900)



if __name__ == "__main__": unittest.main()
