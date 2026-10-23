"""Subset of OSM `opening_hours` (A§6.9).

Supported: ``24/7``; rules separated by ``;``; each rule is an optional weekday selector (``Mo``..``Su``,
ranges ``Tu-Su`` incl. wrapping ``Fr-Mo``, lists ``Sa,Su``) followed by comma-separated time ranges
``HH:MM-HH:MM`` (end may be ``24:00`` or wrap past midnight) or ``off``/``closed``. Later rules replace
earlier ones for the days they name. Rules starting with ``PH`` or ``SH`` are ignored. Anything else raises
`OpeningHoursParseError`. Times are local wall time; aware datetimes are read by their wall-clock fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from verst_planner.domain.errors import OpeningHoursParseError

_DAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
_DAY_INDEX = {d: i for i, d in enumerate(_DAYS)}
_TIME_RANGE = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")
_DAY_SEL = re.compile(r"^(Mo|Tu|We|Th|Fr|Sa|Su)(-(Mo|Tu|We|Th|Fr|Sa|Su))?$")
_DAY_MIN = 24 * 60

Interval = tuple[int, int]  # minutes from the start of the day; end may exceed 1440 (spill)


@dataclass(frozen=True, slots=True)
class OpeningHours:
    source: str
    week: tuple[tuple[Interval, ...], ...]  # 7 entries, Monday first

    @property
    def always(self) -> bool:
        return all(day == ((0, _DAY_MIN),) for day in self.week)

    def _intervals_around(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        """Absolute open intervals of every day that can touch [start, end], merged."""
        day0 = datetime(start.year, start.month, start.day) - timedelta(days=1)
        last = datetime(end.year, end.month, end.day)
        spans: list[tuple[datetime, datetime]] = []
        d = day0
        while d <= last:
            for lo, hi in self.week[d.weekday()]:
                spans.append((d + timedelta(minutes=lo), d + timedelta(minutes=hi)))
            d += timedelta(days=1)
        spans.sort()
        merged: list[tuple[datetime, datetime]] = []
        for a, b in spans:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        return merged

    def is_open(self, local_dt: datetime) -> bool:
        """Open at this instant (closing time itself is closed)."""
        t = local_dt.replace(tzinfo=None, second=0, microsecond=0)
        return any(lo <= t < hi for lo, hi in self._intervals_around(t, t))

    def covers(self, start_local: datetime, end_local: datetime) -> bool:
        """The whole visit [start, end] lies inside one continuous open period (end may equal closing)."""
        s = start_local.replace(tzinfo=None, second=0, microsecond=0)
        e = end_local.replace(tzinfo=None, second=0, microsecond=0)
        if e < s:
            return False
        return any(lo <= s and e <= hi for lo, hi in self._intervals_around(s, e))


def _parse_time(h: str, m: str, allow_24: bool, src: str) -> int:
    hh, mm = int(h), int(m)
    if mm > 59 or hh > 24 or (hh == 24 and (mm != 0 or not allow_24)):
        raise OpeningHoursParseError(f"bad time in {src!r}")
    return hh * 60 + mm


def _parse_days(selector: str, src: str) -> list[int]:
    days: list[int] = []
    for part in selector.split(","):
        m = _DAY_SEL.match(part)
        if not m:
            raise OpeningHoursParseError(f"unsupported day selector {part!r} in {src!r}")
        a = _DAY_INDEX[m.group(1)]
        b = _DAY_INDEX[m.group(3)] if m.group(3) else a
        i = a
        while True:
            if i not in days:
                days.append(i)
            if i == b:
                break
            i = (i + 1) % 7
    return days


def _parse_times(spec: str, src: str) -> tuple[Interval, ...]:
    if spec in ("off", "closed"):
        return ()
    out: list[Interval] = []
    for part in spec.split(","):
        m = _TIME_RANGE.match(part.strip())
        if not m:
            raise OpeningHoursParseError(f"unsupported time range {part!r} in {src!r}")
        lo = _parse_time(m.group(1), m.group(2), False, src)
        hi = _parse_time(m.group(3), m.group(4), True, src)
        if hi == lo:
            raise OpeningHoursParseError(f"empty time range {part!r} in {src!r}")
        if hi < lo:
            hi += _DAY_MIN  # wraps past midnight
        out.append((lo, hi))
    return tuple(sorted(out))


def parse(s: str) -> OpeningHours:
    src = s.strip()
    if not src:
        raise OpeningHoursParseError("empty opening_hours")
    if src == "24/7":
        return OpeningHours(src, tuple(((0, _DAY_MIN),) for _ in range(7)))
    week: list[tuple[Interval, ...]] = [() for _ in range(7)]
    any_rule = False
    for raw in src.split(";"):
        rule = raw.strip()
        if not rule:
            continue
        if rule.startswith(("PH", "SH")):
            continue
        head, _, rest = rule.partition(" ")
        if _DAY_SEL.match(head.split(",")[0]):
            days = _parse_days(head, src)
            times = rest.strip()
        else:
            days = list(range(7))
            times = rule
        if not times:
            raise OpeningHoursParseError(f"missing times in rule {rule!r}")
        intervals = _parse_times(times, src)
        for d in days:
            week[d] = intervals
        any_rule = True
    if not any_rule:
        raise OpeningHoursParseError(f"no usable rule in {src!r}")
    return OpeningHours(src, tuple(week))
