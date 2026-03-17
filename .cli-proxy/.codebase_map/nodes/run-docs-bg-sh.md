# Node: run-docs-bg-sh

## Purpose
Bash wrapper script for running `ai-docs` in background with PID tracking, log rotation, and status monitoring.

## Scope
- **File**: `run_docs_bg.sh` (120 lines)
- **Usage**: `./run_docs_bg.sh <project_path> [ai-docs args...]`
- **Output**: Background process with logs in `logs/ai-docs-YYYYMMDD-HHMMSS.log`
- **PID tracking**: `run.pid` file (PID + log path)

## Instructions for agent
- **Run**: `./run_docs_bg.sh /path/to/project --readme --mkdocs --threads 4`
- **Check status**: `./run_docs_bg.sh` (no args) — shows running process status + tail logs
- **Logs**: `logs/` directory, timestamped files, auto-rotated per run
- **Python detection**: Uses `./.venv/bin/python` if exists, else fallback to `python`
- **Process isolation**: Uses `setsid` (Linux) or `nohup` (fallback) for background execution
- **Do not**: Kill process manually; use `kill $(cat run.pid | awk '{print $1}')` if needed

## Source of truth
- **Script**: `run_docs_bg.sh` (root directory)
- **Python interpreter**: `./.venv/bin/python` (preferred) or `python` (fallback)
- **Log directory**: `./logs/` (created automatically)
- **PID file**: `./run.pid` (format: `<PID> <LOG_PATH>`)
- **Command**: `python -m ai_docs --source <PROJECT_PATH> [args...]`

## When to update
- **CLI changes**: Any new `ai-docs` arguments require updating script usage/help.
- **Log rotation**: Changes to log format/location require script update.
- **Python path**: New virtualenv location or containerization requires `PYTHON_BIN` update.
- **Process management**: Switching to systemd/supervisord requires rewrite.
- **Error handling**: Changes to `set -euo pipefail` or error recovery logic.

## Related nodes
- `ai-docs.md` — CLI tool invoked by script (`ai_docs.cli:main`)
- `pyproject-toml.md` — package entry point (`ai-docs = ai_docs.cli:main`)
- `ai-docs-cache.md` — cache directory (`.ai_docs_cache/`) used during background runs

## Owner
- `project-maintainers`

## Last reviewed
- 2026-03-17
