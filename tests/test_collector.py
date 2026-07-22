import json
import re
import unittest
from pathlib import Path
from profession_monitor.collector import build_search_url, collect_queries, validate_response

CONFIG = Path(__file__).parents[1] / "config" / "searches.json"

def make_page(total,start,count):
    cards="".join(f'<li class="advertisement-result-list-item" data-prof-id="{i}" data-link="https://www.profession.hu/allas/data-analyst-{i}" data-item-name="Data Analyst" data-item-brand="ACME" data-location-id="Budapest">SQL</li>' for i in range(start,start+count))
    return f'<html><title>{total} állásajánlat</title><ul>{cards}</ul></html>'

def page_number(url):
    return int(re.search(r"/(\d+),0,0,",url).group(1))

FIXTURE=(Path(__file__).parent/"fixtures"/"search_page.html").read_text()

class CollectorTests(unittest.TestCase):
    def test_production_queries_exclude_broken_accented_keyword(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertNotIn("adattudós", config["queries"])
        self.assertEqual(len(config["queries"]), 11)

    def test_production_pagination_ceiling_is_30_pages(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["max_pages_per_query"], 30)

    def test_30_page_ceiling_covers_401_result_query(self):
        calls=[]
        def fetch(url):
            page=page_number(url)
            calls.append(page)
            count=20 if page<=20 else 1
            return make_page(401,(page-1)*20+1,count)

        result,errors=collect_queries(["business intelligence"],30,fetch)

        self.assertEqual(errors,[])
        self.assertIn("business intelligence",result)
        self.assertEqual(calls,list(range(1,22)))

    def test_30_page_ceiling_rejects_601_result_query(self):
        calls=[]
        def fetch(url):
            page=page_number(url)
            calls.append(page)
            return make_page(601,(page-1)*20+1,20)

        result,errors=collect_queries(["business intelligence"],30,fetch)

        self.assertEqual(result,{})
        self.assertTrue(any("query truncated after 30 pages" in error for error in errors))
        self.assertEqual(calls,list(range(1,31)))

    def test_builds_encoded_profession_search_url(self):
        url=build_search_url("data analyst",2)
        self.assertIn("/data-analyst/2,0,0,data+analyst",url)

    def test_collects_and_classifies_one_page(self):
        called=[]
        def fetch(url): called.append(url); return FIXTURE.replace("42 állásajánlat", "2 állásajánlat")
        result,errors=collect_queries(["data analyst"],1,fetch)
        self.assertEqual(errors,[])
        self.assertEqual(len(result["data analyst"]),2)
        self.assertEqual(len(called),1)

    def test_excludes_foreign_only_locations_from_hungary_report(self):
        foreign=FIXTURE.replace("42 állásajánlat", "2 állásajánlat").replace('data-location-id="Pest_megye"','data-location-id="Németország"').replace('data-location-id="Budapest"','data-location-id="Svájc"')
        result,errors=collect_queries(["data analyst"],1,lambda _: foreign)
        self.assertEqual(errors,[])
        self.assertEqual(result["data analyst"],[])

    def test_flags_unexplained_short_page_as_incomplete(self):
        result,errors=collect_queries(["data analyst"],3,lambda _: FIXTURE)
        self.assertEqual(result,{})
        self.assertTrue(any("short page" in error for error in errors))

    def test_rejects_result_total_drift_between_pages(self):
        def fetch(url):
            return make_page(21,1,20) if "/1,0,0," in url else make_page(20,21,1)
        result,errors=collect_queries(["data analyst"],2,fetch)
        self.assertEqual(result,{})
        self.assertTrue(any("result total changed" in error for error in errors))

    def test_validates_redirect_host_and_content_type(self):
        validate_response("https://www.profession.hu/allasok/x","text/html",False)
        with self.assertRaises(ValueError): validate_response("https://evil.example/x","text/html",False)
        with self.assertRaises(ValueError): validate_response("https://www.profession.hu/allasok/x","application/json",False)

    def test_rejects_short_final_page(self):
        result,errors=collect_queries(["data analyst"],1,lambda _: make_page(19,1,2))
        self.assertEqual(result,{})
        self.assertTrue(any("expected 19 cards" in error for error in errors))

    def test_deduplicates_cross_page_overlap(self):
        def fetch(url): return make_page(40,1,20) if "/1,0,0," in url else make_page(40,11,20)
        result,errors=collect_queries(["data analyst"],2,fetch)
        self.assertEqual(errors,[])
        self.assertEqual(len(result["data analyst"]),30)

if __name__ == "__main__": unittest.main()
