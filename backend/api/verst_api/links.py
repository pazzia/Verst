"""Partner links (ENG-03, CEO 01.11 «прикрутить настоящее»): a Yandex Travel city search for the hotel's
town with the stay dates and the crew, wrapped into a Travelpayouts partner link when the account is set.

Without `VERST_TP_TOKEN` / `VERST_TP_MARKER` / `VERST_TP_TRS` the link is the plain search
(`affiliate: false`), as before. With them, the plain URL goes through the Travelpayouts partner-links API
(`TP_LINKS_API`; docs: support.travelpayouts.com/hc/en-us/articles/25289759198226) with `sub_id` = trip and
stop, and the returned
`partner_url` is served (`affiliate: true`). Travelpayouts adds the 38-FZ `erid` itself once the partner has
filled in its advertising-law form (Travelpayouts blog, «new advertising law»). Any API failure falls back to
the plain link: a booking is never blocked by the partner network.

The API answer is read leniently (`result.links[0].partner_url` or `links[0].partner_url`); the shape has
to be confirmed with the first real token (docs/partners/hotel-affiliate.md).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.request
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

YANDEX_TRAVEL_SEARCH = "https://travel.yandex.ru/hotels/search/"
PARTNER = "yandex_travel"
TP_LINKS_API = "https://api.travelpayouts.com/links/v1/create"
SUB_ID_MAX = 32

log = logging.getLogger("verst_api.links")

# (url, headers, body, timeout_s) -> parsed JSON; replaced in tests
PostJson = Callable[[str, dict[str, str], bytes, float], Any]


def hotel_search_url(town: str, checkin: date, nights: int, adults: int, children_ages: list[int]) -> str:
    query = {
        "text": town,
        "checkinDate": checkin.isoformat(),
        "checkoutDate": (checkin + timedelta(days=nights)).isoformat(),
        "adults": str(adults),
    }
    if children_ages:
        query["childrenAges"] = ",".join(str(a) for a in children_ages)
    return YANDEX_TRAVEL_SEARCH + "?" + urlencode(query)


def sub_id(*parts: str | None) -> str:
    """Trip and stop ids as one partner sub-id (letters, digits, `_`; at most 32 characters)."""
    clean = [re.sub(r"[^A-Za-z0-9]", "", p) for p in parts if p]
    return "_".join(c for c in clean if c)[:SUB_ID_MAX] or "app"


@dataclass(frozen=True, slots=True)
class Travelpayouts:
    token: str
    marker: str
    trs: str
    timeout_s: float = 4.0


def _post_json(url: str, headers: dict[str, str], body: bytes, timeout_s: float) -> Any:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _partner_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    holder = result if isinstance(result, dict) else payload
    items = holder.get("links")
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return None
    first = items[0]
    code = first.get("code")
    url = first.get("partner_url")
    if code not in (None, "success") or not isinstance(url, str) or not url.startswith("https://"):
        return None
    return url


class AffiliateLinks:
    """Wraps plain partner URLs; a small in-memory cache keeps the API under its 100 requests a minute."""

    def __init__(
        self,
        cfg: Travelpayouts | None,
        post: PostJson = _post_json,
        ttl_s: float = 24 * 3600,
        max_entries: int = 5000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cfg = cfg
        self._post = post
        self._ttl = ttl_s
        self._max = max_entries
        self._clock = clock
        self._cache: OrderedDict[tuple[str, str], tuple[float, str]] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._cfg is not None

    def wrap(self, url: str, sub: str) -> str | None:
        """The partner link for [url]; None if not configured or the API failed (the caller serves [url])."""
        cfg = self._cfg
        if cfg is None:
            return None
        key = (url, sub)
        now = self._clock()
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None and now - hit[0] < self._ttl:
                self._cache.move_to_end(key)
                return hit[1]
        request = {
            "trs": _num(cfg.trs),
            "marker": _num(cfg.marker),
            "shorten": False,
            "links": [{"url": url, "sub_id": sub}],
        }
        body = json.dumps(request).encode("utf-8")
        headers = {
            "X-Access-Token": cfg.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            partner = _partner_url(self._post(TP_LINKS_API, headers, body, cfg.timeout_s))
        except Exception as e:  # network, HTTP 4xx/5xx, bad JSON: never block the booking
            log.warning("partner link API failed", extra={"error": type(e).__name__})
            return None
        if partner is None:
            log.warning("partner link API: no partner_url in the answer")
            return None
        with self._lock:
            self._cache[key] = (now, partner)
            self._cache.move_to_end(key)
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)
        return partner


def _num(v: str) -> int | str:
    return int(v) if v.isdigit() else v


def travelpayouts(settings: Any) -> Travelpayouts | None:
    """The account from the settings (`VERST_TP_*`), or None while it is not configured."""
    token = settings.tp_token.get_secret_value()
    if not token:
        return None
    return Travelpayouts(token, settings.tp_marker, settings.tp_trs, settings.tp_timeout_s)
