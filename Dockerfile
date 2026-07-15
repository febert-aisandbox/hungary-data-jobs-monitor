FROM python:3.13-slim-bookworm

ARG MONITOR_UID=10001
ARG MONITOR_GID=10001
RUN apt-get update \
    && apt-get install --no-install-recommends -y bash coreutils tzdata util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid "$MONITOR_GID" monitor \
    && useradd --create-home --uid "$MONITOR_UID" --gid "$MONITOR_GID" --shell /usr/sbin/nologin monitor

WORKDIR /app
COPY src/ src/
COPY config/ config/
COPY deploy/ deploy/
RUN chmod -R a-w /app \
    && chmod 0555 deploy/run.sh deploy/run-daily.sh deploy/container-entrypoint.sh \
    && mkdir -p /data \
    && chown monitor:monitor /data

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    TZ=Europe/Budapest \
    APP_DIR=/app \
    DATA_DIR=/data \
    OUTPUT_DIR=/data/docs \
    LOG_DIR=/data/logs \
    ENV_FILE=/run/secrets/profession-monitor.env

VOLUME ["/data"]
USER monitor
ENTRYPOINT ["/app/deploy/container-entrypoint.sh"]
