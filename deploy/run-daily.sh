#!/usr/bin/env bash
set -euo pipefail
export TZ="${TZ:-Europe/Budapest}"
NOW_HHMM="${NOW_HHMM:-$(date +%H%M)}"
(( 10#$NOW_HHMM >= 630 )) || exit 0
BASE="${BASE:-${HOME}/profession-monitor}"
DATA_DIR="${DATA_DIR:-$BASE/data}"
LOG_DIR="${LOG_DIR:-$BASE/logs}"
RUNNER="${RUNNER:-$BASE/app/deploy/run.sh}"
STAMP="$DATA_DIR/last-success-date"
TODAY="${NOW_DATE:-$(date +%F)}"
[[ -f "$STAMP" && "$(<"$STAMP")" == "$TODAY" ]] && exit 0
mkdir -p "$LOG_DIR" "$DATA_DIR"
LOG="$LOG_DIR/collector.log"
if [[ -f "$LOG" && "$(stat -c %s "$LOG")" -gt 5242880 ]]; then mv "$LOG" "$LOG.1"; fi
if timeout 20m "$RUNNER" >>"$LOG" 2>&1; then
  printf '%s\n' "$TODAY" > "$STAMP"
else
  printf '[%s] collection failed\n' "$(date -Is)" >>"$LOG"
  exit 1
fi
