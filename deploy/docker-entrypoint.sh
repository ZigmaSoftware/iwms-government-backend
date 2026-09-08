#!/bin/bash
# Starts the container's two responsibilities:
#   1. cron daemon, running the nightly generate_daily_trips job
#   2. gunicorn, serving the Django app (stays in the foreground so
#      Docker/systemd can track the container's actual health)
set -euo pipefail

# cron starts its own minimal environment and does NOT inherit the vars
# Docker injected via --env-file/.env (DB_*, SECRET_KEY, etc). Dump them
# to a file cron jobs can source, so `manage.py` sees the same settings
# gunicorn does.
printenv | sed 's/^\(.*\)$/export \1/' > /etc/container_environment.sh
chmod 0644 /etc/container_environment.sh

echo "Starting cron (daily trip scheduler)..."
cron

echo "Starting gunicorn on 0.0.0.0:9001..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:9001 --workers 3
