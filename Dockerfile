# IWMS Government Backend — Django + gunicorn + nightly trip scheduler (cron)
FROM python:3.12-slim

WORKDIR /app

# System deps needed for mysqlclient/Pillow/cryptography style packages,
# plus cron for the nightly generate_daily_trips job (replaces host cron).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Install deps first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/static /app/media

# Install the nightly trip-generation cron job
COPY deploy/cron/generate-daily-trips.cron /etc/cron.d/generate-daily-trips
RUN chmod 0644 /etc/cron.d/generate-daily-trips \
    && crontab /etc/cron.d/generate-daily-trips

COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 9001

CMD ["/usr/local/bin/docker-entrypoint.sh"]
