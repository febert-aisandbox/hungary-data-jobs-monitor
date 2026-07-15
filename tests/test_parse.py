import unittest
from pathlib import Path

from profession_monitor.parse import parse_search_page, normalize_url

FIXTURE = Path(__file__).parent / "fixtures" / "search_page.html"

class ParseTests(unittest.TestCase):
    def test_extracts_and_normalizes_jobs(self):
        result = parse_search_page(FIXTURE.read_text())
        self.assertEqual(result.total_results, 42)
        self.assertEqual(len(result.jobs), 2)
        first = result.jobs[0]
        self.assertEqual(first.job_id, "2949418")
        self.assertEqual(first.title, "Master Data Analyst")
        self.assertEqual(first.company, "Example Kft")
        self.assertEqual(first.location, "Pest_megye")
        self.assertEqual(first.url, "https://www.profession.hu/allas/master-data-analyst-example-2949418")
        self.assertIn("SQL", first.card_text)

    def test_rejects_page_without_job_cards(self):
        with self.assertRaises(ValueError):
            parse_search_page("<html><title>No jobs</title></html>")

    def test_accepts_only_https_profession_job_urls(self):
        self.assertEqual(normalize_url("/allas/data-analyst-123?x=1"), "https://www.profession.hu/allas/data-analyst-123")
        for value in ("javascript:alert(1)", "https://evil.example/allas/x"):
            with self.assertRaises(ValueError): normalize_url(value)

if __name__ == "__main__": unittest.main()
