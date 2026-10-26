"""Prometheus metrics (ADR-0020 §8). With several uvicorn workers the container sets
`PROMETHEUS_MULTIPROC_DIR` (prometheus_client multiprocess mode) and `/metrics` aggregates the workers.
Labels never carry ids, coordinates or paths with ids: `route` is the route template."""

from __future__ import annotations

import os

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

HTTP_REQUESTS = Counter("verst_http_requests_total", "HTTP requests", ["route", "method", "status"])
HTTP_SECONDS = Histogram(
    "verst_http_request_seconds",
    "HTTP latency (SSE: whole stream)",
    ["route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 25),
)
PLAN_SECONDS = Histogram(
    "verst_plan_seconds", "Engine plan latency", ["outcome"], buckets=(0.25, 0.5, 1, 2, 4, 6, 8, 10, 15, 25)
)
PLAN_SYNTHETIC = Counter("verst_plan_synthetic_total", "Plans returned with approxDistances (road model)")
ROUTING_FALLBACK = Counter("verst_routing_fallback_total", "GraphHopper failures answered by the road model")
ROUTE_REQUESTS = Counter("verst_route_requests_total", "POST /v1/route outcomes", ["outcome"])

CONTENT_TYPE = CONTENT_TYPE_LATEST


def render() -> bytes:
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
        return generate_latest(registry)
    return generate_latest()
