"""The composed world `russia_v1` (ADR-0012 §4): fixture world + catalogue + fictional services.

The fixture world stays authoritative for its towns, places, roads, tolls, prices and ready routes. A
catalogue town or POI that CI linked to a fixture item (`Catalogue.links`) is dropped in favour of the
fixture one, which keeps its id and gains the photo. Catalogue POIs become sights (`Source.OSM` semantics:
open data, not curated); every other catalogue town gets fictional hotels and cafes.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field

from verst_planner import resources
from verst_planner.adapters.catalogue.synthetic import cafes_for, hotels_for
from verst_planner.adapters.fake.prices import FakePriceRepository
from verst_planner.adapters.fake.world import Edge, FakeWorld, Node
from verst_planner.catalogue import Catalogue, CatFood, CatLodging, CatPoi, CatRoadside
from verst_planner.domain.enums import FuelType, PlaceStatus, PlaceType, RoadClass, Source, Tag
from verst_planner.domain.model import LatLon, PartnerIds, Place, RegionInfo, Town
from verst_planner.explain import ru

WORLD_ID = "russia_v1"

POI_TAGS: dict[str, frozenset[Tag]] = {
    "museum": frozenset({Tag.MUSEUM}),
    "kremlin": frozenset({Tag.KREMLIN, Tag.WALK}),
    "monastery": frozenset({Tag.MONASTERY, Tag.WALK}),
    "church": frozenset(),
    "monument": frozenset({Tag.WALK}),
    "park": frozenset({Tag.WALK}),
    "viewpoint": frozenset({Tag.VIEW, Tag.WALK}),
    "embankment": frozenset({Tag.VIEW, Tag.WALK}),
    "square": frozenset({Tag.WALK}),
    "attraction": frozenset({Tag.WALK}),
    # Sprint 4 kinds (ADR-0015 §2)
    "theatre": frozenset({Tag.WALK}),  # the building and its square; a show is not a road-trip stop
    "zoo": frozenset({Tag.WALK}),
    "nature": frozenset({Tag.WALK, Tag.VIEW}),
    "interactive": frozenset(),
    "playground": frozenset({Tag.PLAYGROUND, Tag.WALK}),
}
POI_DWELL = {
    "museum": 75,
    "kremlin": 60,
    "monastery": 60,
    "church": 20,
    "monument": 15,
    "park": 40,
    "viewpoint": 20,
    "embankment": 20,
    "square": 15,
    "attraction": 30,
    "theatre": 15,
    "zoo": 90,
    "nature": 40,
    "interactive": 60,
    "playground": 20,
}
POI_HOURS = {
    "museum": "Tu-Su 10:00-18:00",
    "church": "Mo-Su 08:00-20:00",
    "zoo": "Mo-Su 09:00-19:00",
    "interactive": "Tu-Su 10:00-19:00",
}
POI_TICKETS = {
    "museum": (400, 200),
    "kremlin": (300, 150),
    "monastery": (300, 150),
    "zoo": (500, 250),
    "interactive": (500, 300),
}
FREE_KINDS = frozenset(
    {"church", "monument", "park", "viewpoint", "embankment", "square", "theatre", "nature", "playground"}
)
"""ADR-0019 E-2: kinds with no entry to pay (public spaces, a theatre seen from its square, a church) are free
by their kind; any other kind without a price is «цена неизвестна», never silently free."""
BIG_MUSEUM_SITELINKS = 40


_RATING: dict[int, float] = {}


def poi_rating(sitelinks: int) -> float:
    r = _RATING.get(sitelinks)
    if r is None:
        r = _RATING[sitelinks] = round(
            3.6 + 1.3 * min(1.0, math.log10(1 + sitelinks) / math.log10(1 + 150)), 2
        )
    return r


# catalogue kind → ADR-0015 §2 category (the diversity rules count «temple» and «monastery» as religious)
POI_CATEGORY = {"church": "temple"}
_HOURS_OK: dict[str, bool] = {}


def _hours_ok(text: str) -> bool:
    ok = _HOURS_OK.get(text)
    if ok is None:
        from verst_planner.hours import parse

        try:
            parse(text)
            ok = True
        except Exception:
            ok = False
        _HOURS_OK[text] = ok
    return ok


_NO_PARTNERS = PartnerIds(None, None)
_TAGS: dict[tuple[str, bool], frozenset[Tag]] = {}


def _tags(kind: str, free: bool) -> frozenset[Tag]:
    """The kind's tags (+ FREE_ENTRY), one shared frozenset per (kind, free): 20 k POIs, a few dozen sets."""
    t = _TAGS.get((kind, free))
    if t is None:
        t = _TAGS[(kind, free)] = POI_TAGS[kind] | ({Tag.FREE_ENTRY} if free else frozenset())
    return t


def poi_ticket(p: CatPoi) -> tuple[tuple[int, int] | None, bool]:
    """(ticket estimate, free). OSM `fee=no` is free; a kind with a default ticket gets the estimate (the card
    says «примерная»); a free kind without `fee=yes` is free; anything else has an unknown price (E-2)."""
    if p.fee is False:
        return None, True
    ticket = POI_TICKETS.get(p.kind)
    if ticket is not None:
        return ticket, False
    return None, p.fee is None and p.kind in FREE_KINDS


def poi_place(p: CatPoi, town_id: str, region: str) -> Place:
    ticket, free = poi_ticket(p)
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
        opening_hours=p.hours if p.hours and _hours_ok(p.hours) else POI_HOURS.get(p.kind),
        dwell_min=dwell,
        avg_check_rub=None,
        price_night_rub=None,
        ticket_adult_rub=ticket[0] if ticket else None,
        ticket_child_rub=ticket[1] if ticket else None,
        rating_internal=poi_rating(p.sitelinks),
        tags=_tags(p.kind, free),
        description_ru=p.desc,
        partner_ids=_NO_PARTNERS,
        source=Source.OSM,
        verified_at=None,
        status=PlaceStatus.LIVE,
        category=POI_CATEGORY.get(p.kind, p.kind),
        quality=p.quality,
        heritage=p.heritage,
        card_level=p.level,
    )


# ------------------------------------------------------------------ real stops (CEO 02.11, option a)

REAL_STOPS_FIXTURE_TYPES = frozenset({PlaceType.LODGING, PlaceType.FOOD, PlaceType.FUEL, PlaceType.REST})
"""The fixture world's hand-made places of these types are dropped when the real OSM stops are loaded: they
were made for the demo (CEO 02.11: real hotels, not invented ones)."""
FOOD_DWELL_MIN = 60
FOOD_TRIP_CAP = 12
"""Cafés per town a trip's lunch can stop at (the walk reads every café from the catalogue itself)."""
FOOD_TRIP_ORDER = {"restaurant": 0, "cafe": 1, "food_court": 2, "fast_food": 3}
ROADSIDE_TYPE = {"fuel": PlaceType.FUEL, "rest_area": PlaceType.REST, "services": PlaceType.REST}
FUEL_OF = {"ai92": FuelType.AI92, "ai95": FuelType.AI95, "dt": FuelType.DT}
REGION_RADIUS_KM = 2000.0
Stops = tuple[list[CatLodging], list[CatRoadside]]


def lodging_place(lo: CatLodging, town_id: str, region: str) -> Place:
    """A real OSM lodging: no price (OSM has none: the night says so), dogs only as tagged, no rating."""
    tags: frozenset[Tag] = frozenset({Tag.DOGS_ALLOWED}) if lo.dog is True else frozenset()
    tags_no: frozenset[Tag] = frozenset({Tag.DOGS_ALLOWED}) if lo.dog is False else frozenset()
    return Place(
        id=lo.id,
        type=PlaceType.LODGING,
        name_ru=lo.name,
        point=lo.point,
        address=None,
        region_code=region,
        town_id=town_id,
        opening_hours=None,
        dwell_min=None,
        avg_check_rub=None,
        price_night_rub=None,
        ticket_adult_rub=None,
        ticket_child_rub=None,
        rating_internal=None,
        tags=tags,
        description_ru=None,
        partner_ids=_NO_PARTNERS,
        source=Source.OSM,
        verified_at=None,
        status=PlaceStatus.LIVE,
        category=lo.kind,
        tags_no=tags_no,
    )


def food_place(f: CatFood, town_id: str, region: str) -> Place:
    """A real OSM restaurant or café for a lunch stop: no check (OSM has none)."""
    return Place(
        id=f.id,
        type=PlaceType.FOOD,
        name_ru=f.name,
        point=f.point,
        address=None,
        region_code=region,
        town_id=town_id,
        opening_hours=f.hours if f.hours and _hours_ok(f.hours) else None,
        dwell_min=FOOD_DWELL_MIN,
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


def roadside_place(r: CatRoadside, region: str) -> Place:
    """A real OSM fuel station or rest area: fuels, toilets and a café only as tagged."""
    ptype = ROADSIDE_TYPE[r.kind]
    tags: set[Tag] = set()
    tags_no: set[Tag] = set()
    hours = r.hours if r.hours and _hours_ok(r.hours) else None
    if hours == "24/7":
        tags.add(Tag.H24)
    if r.wc is True:
        tags.add(Tag.WC)
    elif r.wc is False:
        tags_no.add(Tag.WC)
    if ptype is PlaceType.FUEL and r.cafe is True:
        tags.add(Tag.CAFE_AT_FUEL)
    elif ptype is PlaceType.FUEL and r.cafe is False:
        tags_no.add(Tag.CAFE_AT_FUEL)
    generic = "fuel" if ptype is PlaceType.FUEL else "rest"
    return Place(
        id=r.id,
        type=ptype,
        name_ru=r.name or ru.text(f"synthetic.{generic}"),
        point=r.point,
        address=None,
        region_code=region,
        town_id=None,
        opening_hours=hours,
        dwell_min=None,
        avg_check_rub=None,
        price_night_rub=None,
        ticket_adult_rub=None,
        ticket_child_rub=None,
        rating_internal=None,
        tags=frozenset(tags),
        description_ru=None,
        partner_ids=_NO_PARTNERS,
        source=Source.OSM,
        verified_at=None,
        status=PlaceStatus.LIVE,
        category=r.kind,
        tags_no=frozenset(tags_no),
        fuel_kinds=frozenset(FUEL_OF[f] for f in r.fuels),
        fuel_kinds_no=frozenset(FUEL_OF[f] for f in r.fuels_no),
    )


def town_quality(sitelinks_sum: int) -> int:
    if sitelinks_sum >= 300:
        return 3
    if sitelinks_sum >= 100:
        return 2
    return 1 if sitelinks_sum >= 20 else 0


@dataclass(slots=True)
class CatalogueWorld:
    """The composed `FakeWorld` plus the catalogue facts the bridge needs (photos, kinds, links)."""

    world: FakeWorld
    catalogue: Catalogue
    town_of_qid: dict[str, str] = field(default_factory=dict)
    """Catalogue town id → composed town id (a fixture id when linked)."""
    qid_of_place: dict[str, str] = field(default_factory=dict)
    """Composed place/town id → Wikidata id (fixture items through links, catalogue items are their id)."""
    poi_kind: dict[str, str] = field(default_factory=dict)
    """Composed sight id → catalogue POI kind (fixture sights from their tags)."""
    synthetic_towns: set[str] = field(default_factory=set)
    real_stops: bool = False
    """CEO 02.11: the real OSM lodgings, food and roadside places replace every invented one (no synthetic
    hotels, cafés, fuel or rest places, no fixture ones of those types)."""
    lodging_info: dict[str, CatLodging] = field(default_factory=dict)
    """The real lodgings' OSM facts the place does not carry (stars, website, phone) for the hotel card."""
    roadside: list[CatRoadside] = field(default_factory=list)
    """The real fuel stations and rest areas: built into places only along a queried corridor (29 000 of them
    would double the catalogue load on the phone), like the synthetic ones were."""


def with_bypasses(
    fixture: FakeWorld,
) -> tuple[dict[str, Node], list[Edge], dict[str, list[tuple[Edge, str]]]]:
    """The fixture graph plus `resources/bypass_roads.json` (МКАД, ЦКАД; ADR-0015 §2), for `russia_v1`."""
    import json

    doc = json.loads(resources.read_text("bypass_roads.json"))
    nodes = dict(fixture.nodes)
    for n in doc["nodes"]:
        nodes[n["id"]] = Node(n["id"], LatLon(float(n["lat"]), float(n["lon"])), n["region"])
    edges = list(fixture.edges)
    adjacency = {k: list(v) for k, v in fixture.adjacency.items()}
    for e in doc["edges"]:
        a, b = e["from"], e["to"]
        edge = Edge(
            index=len(edges),
            a=a,
            b=b,
            pa=nodes[a].point,
            pb=nodes[b].point,
            km=float(e["km"]),
            speed_kmh=float(e["speedKmh"]),
            road_class=RoadClass(e["roadClass"]),
            ref=e.get("ref"),
            toll=bool(e.get("toll", False)),
        )
        edges.append(edge)
        adjacency.setdefault(a, []).append((edge, b))
        adjacency.setdefault(b, []).append((edge, a))
    for lst in adjacency.values():
        lst.sort(key=lambda eo: (eo[1], eo[0].index))
    return nodes, edges, adjacency


def compose(
    fixture: FakeWorld, cat: Catalogue, world_id: str = WORLD_ID, stops: Stops | None = None
) -> CatalogueWorld:
    regions: dict[str, RegionInfo] = dict(cat.regions)
    regions.update(fixture.regions)  # fixture names/tz win for the regions they define
    prices = FakePriceRepository(fixture)
    towns: dict[str, Town] = dict(fixture.towns)
    places: dict[str, Place] = dict(fixture.places)
    out = CatalogueWorld(world=fixture, catalogue=cat, real_stops=stops is not None)
    if stops is not None:
        places = {k: p for k, p in places.items() if p.type not in REAL_STOPS_FIXTURE_TYPES}

    linked_qids: dict[str, str] = {}
    for fid, link in cat.links.items():
        linked_qids.setdefault(link.wikidata, fid)
        out.qid_of_place[fid] = link.wikidata

    sitelinks_sum: dict[str, int] = {}
    for p in cat.pois:
        sitelinks_sum[p.town] = sitelinks_sum.get(p.town, 0) + p.sitelinks

    for t in cat.towns:
        linked = linked_qids.get(t.id)
        if linked is not None and linked in fixture.towns:
            out.town_of_qid[t.id] = linked
            continue
        quality = town_quality(sitelinks_sum.get(t.id, 0))
        town = Town(
            id=t.id,
            name_ru=t.name,
            name_prep_ru=t.prep,
            point=t.point,
            region_code=t.region,
            population=t.population,
            quality=quality,
            evening_walk=quality >= 2,
            lodging_count_cache=3,
            name_gen_ru=t.gen,
        )
        towns[t.id] = town
        out.town_of_qid[t.id] = t.id
        out.qid_of_place[t.id] = t.id
        if stops is not None:
            continue
        out.synthetic_towns.add(t.id)
        for h in hotels_for(town, prices.lodging_default_night(t.population)):
            places[h.id] = h
        for c in cafes_for(town, prices.food_default_check(t.population)):
            places[c.id] = c

    for p in cat.pois:
        if p.id in linked_qids:
            continue
        town_id = out.town_of_qid.get(p.town)
        if town_id is None:
            continue
        place = poi_place(p, town_id, towns[town_id].region_code)
        places[place.id] = place
        out.qid_of_place[place.id] = p.id
        out.poi_kind[place.id] = p.kind

    if stops is not None:
        _add_real_stops(towns, places, out, cat, stops)

    nodes, edges, adjacency = with_bypasses(fixture)
    out.world = FakeWorld(
        id=world_id,
        as_of=fixture.as_of,
        regions=regions,
        nodes=nodes,
        edges=edges,
        towns=towns,
        town_node=fixture.town_node,
        places=places,
        region_prices=fixture.region_prices,
        tolls=fixture.tolls,
        ready_routes=fixture.ready_routes,
        food_check_by_population=fixture.food_check_by_population,
        lodging_night_by_population=fixture.lodging_night_by_population,
        adjacency=adjacency,
    )
    return out


def _add_real_stops(
    towns: dict[str, Town], places: dict[str, Place], out: CatalogueWorld, cat: Catalogue, stops: Stops
) -> None:
    """Real lodgings and lunch places of the towns, and the roadside places of the country (CEO 02.11)."""
    lodgings, roadside = stops
    count: dict[str, int] = {}
    for lo in lodgings:
        tid = out.town_of_qid.get(lo.town)
        if tid is None:
            continue
        places[lo.id] = lodging_place(lo, tid, towns[tid].region_code)
        out.lodging_info[lo.id] = lo
        count[tid] = count.get(tid, 0) + 1
    for tid, t in list(towns.items()):
        n = count.get(tid, 0)
        if t.lodging_count_cache != n:
            towns[tid] = dataclasses.replace(t, lodging_count_cache=n)
    by_town: dict[str, list[CatFood]] = {}
    for f in cat.food:
        tid = out.town_of_qid.get(f.town)
        if tid is not None and f.id not in places:
            by_town.setdefault(tid, []).append(f)
    for tid, lst in by_town.items():
        # restaurants and cafés with known hours first, then by distance from the centre
        centre = towns[tid].point
        lst.sort(
            key=lambda f: (
                FOOD_TRIP_ORDER.get(f.kind, 9),
                f.hours is None,
                (f.point.lat - centre.lat) ** 2 + (f.point.lon - centre.lon) ** 2,
                f.id,
            )
        )
        for f in lst[:FOOD_TRIP_CAP]:
            places[f.id] = food_place(f, tid, towns[tid].region_code)
    out.roadside = list(roadside)


def point_of(cw: CatalogueWorld, place_id: str) -> LatLon | None:
    p = cw.world.places.get(place_id)
    return p.point if p is not None else None
