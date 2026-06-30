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
set -e

BACKEND_DIR="/home/admin/localserver/iwms-backend"
LOG="/home/admin/generate_daily_trips.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

cd "$BACKEND_DIR"

echo "[$TIMESTAMP] Daily trip scheduler started" >> "$LOG"
.venv/bin/python manage.py generate_daily_trips >> "$LOG" 2>&1
echo "[$TIMESTAMP] Daily trip scheduler finished" >> "$LOG"
