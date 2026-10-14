# IWMS Government Backend — Django + gunicorn
#
# The same image also runs the Celery worker and beat containers
# (`celery -A config worker|beat`, see docker-compose*.yml), which handle
# background tasks and the periodic jobs (daily trip generation, complaint
# SLA sweep). The gunicorn container itself runs no scheduler.
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
# --timeout/--retries: this build environment has a slow/unstable link to
# PyPI, so pip's default 15s read-timeout was cutting off large wheel
# downloads (django, pillow, grpcio) mid-stream.
RUN pip install --no-cache-dir --timeout=180 --retries=10 -r requirements.txt

COPY . .

RUN mkdir -p /app/static /app/media

EXPOSE 9001

# --timeout above JOB_WAIT_SECONDS (50): bulk upload and Excel export
# requests wait for the Celery worker to finish the job.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:9001", "--workers", "3", "--timeout", "90"]
