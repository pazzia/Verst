"""Polite HTTP for the data fetchers (ADR-0012 §1): one request at a time, a fixed User-Agent, retries."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "VerstDataBot/0.3 (+https://github.com/pazzia/Verst; data pipeline)"
RETRIES = 4


class Pacer:
    """At most one request per `gap_s` seconds."""

    def __init__(self, gap_s: float) -> None:
        self.gap = gap_s
        self.last = 0.0

    def wait(self) -> None:
        delay = self.last + self.gap - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self.last = time.monotonic()


def request(
    url: str,
    pacer: Pacer,
    data: dict[str, str] | None = None,
    accept: str = "application/json",
    timeout: float = 120.0,
    retries: int = RETRIES,
) -> Any:
    """GET (or POST form `data`) and decode JSON, with exponential back-off on 429/5xx/timeouts."""
    body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
    last_error: Exception | None = None
    for attempt in range(retries):
        pacer.wait()
        req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT, "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
            retry_after = e.headers.get("Retry-After")
            pause = float(retry_after) if retry_after and retry_after.isdigit() else 5.0 * 2**attempt
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = e
            pause = 5.0 * 2**attempt
        if attempt + 1 == retries:
            break
        print(f"retry {attempt + 1}/{retries} in {pause:.0f}s: {last_error}", file=sys.stderr)
        time.sleep(pause)
    assert last_error is not None
    raise last_error
