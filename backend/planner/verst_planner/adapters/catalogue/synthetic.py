"""Deterministic fictional services for catalogue towns and synthetic roads (ADR-0012 §4).

Everything here is invented and seeded by stable ids (`zlib.crc32`), so the same town always gets the same
hotels and cafes, and a synthetic fuel/rest place can be rebuilt from its id alone (its coordinates are in
the id). No name here may be a real brand (`tests/brand_denylist.txt` scans the composed world).
"""

from __future__ import annotations

import math
import zlib
from datetime import date

from verst_planner.domain.enums import PlaceStatus, PlaceType, Source, Tag
from verst_planner.domain.model import LatLon, PartnerIds, Place, Town
from verst_planner.explain import ru
from verst_planner.geo.distance import KM_PER_DEG_LAT, KM_PER_DEG_LON_EQUATOR

HOTEL_NAMES = tuple(ru.words("synthetic.hotels"))
CAFE_NAMES = tuple(ru.words("synthetic.cafes"))
CANTEEN_NAMES = tuple(ru.words("synthetic.canteens"))
FUEL_NAME = ru.text("synthetic.fuel")
REST_NAME = ru.text("synthetic.rest")

HOTEL_PRICE_FACTORS = (0.8, 1.0, 1.3)
FAMILY_PRICE_FACTOR = 1.4
ECONOMY_CHECK_FACTOR = 0.75
SYN_PREFIX = "syn_"
COORD = 100_000
AS_OF = date(2026, 10, 1)


def _seed(*parts: str) -> int:
    return zlib.crc32("|".join(parts).encode("utf-8"))


def _offset(p: LatLon, dx_km: float, dy_km: float) -> LatLon:
    c = math.cos(math.radians(p.lat))
    return LatLon(p.lat + dy_km / KM_PER_DEG_LAT, p.lon + dx_km / (KM_PER_DEG_LON_EQUATOR * c))


def _round100(x: float) -> int:
    return math.floor(x / 100.0 + 0.5) * 100


def _place(
    pid: str,
    ptype: PlaceType,
    name: str,
    point: LatLon,
    region: str,
    town_id: str | None,
    *,
    tags: frozenset[Tag] = frozenset(),
    rating: float = 4.0,
    price_night: int | None = None,
    family_price: int | None = None,
    avg_check: int | None = None,
    hours: str | None = None,
    breakfast: bool = True,
) -> Place:
    return Place(
        id=pid,
        type=ptype,
        name_ru=name,
        point=point,
        address=None,
        region_code=region,
        town_id=town_id,
        opening_hours=hours,
        dwell_min=None,
        avg_check_rub=avg_check,
        price_night_rub=price_night,
        ticket_adult_rub=None,
        ticket_child_rub=None,
        rating_internal=rating,
        tags=tags,
        description_ru=None,
        partner_ids=PartnerIds(None, None),
        source=Source.CURATED,
        verified_at=AS_OF,
        status=PlaceStatus.LIVE,
        breakfast_included=breakfast,
        family_price_rub=family_price,
    )


def hotels_for(town: Town, night_rub: int) -> list[Place]:
    """Three fictional hotels: prices x (0.8, 1.0, 1.3); one allows dogs, two have family rooms."""
    s = _seed("hotel", town.id)
    out = []
    for k in range(3):
        name = HOTEL_NAMES[(s + 5 * k) % len(HOTEL_NAMES)]
        angle = (s % 360 + 120 * k) * math.pi / 180
        dist = 0.6 + 0.5 * k
        tags = {Tag.PARKING}
        if k in (1, 2):
            tags.add(Tag.FAMILY_ROOM)
        if k == (s % 3):
            tags.add(Tag.DOGS_ALLOWED)
        price = _round100(night_rub * HOTEL_PRICE_FACTORS[k])
        out.append(
            _place(
                f"{SYN_PREFIX}h_{town.id}_{k}",
                PlaceType.LODGING,
                name,
                _offset(town.point, dist * math.cos(angle), dist * math.sin(angle)),
                town.region_code,
                town.id,
                tags=frozenset(tags),
                rating=round(4.1 + 0.2 * ((s >> (4 * k)) % 3), 1),
                price_night=price,
                family_price=_round100(price * FAMILY_PRICE_FACTOR) if Tag.FAMILY_ROOM in tags else None,
                breakfast=k == 1,
            )
        )
    return out


def cafes_for(town: Town, check_rub: int) -> list[Place]:
    """A canteen at the economy check and a cafe at the default check, near the centre."""
    s = _seed("cafe", town.id)
    canteen = _place(
        f"{SYN_PREFIX}c_{town.id}_0",
        PlaceType.FOOD,
        CANTEEN_NAMES[s % len(CANTEEN_NAMES)],
        _offset(town.point, 0.3, -0.2),
        town.region_code,
        town.id,
        tags=frozenset({Tag.PARKING}),
        rating=3.9,
        avg_check=_round100(check_rub * ECONOMY_CHECK_FACTOR) or 100,
        hours="Mo-Su 08:00-20:00",
    )
    cafe = _place(
        f"{SYN_PREFIX}c_{town.id}_1",
        PlaceType.FOOD,
        CAFE_NAMES[s % len(CAFE_NAMES)],
        _offset(town.point, -0.4, 0.3),
        town.region_code,
        town.id,
        tags=frozenset({Tag.KIDS_MENU, Tag.PARKING}),
        rating=4.3,
        avg_check=check_rub,
        hours="Mo-Su 09:00-22:00",
    )
    return [canteen, cafe]


def roadside_id(kind: str, p: LatLon) -> str:
    return f"{SYN_PREFIX}{kind}_{round(p.lat * COORD)}_{round(p.lon * COORD)}"


def roadside(pid: str, region: str) -> Place | None:
    """Rebuild a synthetic fuel (`syn_f_…`) or rest (`syn_r_…`) place from its id."""
    parts = pid.split("_")
    if len(parts) != 4 or parts[0] + "_" != SYN_PREFIX or parts[1] not in ("f", "r"):
        return None
    try:
        p = LatLon(int(parts[2]) / COORD, int(parts[3]) / COORD)
    except ValueError:
        return None
    if parts[1] == "f":
        return _place(
            pid,
            PlaceType.FUEL,
            FUEL_NAME,
            p,
            region,
            None,
            tags=frozenset({Tag.WC, Tag.CAFE_AT_FUEL, Tag.H24}),
        )
    return _place(pid, PlaceType.REST, REST_NAME, p, region, None, tags=frozenset({Tag.WC}), rating=3.5)


def roadside_region_point(pid: str) -> LatLon | None:
    parts = pid.split("_")
    if len(parts) != 4 or parts[1] not in ("f", "r"):
        return None
    try:
        return LatLon(int(parts[2]) / COORD, int(parts[3]) / COORD)
    except ValueError:
        return None
