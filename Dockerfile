# IWMS Government Backend — Django + gunicorn
#
# The nightly trip-generation job (generate_daily_trips) is NOT run via
# cron here — the app already schedules it itself in-process
# (app/services/daily_trip_scheduler.py, started from AppConfig.ready(),
# DB-lock protected across gunicorn workers). No separate scheduler
# process is needed inside this image.
FROM python:3.12-slim

WORKDIR /app

# System deps needed for mysqlclient/Pillow/cryptography style packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install deps first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/static /app/media

EXPOSE 9001

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:9001", "--workers", "3"]
