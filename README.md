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

## Docker deployment

The production collector runs entirely inside a non-root, read-only Docker container. Its scheduler polls every 15 minutes, executes once after 06:30 Europe/Budapest, and retries until publication succeeds. SQLite, the success stamp, generated artifacts, and logs live in the `profession-monitor-data` named volume. The publishing token remains in a mode-600 host file mounted read-only; building with the host UID/GID lets the unprivileged container process read that single file without exposing it through `docker inspect`. No host Python packages or cron entries are required.

```bash
docker build \
  --build-arg MONITOR_UID="$(id -u)" \
  --build-arg MONITOR_GID="$(id -g)" \
  -t profession-monitor:latest .
docker volume create profession-monitor-data
docker run -d --name profession-monitor --restart unless-stopped \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 64 --memory 256m --tmpfs /tmp:rw,nosuid,nodev,noexec,size=16m \
  -v profession-monitor-data:/data \
  -v "$HOME/.config/profession-monitor/env:/run/secrets/profession-monitor.env:ro" \
  profession-monitor:latest
```

## Files

- `/data/market.db` — persistent history in the Docker volume
- `/data/docs/index.html` — generated dashboard artifact
- `/data/docs/daily.json` — machine-readable report
- `/data/docs/daily.txt` — Telegram-ready digest

Public dashboard: https://febert-aisandbox.github.io/hungary-data-jobs-monitor/
