import random
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import replace
from typing import Callable

from .classify import classify_job, extract_skills
from .parse import parse_search_page

BASE="https://www.profession.hu"
USER_AGENT="HungaryDataJobsMonitor/1.0 (+https://febert-aisandbox.github.io/hungary-data-jobs-monitor/)"
FOREIGN_ONLY=("németország","svájc","ausztria","románia","szlovákia","csehország","lengyelország","hollandia","egyesült királyság")

def is_hungary_market_job(location: str) -> bool:
    value=location.casefold()
    return not any(country in value for country in FOREIGN_ONLY)

def build_search_url(query: str, page: int) -> str:
    slug="-".join(query.casefold().split())
    return f"{BASE}/allasok/{urllib.parse.quote(slug)}/{page},0,0,{urllib.parse.quote_plus(query)}"

def validate_response(final_url: str, content_type: str, robots: bool):
    parsed=urllib.parse.urlsplit(final_url)
    if parsed.scheme != "https" or parsed.hostname not in {"profession.hu","www.profession.hu"} or parsed.username or parsed.password or parsed.port not in {None,443}:
        raise ValueError("unexpected redirect target")
    allowed={"text/plain","text/html"} if robots else {"text/html","application/xhtml+xml"}
    if content_type.casefold() not in allowed: raise ValueError(f"unexpected Content-Type {content_type}")

def http_fetch(url: str, timeout: int=30) -> str:
    req=urllib.request.Request(url,headers={"User-Agent":USER_AGENT,"Accept-Language":"hu-HU,hu;q=0.9,en;q=0.7"})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            if response.status != 200: raise RuntimeError(f"HTTP {response.status}")
            validate_response(response.geturl(),response.headers.get_content_type(),url.endswith("/robots.txt"))
            return response.read().decode("utf-8","replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (403,429): raise RuntimeError(f"collection aborted after HTTP {exc.code}") from exc
        raise

def robots_allows_search(fetcher: Callable[[str],str]=http_fetch) -> bool:
    robots_url=f"{BASE}/robots.txt"
    parser=urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(fetcher(robots_url).splitlines())
    return parser.can_fetch("HungaryDataJobsMonitor",build_search_url("data analyst",1))

def collect_queries(queries: list[str], max_pages: int, fetcher: Callable[[str],str]=http_fetch, delay_seconds: float=0.0):
    collected: dict[str,list] = {}
    errors=[]
    for query in queries:
        jobs={}
        try:
            signatures=set()
            raw_seen=set()
            fully_covered=False
            expected_total=None
            for page in range(1,max_pages+1):
                if delay_seconds and (collected or page>1): time.sleep(delay_seconds+random.uniform(0,0.8))
                parsed=parse_search_page(fetcher(build_search_url(query,page)))
                if expected_total is None: expected_total=parsed.total_results
                elif parsed.total_results != expected_total: raise ValueError(f"result total changed from {expected_total} to {parsed.total_results} on page {page}")
                signature=tuple(job.job_id for job in parsed.jobs)
                if signature in signatures: raise ValueError(f"repeated page at {page}")
                signatures.add(signature)
                page_ids=set(signature)
                expected_cards=min(20,max(0,expected_total-(page-1)*20))
                if len(page_ids) != expected_cards:
                    kind="short page: " if len(page_ids)<expected_cards else ""
                    raise ValueError(f"{kind}expected {expected_cards} cards on page {page}, got {len(page_ids)}")
                overlap=raw_seen & page_ids
                if overlap: raise ValueError(f"cross-page duplicate IDs on page {page}")
                raw_seen.update(page_ids)
                for job in parsed.jobs:
                    cls=classify_job(job.title,job.card_text)
                    if cls.relevant and is_hungary_market_job(job.location):
                        jobs[job.job_id]=replace(job,family=cls.family,skills=tuple(extract_skills(job.card_text)))
                if page*20>=parsed.total_results:
                    fully_covered=True
                    break
            if not fully_covered:
                raise ValueError(f"query truncated after {max_pages} pages")
            collected[query]=list(jobs.values())
        except Exception as exc:
            errors.append(f"{query}: {type(exc).__name__}: {exc}")
    return collected,errors
