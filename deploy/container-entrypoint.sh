#!/usr/bin/env bash
set -uo pipefail
DAILY_SCRIPT="${DAILY_SCRIPT:-/app/deploy/run-daily.sh}"
POLL_SECONDS="${POLL_SECONDS:-900}"

if [[ "${SCHEDULER_ONCE:-0}" == "1" ]]; then
  exec "$DAILY_SCRIPT"
fi

child_pid=""
stop() {
  if [[ -n "$child_pid" ]]; then
    kill -TERM -- "-$child_pid" 2>/dev/null || kill -TERM "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  exit 0
}
trap stop TERM INT

while true; do
  setsid "$DAILY_SCRIPT" &
  child_pid=$!
  if ! wait "$child_pid"; then
    printf '[%s] scheduler tick failed; retrying later\n' "$(date -Is)" >&2
  fi
  child_pid=""
  sleep "$POLL_SECONDS" &
  child_pid=$!
  wait "$child_pid" || true
  child_pid=""
done
