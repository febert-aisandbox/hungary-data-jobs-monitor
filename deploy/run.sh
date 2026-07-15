#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-$HOME/profession-monitor/app}"
DATA_DIR="${DATA_DIR:-$HOME/profession-monitor/data}"
ENV_FILE="${ENV_FILE:-$HOME/.config/profession-monitor/env}"
mkdir -p "$DATA_DIR" "$APP_DIR/docs"
if [[ -f "$ENV_FILE" ]]; then set -a; source "$ENV_FILE"; set +a; fi
cd "$APP_DIR"
exec env PYTHONPATH=src python3 -m profession_monitor --config config/searches.json --db "$DATA_DIR/market.db" --output docs --publish
