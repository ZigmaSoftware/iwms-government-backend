#!/bin/bash
# ============================================================
# Daily Trip Job Scheduler
# ------------------------------------------------------------
# Runs the nightly trip-generation job: for every ACTIVE +
# APPROVED + auto-assign TripPlan whose repeat_days includes
# today's weekday, it creates a DailyTripAssignment and clones
# every stop into Daily Trip Points / Household Collections.
#
# Wired into cron to run every day at 12:05 AM (see cron.sh).
# Idempotent: safe to run multiple times — no duplicates.
#
# Manual run:   ./scheduler.sh
# Specific day: BACKEND_DIR/.venv/bin/python manage.py generate_daily_trips --date 2026-06-26
# ============================================================
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

BACKEND_DIR="/home/admin/localserver/iwmsGovernment/iwms-government-backend"
LOG_DIR="/home/admin/localserver/iwmsGovernment/logs"
LOG="$LOG_DIR/generate_daily_trips.log"
LEGACY_VENV_DIR="/home/admin/localserver/iwms-backend/venv"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

resolve_python_bin() {
    local candidate

    for candidate in \
        "$BACKEND_DIR/.venv/bin/python" \
        "$BACKEND_DIR/venv/bin/python" \
        "$LEGACY_VENV_DIR/bin/python"
    do
        if [[ -x "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done

    echo "/usr/bin/python3"
}

PYTHON_BIN=$(resolve_python_bin)

mkdir -p "$LOG_DIR"

cd "$BACKEND_DIR"

echo "[$TIMESTAMP] Daily trip scheduler started" >> "$LOG"
"$PYTHON_BIN" manage.py generate_daily_trips >> "$LOG" 2>&1
echo "[$TIMESTAMP] Daily trip scheduler finished" >> "$LOG"
