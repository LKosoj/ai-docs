#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="./logs"
PID_FILE="./run.pid"

if [[ $# -lt 1 ]]; then
  if [[ -f "$PID_FILE" ]]; then
    read -r PID RUN_LOG <"$PID_FILE" || true
    if [[ -z "${PID:-}" ]]; then
      echo "PID file is empty: $PID_FILE"
      exit 1
    fi
    if ps -p "$PID" >/dev/null 2>&1; then
      ELAPSED_SEC="$(ps -p "$PID" -o etimes= | tr -d ' ')"
      if [[ -n "$ELAPSED_SEC" ]]; then
        printf "Process is running: PID=%s, elapsed=%ss\n" "$PID" "$ELAPSED_SEC"
      else
        echo "Process is running: PID=$PID"
      fi
      if [[ -z "${RUN_LOG:-}" ]]; then
        RUN_LOG="$(ls -1t "$LOG_DIR"/ai-docs-*.log 2>/dev/null | head -n 1 || true)"
      fi
      if [[ -n "$RUN_LOG" && -f "$RUN_LOG" ]]; then
        echo "Log: $RUN_LOG"
        tail -n 100 "$RUN_LOG"
      else
        echo "Log not found."
      fi
      exit 0
    fi
    echo "No running process found for PID=$PID"
    rm -f "$PID_FILE"
    exit 1
  fi
  echo "Usage: $0 <project_path> [ai-docs args...]"
  exit 1
fi

PROJECT_PATH="$1"
shift

mkdir -p "$LOG_DIR"

PYTHON_BIN="./.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python"
fi

LOG_FILE="$LOG_DIR/ai-docs-$(date +%Y%m%d-%H%M%S).log"

if command -v setsid >/dev/null 2>&1; then
  PYTHONUNBUFFERED=1 setsid "$PYTHON_BIN" -m ai_docs --source "$PROJECT_PATH" "$@" >"$LOG_FILE" 2>&1 &
else
  PYTHONUNBUFFERED=1 nohup "$PYTHON_BIN" -m ai_docs --source "$PROJECT_PATH" "$@" >"$LOG_FILE" 2>&1 &
fi

disown || true
echo "$! $LOG_FILE" >"$PID_FILE"

echo "Started ai-docs in background: PID=$(cat "$PID_FILE")"
echo "Log: $LOG_FILE"
