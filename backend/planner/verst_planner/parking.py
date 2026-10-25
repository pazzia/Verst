"""Static street-parking prices at a car stop (ADR-0015 §4; the CEO's Sprint 4 decision: zone tariffs only,
offline, no live occupancy).

Order of evidence, per stop:
1. a tariff zone of `resources/parking_tariffs.json` (Москва, Санкт-Петербург: concentric bands around the
   centre, the band's day or night rate, Sunday and holiday rules);
2. else an OSM `amenity=parking` with `fee=yes` within `osmRadiusKm`, priced by its `charge` tag when it
   parses («100 RUB/hour», «60 ₽/ч», «2 руб/мин»), else unknown;
3. else free/unknown: the stop is outside any paid zone and no paid OSM parking is near → 0 ₽ («free»).

`ParkingModel.unit` turns that into a `ParkingUnit`: `rub = round10(rate x ceil(dwell / 60))`.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from verst_planner import resources
from verst_planner.cost.money import dec, round_to
from verst_planner.domain.model import LatLon, ParkingUnit
from verst_planner.geo.distance import haversine_km
from verst_planner.geo.grid import GridIndex

CHARGE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:rub|руб\w*\.?|₽|р\.?)\s*(?:/|\s*в\s*|\s*per\s*)\s*(hour|h|час\w*|ч|minute|min|мин\w*)",
    re.I,
)


def charge_per_hour(charge: str | None) -> int | None:
    """An OSM `charge` value → ₽ per hour, or None when it does not parse."""
    if not charge:
        return None
    m = CHARGE.search(charge)
    if not m:
        return None
    amount = float(m.group(1).replace(",", "."))
    per_minute = m.group(2).lower().startswith(("min", "мин"))
    return round(amount * 60) if per_minute else round(amount)


@dataclass(frozen=True, slots=True)
class Band:
    radius_km: float
    day_rub: int
    night_rub: int


@dataclass(frozen=True, slots=True)
class CityZones:
    city: str
    centre: LatLon
    bands: tuple[Band, ...]
    day_from: time
    day_to: time
    sunday_free: bool
    sunday_free_below_rub: int
    holidays_free: bool


@dataclass(frozen=True, slots=True)
class OsmParking:
    point: LatLon
    rub_per_hour: int | None


class ParkingModel:
    def __init__(
        self,
        cities: list[CityZones],
        holidays: set[str],
        osm: list[OsmParking],
        osm_radius_km: float,
        as_of: str,
    ) -> None:
        self.cities = cities
        self.holidays = holidays
        self.osm_radius_km = osm_radius_km
        self.as_of = as_of
        self.osm: GridIndex[int] = GridIndex(0.05)
        self._osm = osm
        for i, o in enumerate(osm):
            self.osm.add(o.point, i)

    @classmethod
    def from_resources(cls, osm: list[OsmParking] | None = None) -> ParkingModel:
        doc: dict[str, Any] = json.loads(resources.read_text("parking_tariffs.json"))
        cities = [
            CityZones(
                c["city"],
                LatLon(float(c["centre"][0]), float(c["centre"][1])),
                tuple(Band(float(b["radiusKm"]), int(b["dayRub"]), int(b["nightRub"])) for b in c["bands"]),
                time.fromisoformat(c["day"][0]),
                time.fromisoformat(c["day"][1]),
                bool(c["sundayFree"]),
                int(c.get("sundayFreeBelowRub", 0)),
                bool(c["holidaysFree"]),
            )
            for c in doc["cities"]
        ]
        return cls(cities, set(doc["holidays"]), osm or [], float(doc["osmRadiusKm"]), str(doc["asOf"]))

    def rate(self, point: LatLon, arrive_local: datetime) -> tuple[int | None, str]:
        """(₽ per hour, source); 0 = free here and now; None = paid parking with an unknown price."""
        for c in self.cities:
            d = haversine_km(c.centre, point)
            band = next((b for b in c.bands if d <= b.radius_km), None)
            if band is None:
                continue
            day = c.day_from <= arrive_local.time() < c.day_to
            rub = band.day_rub if day else band.night_rub
            if c.holidays_free and arrive_local.strftime("%m-%d") in self.holidays:
                return 0, "free"
            if c.sunday_free and arrive_local.weekday() == 6 and band.day_rub < c.sunday_free_below_rub:
                return 0, "free"
            return (rub, "zone") if rub > 0 else (0, "free")
        near = self.osm.within(point, self.osm_radius_km)
        if near:
            _d, i = min(near)
            r = self._osm[i].rub_per_hour
            return (r, "osm") if r is not None else (None, "unknown")
        return 0, "free"

    def unit(
        self, stop_id: str, name: str, point: LatLon, arrive_local: datetime, dwell_min: int
    ) -> ParkingUnit:
        rate, source = self.rate(point, arrive_local)
        hours = max(1, math.ceil(dwell_min / 60))
        rub = None if rate is None else round_to(dec(rate * hours), 10)
        return ParkingUnit(stop_id, name, rate, hours, rub, source)


__all__ = ["OsmParking", "ParkingModel", "charge_per_hour"]
