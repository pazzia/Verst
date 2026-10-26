"""Privacy rules of risk register R-07 (ADR-0020 §5) in one place.

- Stored trips and logs carry coordinates rounded to `COORD_DECIMALS` (2 ≈ 1 km); exact points live only in
  memory while a request is served.
- A shared trip names the town of a user point (start, finish, vias), never the label the user typed or picked
  (often a street address).
- Free feedback text is masked for phone numbers and e-mail addresses before it is stored.
- Client IPs appear only as an HMAC inside short-lived rate-limit keys.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Callable, Mapping
from typing import Any

COORD_DECIMALS = 2
COORD_KEYS = frozenset({"lat", "lon"})

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# A run of digits and phone punctuation holding at least 7 digits ("+7 (916) 123-45-67", "89161234567").
_PHONE = re.compile(r"\+?\d[\d\s().\-]{5,}\d")
_DIGITS_MIN = 7
EMAIL_MASK = "[почта скрыта]"
PHONE_MASK = "[телефон скрыт]"


def round_coord(v: float) -> float:
    return round(float(v), COORD_DECIMALS)


def log_point(lat: float, lon: float) -> list[float]:
    """A point as it may appear in a log line."""
    return [round_coord(lat), round_coord(lon)]


def round_coordinates(node: Any) -> Any:
    """A copy of a JSON tree with every numeric `lat` / `lon` rounded to `COORD_DECIMALS`."""
    if isinstance(node, dict):
        return {
            k: (
                round_coord(v)
                if k in COORD_KEYS and isinstance(v, int | float) and not isinstance(v, bool)
                else round_coordinates(v)
            )
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [round_coordinates(v) for v in node]
    return node


def replace_strings(node: Any, replacements: Mapping[str, str]) -> Any:
    """A copy of a JSON tree with every occurrence of each key of `replacements` replaced inside every string
    (titles, reasons and notes quote the user's labels). Longer keys are replaced first."""
    if not replacements:
        return node
    order = sorted(replacements, key=len, reverse=True)

    def fix(s: str) -> str:
        for old in order:
            if old in s:
                s = s.replace(old, replacements[old])
        return s

    return _map_strings(node, fix)


def _map_strings(node: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(node, str):
        return fn(node)
    if isinstance(node, dict):
        return {k: _map_strings(v, fn) for k, v in node.items()}
    if isinstance(node, list):
        return [_map_strings(v, fn) for v in node]
    return node


USER_POINT_KINDS = frozenset({"start", "finish", "via"})


def scrub_trip(trip: dict[str, Any], town_of: Callable[[float, float], str]) -> dict[str, Any]:
    """The trip as it may be stored and shared (R-07):

    1. every user point of `input` (origin, destination, vias) gets the name of its town as `label`;
    2. start / finish / via stops that are user points (no `placeId`, no `townId`) get their town as `name`;
    3. every former label is replaced by its town inside every string (title, reasons, notes);
    4. every `lat` / `lon` in the tree is rounded to 2 decimals.

    `town_of(lat, lon)` names the town of a point (the engine's nearest town, or «Точка на карте»)."""
    inp = trip.get("input")
    replacements: dict[str, str] = {}
    out = dict(trip)
    if isinstance(inp, dict):
        new_inp = dict(inp)
        for key in ("origin", "destination"):
            if isinstance(inp.get(key), dict):
                new_inp[key] = _scrub_point(inp[key], town_of, replacements)
        if isinstance(inp.get("vias"), list):
            new_inp["vias"] = [
                _scrub_point(v, town_of, replacements) if isinstance(v, dict) else v for v in inp["vias"]
            ]
        out["input"] = new_inp
    days = []
    for d in trip.get("daysList") or []:
        if not isinstance(d, dict):
            days.append(d)
            continue
        stops = []
        for s in d.get("stops") or []:
            if (
                isinstance(s, dict)
                and s.get("kind") in USER_POINT_KINDS
                and s.get("placeId") is None
                and s.get("townId") is None
                and _is_num(s.get("lat"))
                and _is_num(s.get("lon"))
            ):
                town = town_of(float(s["lat"]), float(s["lon"]))
                name = s.get("name")
                if isinstance(name, str) and name and name != town:
                    replacements.setdefault(name, town)
                s = {**s, "name": town}
            stops.append(s)
        days.append({**d, "stops": stops})
    if "daysList" in trip:
        out["daysList"] = days
    scrubbed: dict[str, Any] = round_coordinates(replace_strings(out, replacements))
    return scrubbed


def _scrub_point(
    p: Mapping[str, Any], town_of: Callable[[float, float], str], acc: dict[str, str]
) -> dict[str, Any]:
    out = dict(p)
    if _is_num(p.get("lat")) and _is_num(p.get("lon")):
        town = town_of(float(p["lat"]), float(p["lon"]))
        label = p.get("label")
        if isinstance(label, str) and label and label != town:
            acc.setdefault(label, town)
        out["label"] = town
    return out


def _is_num(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def mask_contacts(text: str) -> str:
    """Feedback text with e-mail addresses and phone-like digit runs (≥ 7 digits) masked (R-07 (в))."""
    text = _EMAIL.sub(EMAIL_MASK, text)
    return _PHONE.sub(lambda m: PHONE_MASK if _digits(m.group()) >= _DIGITS_MIN else m.group(), text)


def _digits(s: str) -> int:
    return sum(c.isdigit() for c in s)


def ip_key(secret: str, ip: str) -> str:
    """The client IP as it may appear in a rate-limit key: HMAC-SHA256, 16 hex chars, unlinkable without the
    server secret (an unsalted hash of an IPv4 address is reversible by enumeration)."""
    return hmac.new(secret.encode(), ip.encode(), hashlib.sha256).hexdigest()[:16]


def device_tag(device_id: str) -> str:
    """The device as it appears in logs: 8 hex chars of a hash, enough to follow one device's requests."""
    return hashlib.sha256(device_id.encode()).hexdigest()[:8]
