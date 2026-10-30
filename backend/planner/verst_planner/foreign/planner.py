"""`AbroadPlanner` (CEO 29.10): the planner of `world_v1`.

* A trip whose every point is in Russia goes to the Russian planner (`russia_v1`'s, or the server's) as it is,
  so it is byte for byte the trip it was before.
* A trip that leaves Russia is planned by the same pipeline over the whole world with
  - border crossings as `BORDER` stops (`BorderPort.crossings`; a buffer from `planner_config.json`, or no
    dwell at a border without a checkpoint);
  - Russian legs routed as before and legs abroad on the road model (`foreign.routing`, `approxDistances`);
  - stops abroad taken only on the legs of their own country (no sight across a border from the road);
  - the rouble cost without anything abroad that has no rouble price: nights and meals abroad are unknown,
    fuel abroad is in the fuel line only when the country has a sourced price and a Bank of Russia rate;
  - the `abroad` block: per country km, fuel and fees in the local currency (dated, sourced, «не
    проверено»), what is unknown, and `roubleTotalIncomplete`.
"""

from __future__ import annotations

import bisect
import dataclasses
import itertools
from collections.abc import Callable, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from verst_planner.config import PlannerConfig
from verst_planner.cost.model import CostInput, RegionKm, fuel_stop_cost
from verst_planner.cost.money import round_to
from verst_planner.domain.enums import FuelType, Meal, StopKind, WarningCode
from verst_planner.domain.facts import Fact as Known
from verst_planner.domain.model import (
    BorderPoint,
    CostPatch,
    LatLon,
    NormalizedInput,
    Place,
    PlannedStop,
    ReadyRoute,
    RegionPrice,
    ScheduledStop,
    Town,
    TripInput,
    TripPlan,
)
from verst_planner.engine import Planner
from verst_planner.events import NEVER, NULL_SINK, CancelToken, ProgressSink
from verst_planner.explain import ru
from verst_planner.explain.templates import ReasonTemplates
from verst_planner.foreign.rates import rate_or_none
from verst_planner.foreign.routing import VIA_MIN_POP, BorderRouting, BorderTolls, TownChain
from verst_planner.foreign.rules import RUSSIA, UNVERIFIED_RU, CountryRules, Fee, sources_json
from verst_planner.foreign.world import AbroadWorld
from verst_planner.geo.roadmodel import RoadModel
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.assemble import Sched
from verst_planner.pipeline.resolve import ResolvedPoints
from verst_planner.ports import (
    Clock,
    CorridorQuery,
    ParkingPort,
    PlaceRepository,
    RoutingPort,
)

CENT = Decimal("0.01")
LITRE = Decimal("0.1")


def _q(x: Decimal, step: Decimal = CENT) -> Decimal:
    return x.quantize(step, ROUND_HALF_UP)


class CountryPlaces:
    """The place repository of one trip abroad: only places and towns of the trip's countries."""

    def __init__(
        self, inner: PlaceRepository, allowed: frozenset[str], country_of: Callable[[str], str | None]
    ):
        self.inner = inner
        self.allowed = allowed
        self.country_of = country_of

    def _ok(self, region_code: str) -> bool:
        return self.country_of(region_code) in self.allowed

    def places_in_corridor(self, q: CorridorQuery) -> list[Place]:
        return [p for p in self.inner.places_in_corridor(q) if self._ok(p.region_code)]

    def towns_in_corridor(self, line: tuple[LatLon, ...], radius_km: float) -> list[Town]:
        return [t for t in self.inner.towns_in_corridor(line, radius_km) if self._ok(t.region_code)]

    def lodgings_of_towns(self, town_ids: Sequence[str]) -> dict[str, list[Place]]:
        return self.inner.lodgings_of_towns(town_ids)

    def get_places(self, ids: Sequence[str]) -> dict[str, Place]:
        return self.inner.get_places(ids)

    def get_towns(self, ids: Sequence[str]) -> dict[str, Town]:
        return self.inner.get_towns(ids)

    def get_ready_route(self, route_id: str) -> ReadyRoute | None:
        return self.inner.get_ready_route(route_id)

    def ready_routes_near(self, point: LatLon, hub_radius_km: float, limit: int) -> list[ReadyRoute]:
        return self.inner.ready_routes_near(point, hub_radius_km, limit)


def _points(raw: TripInput) -> list[LatLon]:
    out = [raw.origin.point, *(v.point for v in raw.vias)]
    if raw.destination is not None:
        out.append(raw.destination.point)
    return out


class AbroadPlanner(Planner):
    def __init__(
        self,
        *,
        russian: Planner,
        world: AbroadWorld,
        routing: RoutingPort,
        model: RoadModel,
        clock: Clock,
        config: PlannerConfig,
        templates: ReasonTemplates,
        parking: ParkingPort | None = None,
    ) -> None:
        aw = world
        chain = TownChain(
            t.point
            for t in aw.world.towns.values()
            if t.population >= VIA_MIN_POP and aw.country_of_region.get(t.region_code, RUSSIA) != RUSSIA
        )
        border_routing = BorderRouting(routing, model, lambda p: aw.locator.country_at(p) == RUSSIA, chain)
        super().__init__(
            routing=border_routing,
            places=aw.ports.places,
            prices=aw.ports.prices,
            tolls=BorderTolls(russian.ports.tolls, border_routing),
            regions=aw.ports.regions,
            geocoding=aw.ports.geocoding,
            clock=clock,
            config=config,
            templates=templates,
            parking=parking,
            borders=aw.borders,
        )
        self.russian = russian
        self.aw = aw
        aw.borders.now = lambda: self.clock.now()

    # ------------------------------------------------------------------ dispatch
    def inside_russia(self, points: Sequence[LatLon]) -> bool:
        return all(self.aw.locator.country_at(p) == RUSSIA for p in points)

    def plan(
        self,
        raw: TripInput,
        sink: ProgressSink = NULL_SINK,
        cancel: CancelToken = NEVER,
        split_km_hint: int | None = None,
    ) -> TripPlan:
        if self.inside_russia(_points(raw)):
            return self.russian.plan(raw, sink, cancel, split_km_hint)
        return super().plan(raw, sink, cancel, split_km_hint)

    def estimate_km(self, raw: TripInput, check_too_short: bool = True) -> int:
        if self.inside_russia(_points(raw)):
            return self.russian.estimate_km(raw, check_too_short)
        return super().estimate_km(raw, check_too_short)

    def replace_stop(self, plan: TripPlan, stop_id: str, alternative_id: str) -> TripPlan:
        if plan.abroad is None:
            return self.russian.replace_stop(plan, stop_id, alternative_id)
        return _with_note(super().replace_stop(plan, stop_id, alternative_id))

    def recompute_cost(self, plan: TripPlan, patch: CostPatch) -> TripPlan:
        if plan.abroad is None:
            return self.russian.recompute_cost(plan, patch)
        return _with_note(super().recompute_cost(plan, patch))

    # ------------------------------------------------------------------ hooks
    def _resolved(self, pts: ResolvedPoints, inp: NormalizedInput, ctx: PlanContext) -> None:
        wps = pts.waypoints
        legs: list[str] = []
        for a, b in itertools.pairwise(wps):
            if a.border is not None:
                legs.append(a.border.to_country)
            elif b.border is not None:
                legs.append(b.border.from_country)
            else:
                legs.append(
                    self.aw.locator.country_at(b.point) or self.aw.locator.country_at(a.point) or RUSSIA
                )
        order: list[str] = []
        for c in legs:
            if c not in order:
                order.append(c)
        ctx.ext["legs"] = legs
        ctx.ext["countries"] = order
        ctx.ext["borders"] = [w.border for w in wps if w.border is not None]
        ctx.ext["fuel"] = inp.vehicle.fuel_type
        ctx.ports = dataclasses.replace(
            ctx.ports, places=CountryPlaces(ctx.ports.places, frozenset(order), self.aw.country_of)
        )

    def _leg_country(self, ctx: PlanContext) -> Callable[[float], str]:
        wp_km: list[float] = ctx.ext["wp_km"]
        legs: list[str] = ctx.ext["legs"]

        def at(km: float) -> str:
            # a stop at a waypoint's km belongs to the leg before it (lunch in the town of the border)
            i = bisect.bisect_left(wp_km, km) - 1
            return legs[min(max(i, 0), len(legs) - 1)]

        return at

    def _corridor_built(self, corridor: Corridor, ctx: PlanContext) -> None:
        route = corridor.route
        ctx.ext["wp_km"] = [route.cum_km[i] for i in route.waypoint_idx]
        at = self._leg_country(ctx)
        country = self.aw.country_of
        for lst in (corridor.sights, corridor.food, corridor.fuel, corridor.rest, corridor.lodgings):
            lst[:] = [c for c in lst if country(c.place.region_code) == at(c.km_at)]
        corridor.towns[:] = [t for t in corridor.towns if country(t.town.region_code) == at(t.km_at)]
        for t in corridor.towns:
            t.lodgings[:] = [c for c in t.lodgings if country(c.place.region_code) == at(c.km_at)]

    def _abroad(self, region_code: str) -> str | None:
        """The country of a region when it is not Russia (None for Russia and unknown codes)."""
        c = self.aw.country_of(region_code)
        return c if c is not None and c != RUSSIA else None

    def _stop_abroad(self, km: float, region_code: str, ctx: PlanContext) -> str | None:
        """The country of a stop when it is not Russia: the country of its leg (after the border stop the
        trip is abroad, whatever the nearest town says), or of its region outside a planning run."""
        if "wp_km" in ctx.ext:
            c = self._leg_country(ctx)(km)
            return None if c == RUSSIA else c
        return self._abroad(region_code)

    def _fuel_rub(self, country: str, fuel: FuelType) -> RegionPrice | None:
        """The rouble price of a litre abroad: the sourced local price x the Bank of Russia rate, or None."""
        rules = self.aw.rules.countries.get(country)
        fp = rules.fuel.get(fuel) if rules is not None else None
        rate = rate_or_none(self.aw.rates, rules.currency) if rules is not None else None
        if fp is None or rate is None:
            return None
        return RegionPrice(country, fuel, _q(fp.budget * rate), fp.valid_from)

    def _stop_cost(self, s: PlannedStop, inp: NormalizedInput, ctx: PlanContext) -> int:
        country = self._stop_abroad(s.km_at, s.region_code, ctx)
        if country is None:
            return super()._stop_cost(s, inp, ctx)
        if s.kind is StopKind.FUEL and s.litres > 0:
            price = self._fuel_rub(country, inp.vehicle.fuel_type)
            return fuel_stop_cost(s.litres, price) if price is not None else 0
        if s.kind in (StopKind.FOOD, StopKind.OVERNIGHT):
            return 0  # no price abroad: the stop says so, the rouble total leaves it out
        return super()._stop_cost(s, inp, ctx)

    def _adjust_cost_input(self, ci: CostInput, days: Sequence[Sched], ctx: PlanContext) -> CostInput:
        fuel: FuelType = ctx.ext["fuel"]
        stop_of = {sid: s for d in days for sid, s in zip(d.ids, d.stops, strict=True)}

        def abroad(stop_id: str) -> str | None:
            st = stop_of.get(stop_id)
            return self._stop_abroad(st.km_at, st.region_code, ctx) if st is not None else None

        at = self._leg_country(ctx)
        regions: list[RegionKm] = []
        unpriced_km: dict[str, float] = {}
        for r in ci.regions:
            country = self._abroad(r.code)
            if country is None:
                regions.append(r)
                continue
            price = self._fuel_rub(country, fuel)
            if price is None:
                unpriced_km[country] = unpriced_km.get(country, 0.0) + r.km
                continue
            name = self.aw.rules.countries[country].name_ru
            regions.append(
                RegionKm(r.code, f"{name}: {r.name_ru}", r.km, dataclasses.replace(price, region_code=r.code))
            )
        nights = [n for n in ci.nights if abroad(n.stop_id) is None]
        night_countries = [c for n in ci.nights if (c := abroad(n.stop_id)) is not None]
        meals: dict[str, int] = {}
        for nc in night_countries:
            meals[nc] = meals.get(nc, 0) + 2  # the dinner in the town and the breakfast after the night
        day_inputs = []
        for d, di in zip(days, ci.days, strict=True):
            if di.lunch_overlap:
                ref = next((s.km_at for s in d.stops if s.meal is Meal.LUNCH), (d.km_start + d.km_end) / 2)
                c = at(ref)
                if c != RUSSIA:
                    di = dataclasses.replace(di, lunch_overlap=False)
                    meals[c] = meals.get(c, 0) + 1
            arrival = di.finish_arrival_local
            last = d.stops[-1]
            end = self._stop_abroad(last.km_at, last.region_code, ctx) if arrival is not None else None
            if arrival is not None and end is not None:  # a dinner at the finish abroad has no price
                di = dataclasses.replace(di, finish_arrival_local=None)
                if not di.finish_is_origin and arrival.time() > self.cfg.cost.dinner_last_day_after:
                    meals[end] = meals.get(end, 0) + 1
            day_inputs.append(di)
        parking = tuple(x for x in ci.parking if abroad(x.stop_id) is None)
        ctx.ext["unpriced"] = {
            "fuel_km": unpriced_km,
            "nights": {c: night_countries.count(c) for c in set(night_countries)},
            "meals": meals,
        }
        return dataclasses.replace(
            ci,
            regions=tuple(regions),
            nights=tuple(nights),
            days=tuple(day_inputs),
            parking=parking,
            trip_km=None if unpriced_km else ci.trip_km,
        )

    def _finished(self, plan: TripPlan, ctx: PlanContext) -> TripPlan:
        state_stops = {st.stop_id: st for d in plan.engine_state.days for st in d.stops}
        borders: list[BorderPoint] = list(ctx.ext.get("borders", []))
        km_by: dict[str, float] = {}
        for code, km in plan.engine_state.region_km:
            c = self.aw.country_of(code) or RUSSIA
            km_by[c] = km_by.get(c, 0.0) + km
        block = self._block(plan, ctx, km_by)
        days = []
        nights_abroad: set[int] = set()
        b = iter(borders)
        for d in plan.days_list:
            stops = []
            for s in d.stops:
                st = state_stops.get(s.id)
                if s.kind is StopKind.BORDER:
                    bp = next(b, None)
                    if bp is not None:
                        s = dataclasses.replace(s, border=self._border_json(bp, s, plan.days))
                elif (
                    s.kind in (StopKind.OVERNIGHT, StopKind.FOOD)
                    and st is not None
                    and self._stop_abroad(st.km_at, st.region_code, ctx) is not None
                ):
                    s = _price_unknown(s)
                    if s.kind is StopKind.OVERNIGHT and s.place_id is None:
                        s = dataclasses.replace(s, reason_ru=ru.text("abroad.night_no_hotel"))
                        nights_abroad.add(s.day)
                stops.append(s)
            days.append(dataclasses.replace(d, stops=tuple(stops)))
        warning = ctx.warning(WarningCode.ABROAD, None, "abroad")
        reasons = tuple(
            dataclasses.replace(r, text=ru.text("abroad.night_no_hotel")) if r.day in nights_abroad else r
            for r in plan.overnight_reasons
        )
        out = dataclasses.replace(
            plan,
            days_list=tuple(days),
            abroad=block,
            warnings=(*plan.warnings, warning),
            overnight_reasons=reasons,
        )
        return _with_note(out)

    # ------------------------------------------------------------------ the `abroad` block
    def _block(self, plan: TripPlan, ctx: PlanContext, km_by: dict[str, float]) -> dict[str, Any]:
        fuel_type: FuelType = plan.input.vehicle.fuel_type
        consumption = Decimal(str(plan.input.vehicle.consumption_l_per_100km))
        unpriced = ctx.ext.get("unpriced", {})
        rates = self.aw.rates
        used_rates: dict[str, str] = {}
        countries = []
        missing: list[str] = []
        local_totals: dict[str, Decimal] = {}
        for code in ctx.ext.get("countries", []):
            if code == RUSSIA:
                continue
            rules = self.aw.rules.countries[code]
            rate = rate_or_none(rates, rules.currency)
            if rate is not None and rules.currency != "RUB":
                used_rates[rules.currency] = str(rate)
            km = Decimal(str(round(km_by.get(code, 0.0), 1)))
            fuel = self._fuel_json(rules, fuel_type, km, consumption, rate)
            if fuel.get("amount") is not None:
                local_totals[rules.currency] = local_totals.get(rules.currency, Decimal(0)) + Decimal(
                    fuel["amount"]
                )
            if not fuel["inRoubleTotal"]:
                priced = fuel["pricePerLitre"] is not None
                key = "abroad.missing.fuel_rate" if priced else "abroad.missing.fuel"
                missing.append(ru.text(key, country=rules.name_ru, currency=rules.currency))
            fees = []
            for f in rules.fees:
                fj = self._fee_json(f, plan.days, rates)
                fees.append(fj)
                if fj["counted"]:
                    cur = str(fj["currency"])
                    local_totals[cur] = local_totals.get(cur, Decimal(0)) + Decimal(str(fj["amount"]))
                    if cur != "RUB" and (r := rate_or_none(rates, cur)) is not None:
                        used_rates[cur] = str(r)
            if any(f["mandatory"] for f in fees):
                missing.append(ru.text("abroad.missing.fees", country=rules.name_ru))
            if rules.tolls.status != "zero":
                missing.append(ru.text("abroad.missing.tolls", country=rules.name_ru))
            nights = int(unpriced.get("nights", {}).get(code, 0))
            meals = int(unpriced.get("meals", {}).get(code, 0))
            if nights:
                missing.append(ru.text("abroad.missing.nights", country=rules.name_ru, n=nights))
            if meals:
                missing.append(ru.text("abroad.missing.meals", country=rules.name_ru, n=meals))
            countries.append(
                {
                    "code": code,
                    "nameRu": rules.name_ru,
                    "currency": rules.currency,
                    "km": float(km),
                    "tz": sorted(
                        {ri.tz for c, ri in self.aw.world.regions.items() if self.aw.country_of(c) == code}
                    ),
                    "fuel": fuel,
                    "tolls": {
                        "status": rules.tolls.status,
                        "counted": rules.tolls.status == "zero",
                        "textRu": rules.tolls.text_ru,
                        "sources": sources_json(rules.tolls.sources),
                    },
                    "fees": fees,
                    "nightsUnpriced": nights,
                    "mealsUnpriced": meals,
                    "documents": [f.to_json() for f in rules.documents],
                    "rules": [f.to_json() for f in rules.rules],
                    "unverified": True,
                }
            )
        totals = []
        for cur in sorted(local_totals):
            amount = _q(local_totals[cur])
            r = rate_or_none(rates, cur)
            totals.append(
                {
                    "currency": cur,
                    "amount": str(amount),
                    "rub": round_to(amount * r, 10) if r is not None else None,
                }
            )
        note = ru.text("abroad.total_note")
        return {
            "unverified": True,
            "checkedAt": self.aw.rules.checked_at.isoformat(),
            "noteRu": UNVERIFIED_RU,
            "countries": countries,
            "localTotals": totals,
            "localTotalsRu": ru.text("abroad.local_totals"),
            "rates": (
                {"asOf": rates.as_of, "source": rates.source, "rubPerUnit": dict(sorted(used_rates.items()))}
                if rates is not None
                else None
            ),
            "ratesNoteRu": None if rates is not None else ru.text("abroad.no_rates"),
            "roubleTotalIncomplete": bool(missing),
            "notInRoubleTotalRu": missing,
            "totalNoteRu": note if missing else None,
        }

    def _fuel_json(
        self, rules: CountryRules, fuel: FuelType, km: Decimal, consumption: Decimal, rate: Decimal | None
    ) -> dict[str, Any]:
        fp = rules.fuel.get(fuel)
        litres = _q(km * consumption / 100, LITRE)
        base: dict[str, Any] = {
            "fuelType": fuel.value,
            "litres": float(litres),
            "currency": rules.currency,
            "sources": sources_json(rules.fuel_sources),
            "noteRu": rules.fuel_note_ru,
            "unverified": True,
        }
        if fp is None:
            return base | {
                "pricePerLitre": None,
                "priceRange": None,
                "validFrom": None,
                "amount": None,
                "rub": None,
                "inRoubleTotal": False,
                "noteRu": " ".join(x for x in (rules.fuel_note_ru, ru.text("abroad.fuel_unknown")) if x),
            }
        amount = _q(litres * fp.budget)
        note = " ".join(x for x in (rules.fuel_note_ru, fp.note_ru or "") if x)
        return base | {
            "pricePerLitre": str(fp.budget),
            "priceRange": [str(min(fp.values)), str(max(fp.values))],
            "validFrom": fp.valid_from.isoformat(),
            "amount": str(amount),
            "rub": round_to(amount * rate, 10) if rate is not None else None,
            "inRoubleTotal": rate is not None,
            "noteRu": note,
        }

    @staticmethod
    def _fee_json(f: Fee, days: int, rates: Any) -> dict[str, Any]:
        amount = f.amount_for(days) if f.counted else None
        counted = amount is not None
        why = None
        if not counted:
            if not f.mandatory:
                why = "not_mandatory"
            elif f.amount is None and not f.variants:
                why = "no_amount"
            elif f.conflict:
                why = "conflict"
            elif not any(s.type in ("official", "primary") for s in f.sources):
                why = "secondary_source"
            else:
                why = "no_period"
        out: dict[str, Any] = {
            "key": f.key,
            "textRu": f.text_ru,
            "mandatory": f.mandatory,
            "counted": counted,
            "notCountedWhy": why,
            "notCountedRu": ru.text(f"abroad.fee.{why}") if why else None,
            "currency": f.currency,
            "amount": str(amount[0]) if amount is not None else None,
            "periodDays": amount[1] if amount is not None else None,
            "rub": None,
            "inRoubleTotal": False,
            "sources": sources_json(f.sources),
            "ruleSources": sources_json(f.rule_sources),
            "unverified": True,
        }
        if amount is not None and f.currency is not None:
            r = rate_or_none(rates, f.currency)
            out["rub"] = round_to(amount[0] * r, 10) if r is not None else None
        return out

    def _border_json(self, bp: BorderPoint, s: ScheduledStop, days: int) -> dict[str, Any]:
        crossing = next(c for c in self.aw.rules.crossings if c.id == bp.id)
        to_rules = self.aw.rules.countries.get(bp.to_country)
        month = s.arrive_at.month if s.arrive_at is not None else None
        buffer = 0 if bp.marker else self.cfg.border.buffer_min

        def name(code: str) -> str:
            if code == RUSSIA:
                return ru.text("abroad.russia")
            r = self.aw.rules.countries.get(code)
            return r.name_ru if r is not None else code

        wait = crossing.wait
        return {
            "crossingId": bp.id,
            "nameRu": crossing.name_ru,
            "from": bp.from_country,
            "to": bp.to_country,
            "fromRu": name(bp.from_country),
            "toRu": name(bp.to_country),
            "marker": bp.marker,
            "coordsApprox": bp.coords_approx,
            "coordsNoteRu": bp.coords_note_ru,
            "waitKnown": wait is not None,
            "waitRu": wait.text_ru if wait is not None else ru.text("abroad.wait_unknown"),
            "waitSources": sources_json(wait.sources) if wait is not None else [],
            "bufferMin": buffer,
            "bufferRu": (
                ru.text("abroad.buffer", buffer=ru.duration_phrase(buffer))
                if buffer
                else ru.text("abroad.no_stop")
            ),
            "facts": [f.to_json() for f in crossing.facts],
            "risks": [f.to_json() | {"appliesOnTripDate": month in f.months} for f in crossing.risks],
            "documents": [f.to_json() for f in to_rules.documents] if to_rules is not None else [],
            "fees": [self._fee_json(f, days, self.aw.rates) for f in to_rules.fees]
            if to_rules is not None
            else [],
            "rules": [f.to_json() for f in to_rules.rules] if to_rules is not None else [],
            "unverified": True,
            "checkedAt": self.aw.rules.checked_at.isoformat(),
            "noteRu": UNVERIFIED_RU,
        }


def _price_unknown(s: ScheduledStop) -> ScheduledStop:
    facts = s.unknown_facts if Known.PRICE.value in s.unknown_facts else (*s.unknown_facts, Known.PRICE.value)
    line = ru.text("unknown.price_abroad")
    return dataclasses.replace(
        s,
        unknown_facts=facts,
        unknown_ru=line if s.unknown_ru is None or line in s.unknown_ru else f"{s.unknown_ru}. {line}",
    )


def _with_note(plan: TripPlan) -> TripPlan:
    """The cost's «what the total leaves out» with the trip's part abroad (kept after a cost patch)."""
    extra = (plan.abroad or {}).get("totalNoteRu")
    note = plan.cost.total_note_ru
    if not extra or (note and extra in note):
        return plan
    joined = f"{note.rstrip('.')}. {extra}" if note else extra
    return dataclasses.replace(plan, cost=dataclasses.replace(plan.cost, total_note_ru=joined))


__all__ = ["AbroadPlanner", "CountryPlaces"]
