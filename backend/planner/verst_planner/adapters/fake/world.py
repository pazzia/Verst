"""World fixtures: one JSON file feeding every fake adapter (A§5.2).

Loader rules (``ValueError`` with the JSON path on violation): unique ids; every edge
``km >= 0.95 x haversine(from, to)``; every place has exactly one of ``lat/lon`` or ``anchor``; tags within
the closed list; town nodes exist; ready-route points resolve; a ``RU`` price row exists for every fuel type.

Anchors: ``{"edge": [a, b], "km": k, "lateralKm": l}`` is the point at fraction ``k / edge.km`` along the
straight segment a→b, offset ``l`` km to the left (positive) or right (negative) of the direction of travel;
``{"node": n, "dxKm": x, "dyKm": y}`` is the node offset east/north. Offsets use the local equirectangular
frame of `geo.distance` so a place anchored at ``lateralKm: 14.9`` projects at 14.9 km.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from verst_planner.domain.enums import FuelType, PlaceStatus, PlaceType, RoadClass, Source, Tag
from verst_planner.domain.model import (
    LatLon,
    PartnerIds,
    Place,
    ReadyRoute,
    ReadyRoutePoint,
    RegionInfo,
    RegionPrice,
    TollSegment,
    Town,
)
from verst_planner.geo.distance import KM_PER_DEG_LAT, KM_PER_DEG_LON_EQUATOR, haversine_km

EDGE_MIN_RATIO = 0.95
_TAG_VALUES = frozenset(t.value for t in Tag)


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    point: LatLon
    region: str


@dataclass(frozen=True, slots=True)
class Edge:
    index: int
    a: str
    b: str
    pa: LatLon
    pb: LatLon
    km: float
    speed_kmh: float
    road_class: RoadClass
    ref: str | None
    toll: bool

    @property
    def minutes(self) -> float:
        return self.km / self.speed_kmh * 60.0


@dataclass(frozen=True, slots=True)
class TollDef:
    segment: TollSegment
    edge: Edge
    a: str  # direction of fromKm/toKm along the edge
    from_km: float
    to_km: float


@dataclass(slots=True)
class FakeWorld:
    id: str
    as_of: date
    regions: dict[str, RegionInfo]
    nodes: dict[str, Node]
    edges: list[Edge]
    towns: dict[str, Town]
    town_node: dict[str, str]
    places: dict[str, Place]
    region_prices: list[RegionPrice]
    tolls: list[TollDef]
    ready_routes: dict[str, ReadyRoute]
    food_check_by_population: list[tuple[int, int]]
    lodging_night_by_population: list[tuple[int, int]]
    adjacency: dict[str, list[tuple[Edge, str]]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> FakeWorld:
        with Path(path).open(encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FakeWorld:
        return _Loader(d).build()

    def edge_between(self, a: str, b: str) -> Edge | None:
        for e, other in self.adjacency.get(a, ()):
            if other == b:
                return e
        return None

    def region_of_point(self, p: LatLon) -> str:
        """Region of the nearest node (ties by node id)."""
        best = min(self.nodes.values(), key=lambda n: (haversine_km(n.point, p), n.id))
        return best.region


def offset_local(origin: LatLon, dx_km: float, dy_km: float, cos_phi: float | None = None) -> LatLon:
    """`origin` moved `dx_km` east and `dy_km` north in the local equirectangular frame."""
    c = math.cos(math.radians(origin.lat)) if cos_phi is None else cos_phi
    return LatLon(origin.lat + dy_km / KM_PER_DEG_LAT, origin.lon + dx_km / (KM_PER_DEG_LON_EQUATOR * c))


def point_on_edge(pa: LatLon, pb: LatLon, frac: float, lateral_km: float = 0.0) -> LatLon:
    """Point at `frac` along the straight segment pa→pb, `lateral_km` to the left of travel."""
    cos_phi = math.cos(math.radians((pa.lat + pb.lat) / 2))
    bx = (pb.lon - pa.lon) * KM_PER_DEG_LON_EQUATOR * cos_phi
    by = (pb.lat - pa.lat) * KM_PER_DEG_LAT
    length = math.hypot(bx, by)
    nx, ny = (0.0, 0.0) if length == 0 else (-by / length, bx / length)
    x = frac * bx + lateral_km * nx
    y = frac * by + lateral_km * ny
    return offset_local(pa, x, y, cos_phi)


class _Loader:
    def __init__(self, d: dict[str, Any]) -> None:
        self.d = d

    # ----------------------------------------------------------- helpers
    @staticmethod
    def _req(obj: dict[str, Any], key: str, path: str) -> Any:
        if key not in obj:
            raise ValueError(f"{path}.{key}: required")
        return obj[key]

    @staticmethod
    def _date(v: Any, path: str) -> date:
        try:
            return date.fromisoformat(str(v))
        except ValueError:
            raise ValueError(f"{path}: bad date {v!r}") from None

    @staticmethod
    def _decimal(v: Any, path: str) -> Decimal:
        try:
            return Decimal(str(v))
        except InvalidOperation:
            raise ValueError(f"{path}: bad decimal {v!r}") from None

    def _list(self, key: str) -> list[dict[str, Any]]:
        v = self.d.get(key, [])
        if not isinstance(v, list):
            raise ValueError(f"{key}: must be a list")
        return v

    # ----------------------------------------------------------- build
    def build(self) -> FakeWorld:
        d = self.d
        world_id = str(self._req(d, "id", "$"))
        as_of = self._date(self._req(d, "asOf", "$"), "asOf")
        regions = self._regions()
        nodes = self._nodes(regions)
        edges, adjacency = self._edges(nodes)
        towns_raw = self._list("towns")
        town_node: dict[str, str] = {}
        for i, t in enumerate(towns_raw):
            node = self._req(t, "node", f"towns[{i}]")
            if node not in nodes:
                raise ValueError(f"towns[{i}].node: unknown node {node!r}")
        places = self._places(nodes, edges, adjacency, {str(t.get("id")) for t in towns_raw}, regions)
        towns = self._towns(towns_raw, nodes, places, town_node, regions)
        prices = self._prices(regions)
        tolls = self._tolls(nodes, adjacency)
        ready = self._ready_routes(towns, places)
        defaults = d.get("defaults", {})
        food = [(int(a), int(b)) for a, b in defaults.get("foodCheckByPopulation", [[0, 600]])]
        lodging = [(int(a), int(b)) for a, b in defaults.get("lodgingNightByPopulation", [[0, 4000]])]
        return FakeWorld(
            id=world_id,
            as_of=as_of,
            regions=regions,
            nodes=nodes,
            edges=edges,
            towns=towns,
            town_node=town_node,
            places=places,
            region_prices=prices,
            tolls=tolls,
            ready_routes=ready,
            food_check_by_population=sorted(food, reverse=True),
            lodging_night_by_population=sorted(lodging, reverse=True),
            adjacency=adjacency,
        )

    def _regions(self) -> dict[str, RegionInfo]:
        out: dict[str, RegionInfo] = {}
        for i, r in enumerate(self._list("regions")):
            code = str(self._req(r, "code", f"regions[{i}]"))
            if code in out:
                raise ValueError(f"regions[{i}].code: duplicate id {code!r}")
            out[code] = RegionInfo(code, str(r.get("nameRu", code)), str(r.get("tz", "Europe/Moscow")))
        return out

    def _nodes(self, regions: dict[str, RegionInfo]) -> dict[str, Node]:
        out: dict[str, Node] = {}
        for i, n in enumerate(self._list("nodes")):
            nid = str(self._req(n, "id", f"nodes[{i}]"))
            if nid in out:
                raise ValueError(f"nodes[{i}].id: duplicate id {nid!r}")
            region = str(self._req(n, "region", f"nodes[{i}]"))
            if region not in regions:
                raise ValueError(f"nodes[{i}].region: unknown region {region!r}")
            out[nid] = Node(nid, LatLon(float(n["lat"]), float(n["lon"])), region)
        return out

    def _edges(self, nodes: dict[str, Node]) -> tuple[list[Edge], dict[str, list[tuple[Edge, str]]]]:
        edges: list[Edge] = []
        adjacency: dict[str, list[tuple[Edge, str]]] = {}
        seen: set[frozenset[str]] = set()
        for i, e in enumerate(self._list("edges")):
            path = f"edges[{i}]"
            a, b = str(self._req(e, "from", path)), str(self._req(e, "to", path))
            for end, name in ((a, "from"), (b, "to")):
                if end not in nodes:
                    raise ValueError(f"{path}.{name}: unknown node {end!r}")
            if a == b:
                raise ValueError(f"{path}.to: self-loop")
            key = frozenset((a, b))
            if key in seen:
                raise ValueError(f"{path}: duplicate edge {a}-{b}")
            seen.add(key)
            km = float(self._req(e, "km", path))
            straight = haversine_km(nodes[a].point, nodes[b].point)
            if km < EDGE_MIN_RATIO * straight:
                raise ValueError(f"{path}.km: {km} < 0.95 x straight line {straight:.1f} km")
            speed = float(self._req(e, "speedKmh", path))
            if speed <= 0:
                raise ValueError(f"{path}.speedKmh: must be positive")
            try:
                road_class = RoadClass(e.get("roadClass", "other"))
            except ValueError:
                raise ValueError(f"{path}.roadClass: unknown {e.get('roadClass')!r}") from None
            edge = Edge(
                index=i,
                a=a,
                b=b,
                pa=nodes[a].point,
                pb=nodes[b].point,
                km=km,
                speed_kmh=speed,
                road_class=road_class,
                ref=e.get("ref"),
                toll=bool(e.get("toll", False)),
            )
            edges.append(edge)
            adjacency.setdefault(a, []).append((edge, b))
            adjacency.setdefault(b, []).append((edge, a))
        for lst in adjacency.values():
            lst.sort(key=lambda eo: (eo[1], eo[0].index))
        return edges, adjacency

    def _anchor_point(
        self,
        anchor: dict[str, Any],
        path: str,
        nodes: dict[str, Node],
        adjacency: dict[str, list[tuple[Edge, str]]],
    ) -> tuple[LatLon, str]:
        if "node" in anchor:
            nid = str(anchor["node"])
            if nid not in nodes:
                raise ValueError(f"{path}.node: unknown node {nid!r}")
            n = nodes[nid]
            return offset_local(n.point, float(anchor.get("dxKm", 0)), float(anchor.get("dyKm", 0))), n.region
        if "edge" in anchor:
            pair = anchor["edge"]
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError(f"{path}.edge: must be [from, to]")
            a, b = str(pair[0]), str(pair[1])
            edge = next((e for e, other in adjacency.get(a, ()) if other == b), None)
            if edge is None:
                raise ValueError(f"{path}.edge: no edge {a}-{b}")
            km = float(self._req(anchor, "km", path))
            if not 0 <= km <= edge.km:
                raise ValueError(f"{path}.km: outside edge length {edge.km}")
            p = point_on_edge(nodes[a].point, nodes[b].point, km / edge.km, float(anchor.get("lateralKm", 0)))
            region = nodes[a].region if km <= edge.km / 2 else nodes[b].region
            return p, region
        raise ValueError(f"{path}: anchor needs node or edge")

    def _places(
        self,
        nodes: dict[str, Node],
        edges: list[Edge],
        adjacency: dict[str, list[tuple[Edge, str]]],
        town_ids: set[str],
        regions: dict[str, RegionInfo],
    ) -> dict[str, Place]:
        out: dict[str, Place] = {}
        for i, p in enumerate(self._list("places")):
            path = f"places[{i}]"
            pid = str(self._req(p, "id", path))
            if pid in out:
                raise ValueError(f"{path}.id: duplicate id {pid!r}")
            has_ll = "lat" in p or "lon" in p
            has_anchor = "anchor" in p
            if has_ll == has_anchor:
                raise ValueError(f"{path}: exactly one of lat/lon or anchor is required")
            if has_anchor:
                point, region = self._anchor_point(p["anchor"], f"{path}.anchor", nodes, adjacency)
            else:
                point = LatLon(float(p["lat"]), float(p["lon"]))
                region = min(nodes.values(), key=lambda n: (haversine_km(n.point, point), n.id)).region
            region = str(p.get("region", region))
            if region not in regions:
                raise ValueError(f"{path}.region: unknown region {region!r}")
            tags_raw = p.get("tags", [])
            tags_no_raw = p.get("tagsNo", [])  # ADR-0019 E-6: tags confirmed absent
            for key, raw in (("tags", tags_raw), ("tagsNo", tags_no_raw)):
                for j, t in enumerate(raw):
                    if t not in _TAG_VALUES:
                        raise ValueError(f"{path}.{key}[{j}]: unknown tag {t!r}")
            fuels: dict[str, frozenset[FuelType]] = {}
            for key in ("fuelKinds", "fuelKindsNo"):  # ADR-0019 E-4: absent = the station's fuels are unknown
                try:
                    fuels[key] = frozenset(FuelType(f) for f in p.get(key, []))
                except ValueError:
                    raise ValueError(f"{path}.{key}: unknown fuel in {p.get(key)!r}") from None
            rating = p.get("rating")
            breakfast = p.get("breakfastIncluded")
            try:
                ptype = PlaceType(self._req(p, "type", path))
            except ValueError:
                raise ValueError(f"{path}.type: unknown type {p.get('type')!r}") from None
            town_id = p.get("townId")
            if town_id is not None and town_id not in town_ids:
                raise ValueError(f"{path}.townId: unknown town {town_id!r}")
            source = Source(p.get("source", "curated"))
            verified = p.get("verifiedAt")
            partner = p.get("partner") or {}
            out[pid] = Place(
                id=pid,
                type=ptype,
                name_ru=str(self._req(p, "nameRu", path)),
                point=point,
                address=p.get("address"),
                region_code=region,
                town_id=town_id,
                opening_hours=p.get("openingHours"),
                dwell_min=p.get("dwellMin"),
                avg_check_rub=p.get("avgCheckRub"),
                price_night_rub=p.get("priceNightRub"),
                ticket_adult_rub=p.get("ticketAdultRub"),
                ticket_child_rub=p.get("ticketChildRub"),
                rating_internal=None if rating is None else float(rating),  # E-5: no rating, no 3.0
                tags=frozenset(Tag(t) for t in tags_raw),
                description_ru=p.get("descriptionRu"),
                partner_ids=PartnerIds(partner.get("yandexTravelId"), partner.get("tripsterId")),
                source=source,
                verified_at=None if verified is None else self._date(verified, f"{path}.verifiedAt"),
                status=PlaceStatus(p.get("status", "live")),
                breakfast_included=None if breakfast is None else bool(breakfast),  # E-3: unknown
                tags_no=frozenset(Tag(t) for t in tags_no_raw),
                fuel_kinds=fuels["fuelKinds"],
                fuel_kinds_no=fuels["fuelKindsNo"],
            )
        return out

    def _towns(
        self,
        raw: list[dict[str, Any]],
        nodes: dict[str, Node],
        places: dict[str, Place],
        town_node: dict[str, str],
        regions: dict[str, RegionInfo],
    ) -> dict[str, Town]:
        out: dict[str, Town] = {}
        lodging_count: dict[str, int] = {}
        for p in places.values():
            if p.type is PlaceType.LODGING and p.status is PlaceStatus.LIVE and p.town_id:
                lodging_count[p.town_id] = lodging_count.get(p.town_id, 0) + 1
        for i, t in enumerate(raw):
            path = f"towns[{i}]"
            tid = str(self._req(t, "id", path))
            if tid in out:
                raise ValueError(f"{path}.id: duplicate id {tid!r}")
            node = nodes[str(t["node"])]
            quality = int(t.get("quality", 0))
            if not 0 <= quality <= 3:
                raise ValueError(f"{path}.quality: must be 0..3")
            region = str(t.get("region", node.region))
            if region not in regions:
                raise ValueError(f"{path}.region: unknown region {region!r}")
            town_node[tid] = node.id
            out[tid] = Town(
                id=tid,
                name_ru=str(self._req(t, "nameRu", path)),
                name_prep_ru=t.get("namePrepRu"),
                name_gen_ru=t.get("nameGenRu"),
                point=node.point,
                region_code=region,
                population=int(t.get("population", 0)),
                quality=quality,
                evening_walk=bool(t.get("eveningWalk", False)),
                lodging_count_cache=lodging_count.get(tid, 0),
            )
        return out

    def _prices(self, regions: dict[str, RegionInfo]) -> list[RegionPrice]:
        out: list[RegionPrice] = []
        for i, r in enumerate(self._list("regionPrices")):
            path = f"regionPrices[{i}]"
            code = str(self._req(r, "region", path))
            if code != "RU" and code not in regions:
                raise ValueError(f"{path}.region: unknown region {code!r}")
            try:
                ft = FuelType(self._req(r, "fuelType", path))
            except ValueError:
                raise ValueError(f"{path}.fuelType: unknown {r.get('fuelType')!r}") from None
            out.append(
                RegionPrice(
                    code,
                    ft,
                    self._decimal(self._req(r, "priceRub", path), f"{path}.priceRub"),
                    self._date(self._req(r, "asOf", path), f"{path}.asOf"),
                )
            )
        for ft in FuelType:
            if not any(p.region_code == "RU" and p.fuel_type is ft for p in out):
                raise ValueError(f"regionPrices: missing RU row for {ft.value}")
        return out

    def _tolls(self, nodes: dict[str, Node], adjacency: dict[str, list[tuple[Edge, str]]]) -> list[TollDef]:
        out: list[TollDef] = []
        ids: set[str] = set()
        for i, s in enumerate(self._list("tollSegments")):
            path = f"tollSegments[{i}]"
            sid = str(self._req(s, "id", path))
            if sid in ids:
                raise ValueError(f"{path}.id: duplicate id {sid!r}")
            ids.add(sid)
            pair = self._req(s, "edge", path)
            a, b = str(pair[0]), str(pair[1])
            edge = next((e for e, other in adjacency.get(a, ()) if other == b), None)
            if edge is None:
                raise ValueError(f"{path}.edge: no edge {a}-{b}")
            from_km, to_km = float(s.get("fromKm", 0)), float(s.get("toKm", edge.km))
            if not 0 <= from_km < to_km <= edge.km:
                raise ValueError(f"{path}.toKm: range outside edge length {edge.km}")
            seg = TollSegment(
                id=sid,
                road_ref=str(self._req(s, "roadRef", path)),
                name_ru=str(s.get("nameRu", s["roadRef"])),
                tariff_day_rub=self._decimal(self._req(s, "tariffDayRub", path), f"{path}.tariffDayRub"),
                tariff_night_rub=self._decimal(
                    self._req(s, "tariffNightRub", path), f"{path}.tariffNightRub"
                ),
                vehicle_class=int(s.get("vehicleClass", 1)),
                night_from=time.fromisoformat(str(s.get("nightFrom", "00:00"))),
                night_to=time.fromisoformat(str(s.get("nightTo", "06:00"))),
                as_of=self._date(self._req(s, "asOf", path), f"{path}.asOf"),
            )
            out.append(TollDef(seg, edge, a, from_km, to_km))
        return out

    def _ready_routes(self, towns: dict[str, Town], places: dict[str, Place]) -> dict[str, ReadyRoute]:
        out: dict[str, ReadyRoute] = {}
        for i, r in enumerate(self._list("readyRoutes")):
            path = f"readyRoutes[{i}]"
            rid = str(self._req(r, "id", path))
            if rid in out:
                raise ValueError(f"{path}.id: duplicate id {rid!r}")
            hub = str(self._req(r, "hubTownId", path))
            if hub not in towns:
                raise ValueError(f"{path}.hubTownId: unknown town {hub!r}")
            points: list[ReadyRoutePoint] = []
            for j, pt in enumerate(self._req(r, "points", path)):
                ppath = f"{path}.points[{j}]"
                role = pt.get("role")
                if role == "via":
                    tid = pt.get("townId")
                    if tid not in towns:
                        raise ValueError(f"{ppath}.townId: unknown town {tid!r}")
                    points.append(ReadyRoutePoint(int(pt.get("seq", j + 1)), "via", str(tid), None))
                elif role == "stop":
                    pid = pt.get("placeId")
                    if pid not in places:
                        raise ValueError(f"{ppath}.placeId: unknown place {pid!r}")
                    points.append(ReadyRoutePoint(int(pt.get("seq", j + 1)), "stop", None, str(pid)))
                else:
                    raise ValueError(f"{ppath}.role: must be via or stop")
            nights = tuple(str(n) for n in r.get("suggestedNights", []))
            for j, n in enumerate(nights):
                if n not in towns:
                    raise ValueError(f"{path}.suggestedNights[{j}]: unknown town {n!r}")
            ring = r.get("ring", "weekend")
            if ring not in ("weekend", "long"):
                raise ValueError(f"{path}.ring: must be weekend or long")
            out[rid] = ReadyRoute(
                id=rid,
                hub_town_id=hub,
                title_ru=str(self._req(r, "titleRu", path)),
                subtitle_ru=str(r.get("subtitleRu", "")),
                points=tuple(sorted(points, key=lambda x: x.seq)),
                suggested_nights=nights,
                km_total=int(self._req(r, "kmTotal", path)),
                km_sign=int(self._req(r, "kmSign", path)),
                ring="weekend" if ring == "weekend" else "long",
                round_trip=bool(r.get("roundTrip", True)),
                days_min=int(r.get("daysMin", 1)),
                days_max=int(r.get("daysMax", 14)),
                tags=tuple(str(t) for t in r.get("tags", [])),
                cover_key=r.get("coverKey"),
                sort=int(r.get("sort", 100)),
                parent_id=r.get("parentId"),
            )
        for rid, rr in out.items():
            if rr.parent_id is not None and rr.parent_id not in out:
                raise ValueError(f"readyRoutes.{rid}.parentId: unknown ready route {rr.parent_id!r}")
        return out
