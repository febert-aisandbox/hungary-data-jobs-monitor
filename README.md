# Hungary Data Jobs Monitor

Daily, public-market monitor for data-related advertisements on Profession.hu. It collects a conservative set of search-result pages, applies a transparent title-based relevance classifier, deduplicates advertisements by Profession.hu ID, retains history in SQLite, and publishes a static dashboard plus a Telegram-ready digest.

## What the counts mean

Counts represent advertisements observed in public search results—not hires, applicants, or guaranteed distinct vacancies. The first run establishes a baseline, so all advertisements are initially “new.” An advertisement becomes inactive only after two consecutive complete successful runs do not observe it. Partial runs never expire jobs.

## Local run

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m profession_monitor --db data/market.db --output docs --delay 0 --max-pages 1
```

Production collection uses `config/searches.json`, 2.5 seconds plus jitter between requests, and follows each query through its complete reported result set (with a 20-page safety cap). It uses a stable User-Agent and aborts publication after parser, pagination-consistency, or network failures. It never bypasses login, CAPTCHA, rate limits, or access controls.

## Files

- `data/market.db` — persistent history (not committed)
- `docs/index.html` — dashboard
- `docs/daily.json` — machine-readable report
- `docs/daily.txt` — Telegram-ready digest

Public dashboard: https://febert-aisandbox.github.io/hungary-data-jobs-monitor/
