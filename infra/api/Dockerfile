# verst-api (ENG-04, ADR-0020 §7): FastAPI + the verst_planner engine, non-root, read-only root filesystem.
# Build context = repository root:
#   docker build -f infra/api/Dockerfile -t verst-api:$(git rev-parse --short HEAD) .
# Pin the base image by digest at deploy time (README.md "Release").
FROM python:3.12.14-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/srv/verst/api:/srv/verst/planner \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus

# Dependencies first (cache layer): every package pinned with sha256 hashes; the lock is complete (--no-deps).
COPY backend/api/requirements.lock /srv/verst/api/requirements.lock
RUN pip install --require-hashes --no-deps -r /srv/verst/api/requirements.lock

# The engine (stdlib only) with its packaged catalogue, and the one fixture world it composes with.
COPY backend/planner/verst_planner /srv/verst/planner/verst_planner
COPY backend/planner/fixtures/worlds/central_russia_v1.json /srv/verst/planner/fixtures/worlds/
COPY backend/api/verst_api /srv/verst/api/verst_api
COPY backend/api/migrations /srv/verst/api/migrations
COPY --chmod=0755 infra/api/entrypoint.sh /usr/local/bin/verst-api

RUN python -m compileall -q /srv/verst \
 && useradd --system --uid 10002 --home-dir /srv/verst --shell /usr/sbin/nologin verst
USER verst
WORKDIR /srv/verst

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"]
ENTRYPOINT ["verst-api"]
