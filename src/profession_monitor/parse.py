import html
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from .models import Job, ParseResult

_CARD_CLASS = "advertisement-result-list-item"


def normalize_url(url: str) -> str:
    parsed = urlsplit(urljoin("https://www.profession.hu", html.unescape(url)))
    if parsed.scheme != "https" or parsed.hostname not in {"profession.hu", "www.profession.hu"} or not parsed.path.startswith("/allas/"):
        raise ValueError("invalid Profession.hu job URL")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


class _CardsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.jobs: list[Job] = []
        self.current: dict[str, str] | None = None
        self.li_depth = 0
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = values.get("class", "").split()
        if self.current is None and tag == "li" and _CARD_CLASS in classes:
            self.current = values
            self.li_depth = 1
            self.text = []
            return
        if self.current is not None and tag == "li":
            self.li_depth += 1

    def handle_data(self, data):
        if self.current is not None:
            value = " ".join(data.split())
            if value:
                self.text.append(value)

    def handle_endtag(self, tag):
        if self.current is None or tag != "li":
            return
        self.li_depth -= 1
        if self.li_depth:
            return
        attrs = self.current
        job_id = attrs.get("data-prof-id") or attrs.get("data-item-id") or ""
        url = attrs.get("data-link", "")
        title = attrs.get("data-item-name", "").strip()
        if job_id and url and title:
            text = " ".join(self.text)
            mode = next((x for x in ("Hibrid", "Távmunka", "Remote", "Home office") if x.casefold() in text.casefold()), "")
            self.jobs.append(Job(
                job_id=job_id,
                url=normalize_url(url),
                title=title,
                company=attrs.get("data-item-brand", "").strip(),
                location=attrs.get("data-location-id", "").strip(),
                seniority=attrs.get("data-category4", "").strip(),
                work_mode=mode,
                card_text=text,
            ))
        self.current = None
        self.text = []


def parse_search_page(source: str) -> ParseResult:
    parser = _CardsParser()
    parser.feed(source)
    if not parser.jobs:
        raise ValueError("Profession.hu parser found zero job cards")
    match = re.search(r"([\d\s]+)\s+(?:állásajánlat|ajánlat)", source, re.I) or re.search(r"-\s*([\d\s]+)\s*db\s*-",source,re.I)
    if match:
        total = int(re.sub(r"\s", "", match.group(1)))
    elif len(parser.jobs)<20:
        total=len(parser.jobs)
    else:
        raise ValueError("Profession.hu total-result marker missing")
    unique = {job.job_id: job for job in parser.jobs}
    return ParseResult(list(unique.values()), total)
