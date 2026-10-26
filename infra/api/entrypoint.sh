#!/bin/sh
# verst-api container entrypoint (ADR-0020 §7).
# - uvicorn's access log is off: it prints raw paths with query strings (coordinates, R-07); verst-api writes
#   its own JSON access line with the route template instead.
# - --proxy-headers: the client IP comes from X-Forwarded-For set by Caddy, the only peer that can reach this
#   port (it is not published); Caddy replaces any X-Forwarded-For sent by clients.
# - Every worker loads the engine (~0.3 s, ~60 MB); migrations run once under an advisory lock.
set -eu
rm -rf "${PROMETHEUS_MULTIPROC_DIR:?}"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
exec uvicorn verst_api.main:app --factory \
  --host 0.0.0.0 --port 8000 \
  --workers "${VERST_WORKERS:-2}" \
  --proxy-headers --forwarded-allow-ips "*" \
  --no-access-log \
  --timeout-graceful-shutdown 30
