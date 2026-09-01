#!/usr/bin/env bash
# ==============================================================================
# Assignment Tracker - Automated Ingestion Runner for Server Cron
# ==============================================================================

# Determine the absolute directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Timestamp for log output
echo "--------------------------------------------------"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting automated email ingestion..."

# Check for uv or virtualenv python
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif command -v uv &> /dev/null; then
    PYTHON_BIN="uv run python"
else
    PYTHON_BIN="python3"
fi

# Execute ingestion pipeline
$PYTHON_BIN main.py ingest-email

EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ingestion finished with exit code: $EXIT_CODE"
echo "--------------------------------------------------"

exit $EXIT_CODE
