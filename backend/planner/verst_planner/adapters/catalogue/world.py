"""The composed world `russia_v1` (ADR-0012 §4): fixture world + catalogue + fictional services.

The fixture world stays authoritative for its towns, places, roads, tolls, prices and ready routes. A
catalogue town or POI that CI linked to a fixture item (`Catalogue.links`) is dropped in favour of the
fixture one, which keeps its id and gains the photo. Catalogue POIs become sights (`Source.OSM` semantics:
open data, not curated); every other catalogue town gets fictional hotels and cafes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from verst_planner.adapters.catalogue.synthetic import cafes_for, hotels_for
from verst_planner.adapters.fake.prices import FakePriceRepository
from verst_planner.adapters.fake.world import FakeWorld
from verst_planner.catalogue import Catalogue, CatPoi
from verst_planner.domain.enums import PlaceStatus, PlaceType, Source, Tag
from verst_planner.domain.model import LatLon, PartnerIds, Place, RegionInfo, Town

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
}
POI_HOURS = {"museum": "Tu-Su 10:00-18:00", "church": "Mo-Su 08:00-20:00"}
POI_TICKETS = {"museum": (400, 200), "kremlin": (300, 150), "monastery": (300, 150)}
BIG_MUSEUM_SITELINKS = 40


def poi_rating(sitelinks: int) -> float:
    return round(3.6 + 1.3 * min(1.0, math.log10(1 + sitelinks) / math.log10(1 + 150)), 2)


def poi_place(p: CatPoi, town_id: str, region: str) -> Place:
    ticket = POI_TICKETS.get(p.kind)
    tags = set(POI_TAGS[p.kind])
    if ticket is None:
        tags.add(Tag.FREE_ENTRY)
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
        opening_hours=POI_HOURS.get(p.kind),
        dwell_min=dwell,
        avg_check_rub=None,
        price_night_rub=None,
        ticket_adult_rub=ticket[0] if ticket else None,
        ticket_child_rub=ticket[1] if ticket else None,
        rating_internal=poi_rating(p.sitelinks),
        tags=frozenset(tags),
        description_ru=p.desc,
        partner_ids=PartnerIds(None, None),
        source=Source.OSM,
        verified_at=None,
        status=PlaceStatus.LIVE,
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


def compose(fixture: FakeWorld, cat: Catalogue, world_id: str = WORLD_ID) -> CatalogueWorld:
    regions: dict[str, RegionInfo] = dict(cat.regions)
    regions.update(fixture.regions)  # fixture names/tz win for the regions they define
    prices = FakePriceRepository(fixture)
    towns: dict[str, Town] = dict(fixture.towns)
    places: dict[str, Place] = dict(fixture.places)
    out = CatalogueWorld(world=fixture, catalogue=cat)

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

    out.world = FakeWorld(
        id=world_id,
        as_of=fixture.as_of,
        regions=regions,
        nodes=fixture.nodes,
        edges=fixture.edges,
        towns=towns,
        town_node=fixture.town_node,
        places=places,
        region_prices=fixture.region_prices,
        tolls=fixture.tolls,
        ready_routes=fixture.ready_routes,
        food_check_by_population=fixture.food_check_by_population,
        lodging_night_by_population=fixture.lodging_night_by_population,
        adjacency=fixture.adjacency,
    )
    return out


def point_of(cw: CatalogueWorld, place_id: str) -> LatLon | None:
    p = cw.world.places.get(place_id)
    return p.point if p is not None else None
