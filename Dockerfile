# TalentBridge — complete local environment.
# Build:  docker build -t talentbridge .
# Run:    docker run -d --name talentbridge -p 127.0.0.1:8000:8000 talentbridge
#
# The base image and Python packages are the only downloaded artifacts; all
# application code, migrations, seed data, and tests live in this repository.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup --system app \
    && adduser --system --ingroup app --home /home/app app \
    && mkdir -p /data \
    && chown -R app:app /app /data

USER app

ENV DATABASE_PATH=/data/app.db \
    HOST=0.0.0.0 \
    PORT=8000 \
    SECRET_KEY=local-docker-demo-secret-change-me

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"

ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
