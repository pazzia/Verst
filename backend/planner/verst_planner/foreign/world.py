"""The server-only world `world_v1` (CEO 29.10): `russia_v1` + the catalogues abroad found on disk.

Composition: every town, place and region of `russia_v1` as they are, plus per country abroad
* its regions (ISO 3166-2 codes with their IANA zones, from `meta.regions`);
* its towns (no fictional hotels or cafés: there are no prices abroad, a night or a meal there is unknown);
* its POIs as sights — no default ticket («цена неизвестна») and no default opening hours, only OSM's; a
  fortress catalogued with the kremlin kind is labelled «Крепость»;
* its OSM restaurants and cafés as food places without a check.

`Borders` is the world's `BorderPort`: the point check (supported country, closed border) and the crossings
between two waypoints (`border_crossings.json`, anchored at the nearest catalogue town; `coordsApprox`).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from verst_planner.adapters.catalogue import CataloguePorts, CatalogueWorld
from verst_planner.adapters.catalogue.repos import (
    CatalogueGeocoding,
    IndexedPlaceRepository,
    RegionByNearestTown,
)
from verst_planner.adapters.catalogue.world import (
    BIG_MUSEUM_SITELINKS,
    FREE_KINDS,
    POI_DWELL,
    _hours_ok,
    _tags,
    poi_rating,
    town_quality,
)
from verst_planner.adapters.fake.prices import FakePriceRepository
from verst_planner.adapters.fake.world import FakeWorld
from verst_planner.catalogue import CatFood, CatPoi
from verst_planner.domain.enums import PlaceStatus, PlaceType, Source
from verst_planner.domain.errors import InvalidInput
from verst_planner.domain.model import BorderPoint, LatLon, PartnerIds, Place, RegionInfo, Town
from verst_planner.explain import ru
from verst_planner.foreign.catalogues import CountryCatalogue
from verst_planner.foreign.locator import INSIDE_KM, CountryLocator
from verst_planner.foreign.rates import Rates
from verst_planner.foreign.rules import RUSSIA, Crossing, Rules
from verst_planner.geo.distance import haversine_km

WORLD_ID = "world_v1"
FOOD_KINDS_ABROAD = frozenset({"restaurant", "cafe", "fast_food"})
FOOD_DWELL = 60
SAMPLE_KM = 5.0
_NO_PARTNERS = PartnerIds(None, None)


def abroad_poi(p: CatPoi, town_id: str, region: str) -> Place:
    """A POI abroad as a sight: like `russia_v1`'s, but no rouble ticket estimate and no assumed hours."""
    free = p.fee is False or (p.fee is None and p.kind in FREE_KINDS)
    dwell = POI_DWELL[p.kind]
    if p.kind == "museum" and p.sitelinks >= BIG_MUSEUM_SITELINKS:
        dwell = 90
    return Place(
        id=p.id,
        type=PlaceType.SIGHT,
        name_ru=p.name,
        point=p.point,
        address=None,
        region_code=region,
        town_id=town_id,
        opening_hours=p.hours if p.hours and _hours_ok(p.hours) else None,
        dwell_min=dwell,
        avg_check_rub=None,
        price_night_rub=None,
        ticket_adult_rub=None,
        ticket_child_rub=None,
        rating_internal=poi_rating(p.sitelinks),
        tags=_tags(p.kind, free),
        description_ru=p.desc,
        partner_ids=_NO_PARTNERS,
        source=Source.OSM,
        verified_at=None,
        status=PlaceStatus.LIVE,
        category={"church": "temple", "kremlin": "fortress"}.get(p.kind, p.kind),
        quality=p.quality,
        heritage=p.heritage,
        card_level=p.level,
    )


def abroad_food(f: CatFood, town_id: str, region: str) -> Place:
    """An OSM restaurant or café abroad: a food stop with no check (the meal's price is unknown)."""
    return Place(
        id=f.id,
        type=PlaceType.FOOD,
        name_ru=f.name,
        point=f.point,
        address=None,
        region_code=region,
        town_id=town_id,
        opening_hours=f.hours if f.hours and _hours_ok(f.hours) else None,
        dwell_min=FOOD_DWELL,
        avg_check_rub=None,
        price_night_rub=None,
        ticket_adult_rub=None,
        ticket_child_rub=None,
        rating_internal=None,
        tags=frozenset(),
        description_ru=None,
        partner_ids=_NO_PARTNERS,
        source=Source.OSM,
        verified_at=None,
        status=PlaceStatus.LIVE,
        category=f.kind,
    )


@dataclass(slots=True)
class Composed:
    world: FakeWorld
    cw: CatalogueWorld
    country_of_region: dict[str, str]
    abroad_towns: list[tuple[str, Town]]


def compose(ru: CatalogueWorld, cats: Iterable[CountryCatalogue], world_id: str = WORLD_ID) -> Composed:
    base = ru.world
    regions: dict[str, RegionInfo] = dict(base.regions)
    towns: dict[str, Town] = dict(base.towns)
    places: dict[str, Place] = dict(base.places)
    country_of_region = {code: RUSSIA for code in regions}
    cw = CatalogueWorld(
        world=base,
        catalogue=ru.catalogue,
        town_of_qid=dict(ru.town_of_qid),
        qid_of_place=dict(ru.qid_of_place),
        poi_kind=dict(ru.poi_kind),
        synthetic_towns=set(ru.synthetic_towns),
    )
    abroad_towns: list[tuple[str, Town]] = []
    for cc in cats:
        cat = cc.catalogue
        sitelinks: dict[str, int] = {}
        for p in cat.pois:
            sitelinks[p.town] = sitelinks.get(p.town, 0) + p.sitelinks
        for t in cat.towns:
            if t.id in towns:
                continue  # first wins (Russia, then the folders in order)
            quality = town_quality(sitelinks.get(t.id, 0))
            town = Town(
                id=t.id,
                name_ru=t.name,
                name_prep_ru=t.prep,
                point=t.point,
                region_code=t.region,
                population=t.population,
                quality=quality,
                evening_walk=quality >= 2,
                lodging_count_cache=0,
                name_gen_ru=t.gen,
            )
            towns[t.id] = town
            abroad_towns.append((cc.code, town))
            country_of_region[t.region] = cc.code  # Abkhazia's GE-AB belongs to AB, whose towns use it
            cw.town_of_qid[t.id] = t.id
            cw.qid_of_place[t.id] = t.id
        for code, info in cat.regions.items():
            regions.setdefault(code, info)
            country_of_region.setdefault(code, cc.code)
        for p in cat.pois:
            home = towns.get(p.town)
            if p.id in places or home is None or country_of_region.get(home.region_code) != cc.code:
                continue
            places[p.id] = abroad_poi(p, home.id, home.region_code)
            cw.qid_of_place[p.id] = p.id
            cw.poi_kind[p.id] = p.kind
        for f in cat.food:
            home = towns.get(f.town)
            if f.kind not in FOOD_KINDS_ABROAD or f.id in places or home is None:
                continue
            if country_of_region.get(home.region_code) != cc.code:
                continue
            places[f.id] = abroad_food(f, home.id, home.region_code)
    world = FakeWorld(
        id=world_id,
        as_of=base.as_of,
        regions=regions,
        nodes=base.nodes,
        edges=base.edges,
        towns=towns,
        town_node=base.town_node,
        places=places,
        region_prices=base.region_prices,
        tolls=base.tolls,
        ready_routes=base.ready_routes,
        food_check_by_population=base.food_check_by_population,
        lodging_night_by_population=base.lodging_night_by_population,
        adjacency=base.adjacency,
    )
    cw.world = world
    return Composed(world, cw, country_of_region, abroad_towns)


# ---------------------------------------------------------------------------------------------- borders


class Borders:
    """`BorderPort` of `world_v1`."""

    def __init__(
        self,
        locator: CountryLocator,
        rules: Rules,
        towns: Iterable[tuple[str, Town]],
        loaded: frozenset[str],
    ) -> None:
        self.locator = locator
        self.rules = rules
        self.loaded = loaded
        self.now: Callable[[], datetime] = lambda: datetime.now(UTC)
        """The planner's clock (set by the planner: a closure ends on a date)."""
        self.by_name: dict[tuple[str, str], list[Town]] = {}
        for code, t in towns:
            self.by_name.setdefault((code, t.name_ru), []).append(t)
        for lst in self.by_name.values():
            lst.sort(key=lambda t: (-t.population, t.id))

    def supported(self, country: str) -> bool:
        return country == RUSSIA or (country in self.loaded and country in self.rules.countries)

    def check_point(self, point: LatLon, field: str) -> None:
        country = self.locator.country_at(point)
        if country is None:
            raise InvalidInput(field, "outside_supported", message_ru=ru.text("abroad.outside.unknown"))
        if not self.supported(country):
            raise InvalidInput(
                field, "outside_supported", country=country, message_ru=ru.text("abroad.outside.country")
            )
        rules = self.rules.countries.get(country)
        closed = rules.closed if rules is not None else None
        if closed is not None and closed.active(self.now()):
            raise InvalidInput(
                field,
                "border_closed",
                country=country,
                message_ru=closed.message_ru,
                until=closed.until_local.isoformat(),
            )

    def open_countries(self) -> frozenset[str]:
        now = self.now()
        return frozenset(
            c
            for c in self.loaded | {RUSSIA}
            if self.supported(c)
            and not ((r := self.rules.countries.get(c)) is not None and r.closed and r.closed.active(now))
        )

    def crossings(self, a: LatLon, b: LatLon) -> list[BorderPoint]:
        ca, cb = self.locator.country_at(a), self.locator.country_at(b)
        if ca is None or cb is None or ca == cb:
            return []
        path = self.rules.path(ca, cb, self.open_countries())
        if path is None:
            raise InvalidInput("destination", "no_crossing", country=cb)
        out: list[BorderPoint] = []
        start, cur = a, ca
        for c in path:
            nxt = c.between[1] if c.between[0] == cur else c.between[0]
            bp = self._point(c, cur, nxt, start, b)
            out.append(bp)
            start, cur = bp.point, nxt
        return out

    # ------------------------------------------------------------------ where a crossing is
    def _point(self, c: Crossing, frm: str, to: str, a: LatLon, b: LatLon) -> BorderPoint:
        line = self._line_crossing(a, b, frm)
        anchor = c.anchor
        if anchor is not None and anchor.country in (frm, to):
            for name in anchor.towns:
                hits = self.by_name.get((anchor.country, name), [])
                hits = [t for t in hits if anchor.region is None or t.region_code == anchor.region]
                if hits:
                    return self._at(c, frm, to, hits[0], "border.coords.anchor")
            if anchor.region is not None:
                in_region = [
                    t
                    for (code, _name), lst in self.by_name.items()
                    if code == anchor.country
                    for t in lst
                    if t.region_code == anchor.region
                ]
                if in_region:
                    t = min(in_region, key=lambda t: (haversine_km(t.point, line), t.id))
                    return self._at(c, frm, to, t, "border.coords.region")
        town = self.locator.nearest_of(line, frm, INSIDE_KM)
        if town is not None:
            return self._at(c, frm, to, town, "border.coords.line_town")
        note = ru.text("border.coords.line")
        return BorderPoint(c.id, c.name_ru, line, frm, to, c.marker, True, None, note)

    @staticmethod
    def _at(c: Crossing, frm: str, to: str, t: Town, key: str) -> BorderPoint:
        note = ru.text(key, town=t.name_ru)
        return BorderPoint(c.id, c.name_ru, t.point, frm, to, c.marker, True, t.id, note)

    def _line_crossing(self, a: LatLon, b: LatLon, frm: str) -> LatLon:
        """The last point of country `frm` before the straight line a→b first reaches another country,
        sampled every `SAMPLE_KM`, by the nearest town within 60 km (a sample far from towns is skipped)."""
        n = max(1, math.ceil(haversine_km(a, b) / SAMPLE_KM))
        last = a
        for k in range(n + 1):
            f = k / n
            p = LatLon(a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f)
            country = self.locator.town_country(p)  # far from towns is no evidence of a border
            if country == frm:
                last = p
            elif country is not None:
                return last
        return last


# ---------------------------------------------------------------------------------------------- the world


@dataclass(slots=True)
class AbroadWorld:
    world: FakeWorld
    cw: CatalogueWorld
    ports: CataloguePorts
    """Ports over the whole world (geocoding, places, regions); the Russian ones for routing and tolls."""
    russian: CataloguePorts
    locator: CountryLocator
    borders: Borders
    rules: Rules
    countries: dict[str, CountryCatalogue]
    country_of_region: dict[str, str]
    rates: Rates | None = None
    loaded_from: str | None = None
    errors: list[str] = field(default_factory=list)

    def country_of(self, region_code: str) -> str | None:
        hit = self.country_of_region.get(region_code)
        if hit is not None:
            return hit
        return RUSSIA if region_code == RUSSIA or region_code.startswith(RUSSIA + "-") else None

    def info(self) -> dict[str, object]:
        return {
            "world": self.world.id,
            "countries": sorted(self.countries),
            "towns": len(self.world.towns),
            "places": len(self.world.places),
            "dir": self.loaded_from,
            "rates": self.rates.as_of if self.rates is not None else None,
        }


def build(
    ru: CatalogueWorld,
    russian: CataloguePorts,
    cats: list[CountryCatalogue],
    rates: Rates | None = None,
    rules: Rules | None = None,
    loaded_from: Path | None = None,
) -> AbroadWorld:
    rules = rules or Rules.from_resources()
    comp = compose(ru, cats)
    world = comp.world
    ru_towns = [
        t for t in world.towns.values() if comp.country_of_region.get(t.region_code, RUSSIA) == RUSSIA
    ]
    locator = CountryLocator(ru_towns, comp.abroad_towns)
    regions = RegionByNearestTown(world)
    places = IndexedPlaceRepository(world, regions)
    popularity = {
        pid: ru.catalogue.poi_by_id[q].sitelinks
        for pid, q in comp.cw.qid_of_place.items()
        if q in ru.catalogue.poi_by_id
    }
    for cc in cats:
        for p in cc.catalogue.pois:
            popularity.setdefault(p.id, p.sitelinks)
    ports = CataloguePorts(
        routing=russian.routing,
        geocoding=CatalogueGeocoding(world, popularity, places.town_index),
        places=places,
        prices=FakePriceRepository(world),
        tolls=russian.tolls,
        regions=regions,
        clock=russian.clock,
        world=comp.cw,
        parking=russian.parking,
    )
    countries = {cc.code: cc for cc in cats}
    borders = Borders(
        locator, rules, comp.abroad_towns + [(RUSSIA, t) for t in ru_towns], frozenset(countries)
    )
    return AbroadWorld(
        world=world,
        cw=comp.cw,
        ports=ports,
        russian=russian,
        locator=locator,
        borders=borders,
        rules=rules,
        countries=countries,
        country_of_region=comp.country_of_region,
        rates=rates,
        loaded_from=str(loaded_from) if loaded_from is not None else None,
    )


__all__ = ["WORLD_ID", "AbroadWorld", "Borders", "Composed", "abroad_food", "abroad_poi", "build", "compose"]
