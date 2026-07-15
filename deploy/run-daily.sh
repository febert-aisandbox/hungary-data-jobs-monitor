#!/usr/bin/env bash
set -euo pipefail
export TZ=Europe/Budapest
HOUR="$(date +%H)"
(( 10#$HOUR >= 6 )) || exit 0
BASE="${HOME}/profession-monitor"
STAMP="$BASE/data/last-success-date"
TODAY="$(date +%F)"
[[ -f "$STAMP" && "$(<"$STAMP")" == "$TODAY" ]] && exit 0
mkdir -p "$BASE/logs" "$BASE/data"
LOG="$BASE/logs/collector.log"
if [[ -f "$LOG" && "$(stat -c %s "$LOG")" -gt 5242880 ]]; then mv "$LOG" "$LOG.1"; fi
if timeout 20m "$BASE/app/deploy/run.sh" >>"$LOG" 2>&1; then
  printf '%s\n' "$TODAY" > "$STAMP"
else
  printf '[%s] collection failed\n' "$(date -Is)" >>"$LOG"
  exit 1
fi
