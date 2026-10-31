"""`FakeRouting`: Dijkstra over the world graph (A§5.2).

Undirected graph; edge cost = minutes (`km / speedKmh x 60`), x100 for toll edges with `avoid_tolls`.
Snapping: a request point snaps to the nearest graph node when that node is no farther than the nearest edge
point + 0.5 km, else to the nearest point on an edge (virtual split); only nodes with edges count. A snap
distance above `snap_max_km` (2 km) raises `Unreachable(point_index, snap_km)`. The polyline interpolates
each traversed edge every ~1 km; `cum_km`/`cum_min` are scaled so each edge contributes exactly its `km` and
minutes. One `RouteDetail` per edge, merged when class/ref/toll are equal.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from verst_planner.adapters.fake.world import Edge, FakeWorld, point_on_edge
from verst_planner.domain.enums import RoadClass
from verst_planner.domain.errors import PlannerError, Unreachable
from verst_planner.domain.model import LatLon, Route, RouteDetail, RouteRequest
from verst_planner.geo.distance import haversine_km, project_on_segment

TOLL_AVOID_FACTOR = 100.0
NODE_PREFERENCE_KM = 0.5


@dataclass(frozen=True, slots=True)
class _Snap:
    node: str | None  # graph node id when snapped to a node
    edge: Edge | None  # edge when snapped onto an edge (virtual split)
    frac: float  # fraction along edge.a → edge.b
    point: LatLon
    dist_km: float


@dataclass(frozen=True, slots=True)
class _Hop:
    """A directed traversal of (part of) an edge."""

    edge: Edge
    pa: LatLon
    pb: LatLon
    km: float
    minutes: float


class FakeRouting:
    def __init__(
        self, world: FakeWorld, fail_with: PlannerError | None = None, snap_max_km: float = 2.0
    ) -> None:
        self.world = world
        self.fail_with = fail_with
        self.snap_max_km = snap_max_km
        self.calls = 0
        self._graph_nodes = sorted(n for n in world.nodes if world.adjacency.get(n))

    # ------------------------------------------------------------------ snapping
    def _snap(self, p: LatLon, idx: int) -> _Snap:
        w = self.world
        best_node, best_nd = None, math.inf
        for nid in self._graph_nodes:
            d = haversine_km(p, w.nodes[nid].point)
            if d < best_nd:
                best_node, best_nd = nid, d
        best_edge, best_t, best_ed = None, 0.0, math.inf
        for e in w.edges:
            t, d = project_on_segment(p, e.pa, e.pb)
            if d < best_ed:
                best_edge, best_t, best_ed = e, t, d
        if best_node is not None and best_nd <= best_ed + NODE_PREFERENCE_KM:
            snap = _Snap(best_node, None, 0.0, w.nodes[best_node].point, best_nd)
        elif best_edge is not None:
            if best_t <= 0.0 or best_t >= 1.0:
                nid = best_edge.a if best_t <= 0.0 else best_edge.b
                snap = _Snap(nid, None, 0.0, w.nodes[nid].point, haversine_km(p, w.nodes[nid].point))
            else:
                snap = _Snap(
                    None, best_edge, best_t, point_on_edge(best_edge.pa, best_edge.pb, best_t), best_ed
                )
        else:
            raise Unreachable(idx, None)
        if snap.dist_km > self.snap_max_km:
            raise Unreachable(idx, round(snap.dist_km, 3))
        return snap

    # ------------------------------------------------------------------ search
    def _neighbours(self, node: str, virtual: dict[str, list[tuple[_Hop, str]]]) -> list[tuple[_Hop, str]]:
        out: list[tuple[_Hop, str]] = []
        if not node.startswith("~"):
            for e, other in self.world.adjacency.get(node, ()):
                if e.a == node:
                    out.append((_Hop(e, e.pa, e.pb, e.km, e.minutes), other))
                else:
                    out.append((_Hop(e, e.pb, e.pa, e.km, e.minutes), other))
        out.extend(virtual.get(node, ()))
        return out

    def _dijkstra(
        self, src: str, dst: str, virtual: dict[str, list[tuple[_Hop, str]]], avoid_tolls: bool
    ) -> list[_Hop] | None:
        if src == dst:
            return []
        dist: dict[str, float] = {src: 0.0}
        prev: dict[str, tuple[str, _Hop]] = {}
        heap: list[tuple[float, str]] = [(0.0, src)]
        done: set[str] = set()
        while heap:
            d, u = heapq.heappop(heap)
            if u in done:
                continue
            done.add(u)
            if u == dst:
                break
            for hop, v in self._neighbours(u, virtual):
                cost = hop.minutes * (TOLL_AVOID_FACTOR if avoid_tolls and hop.edge.toll else 1.0)
                nd = d + cost
                if nd < dist.get(v, math.inf) - 1e-12:
                    dist[v] = nd
                    prev[v] = (u, hop)
                    heapq.heappush(heap, (nd, v))
        if dst not in done:
            return None
        hops: list[_Hop] = []
        cur = dst
        while cur != src:
            u, hop = prev[cur]
            hops.append(hop)
            cur = u
        hops.reverse()
        return hops

    # ------------------------------------------------------------------ public
    def route(self, req: RouteRequest) -> Route:
        self.calls += 1
        if self.fail_with is not None:
            raise self.fail_with
        if len(req.points) < 2:
            raise Unreachable(0, None)
        snaps = [self._snap(p, i) for i, p in enumerate(req.points)]
        ids: list[str] = []
        virtual: dict[str, list[tuple[_Hop, str]]] = {}
        on_edge: dict[int, list[tuple[str, float, LatLon]]] = {}
        for i, s in enumerate(snaps):
            if s.node is not None:
                ids.append(s.node)
                continue
            assert s.edge is not None
            vid = f"~v{i}"
            ids.append(vid)
            e = s.edge
            km_a, km_b = s.frac * e.km, (1 - s.frac) * e.km
            to_a = _Hop(e, s.point, e.pa, km_a, km_a / e.speed_kmh * 60)
            to_b = _Hop(e, s.point, e.pb, km_b, km_b / e.speed_kmh * 60)
            virtual.setdefault(vid, []).extend([(to_a, e.a), (to_b, e.b)])
            virtual.setdefault(e.a, []).append((_Hop(e, e.pa, s.point, km_a, to_a.minutes), vid))
            virtual.setdefault(e.b, []).append((_Hop(e, e.pb, s.point, km_b, to_b.minutes), vid))
            for other_id, other_frac, other_pt in on_edge.get(e.index, []):
                km = abs(s.frac - other_frac) * e.km
                minutes = km / e.speed_kmh * 60
                virtual[vid].append((_Hop(e, s.point, other_pt, km, minutes), other_id))
                virtual.setdefault(other_id, []).append((_Hop(e, other_pt, s.point, km, minutes), vid))
            on_edge.setdefault(e.index, []).append((vid, s.frac, s.point))

        points: list[LatLon] = [snaps[0].point]
        cum_km: list[float] = [0.0]
        cum_min: list[float] = [0.0]
        spans: list[tuple[int, int, Edge]] = []
        waypoint_idx = [0]
        for i in range(len(snaps) - 1):
            hops = self._dijkstra(ids[i], ids[i + 1], virtual, req.avoid_tolls)
            if hops is None:
                raise Unreachable(i + 1, None)
            for hop in hops:
                if hop.km <= 0:
                    continue
                n = max(1, round(hop.km))
                start = len(points) - 1
                for k in range(1, n + 1):
                    f = k / n
                    points.append(
                        hop.pb
                        if k == n
                        else LatLon(
                            hop.pa.lat + (hop.pb.lat - hop.pa.lat) * f,
                            hop.pa.lon + (hop.pb.lon - hop.pa.lon) * f,
                        )
                    )
                    cum_km.append(cum_km[start] + hop.km * f)
                    cum_min.append(cum_min[start] + hop.minutes * f)
                spans.append((start, len(points) - 1, hop.edge))
            waypoint_idx.append(len(points) - 1)

        details: list[RouteDetail] = []
        for lo, hi, e in spans:
            if details and (details[-1].road_class, details[-1].road_ref, details[-1].toll) == (
                e.road_class,
                e.ref,
                e.toll,
            ):
                last = details[-1]
                details[-1] = RouteDetail(last.from_idx, hi, last.road_class, last.road_ref, last.toll)
            else:
                details.append(RouteDetail(lo, hi, e.road_class, e.ref, e.toll))
        if not details:  # all requested points snapped to the same spot
            details.append(RouteDetail(0, len(points) - 1, RoadClass.OTHER, None, False))
        return Route(
            points=tuple(points),
            cum_km=tuple(cum_km),
            cum_min=tuple(cum_min),
            details=tuple(details),
            waypoint_idx=tuple(waypoint_idx),
            snapped=tuple(s.point for s in snaps),
            km_total=cum_km[-1],
            min_total=cum_min[-1],
        )
