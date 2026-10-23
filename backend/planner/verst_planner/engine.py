"""`Planner` facade (A§6.1): stages 0-13, progress events (A§8.3), cancellation, replace and cost patches."""

from __future__ import annotations

import dataclasses
import statistics
from collections.abc import Sequence
from datetime import datetime, timedelta

from verst_planner import ENGINE_VERSION
from verst_planner.config import PlannerConfig
from verst_planner.cost.model import (
    CostInput,
    DayInput,
    NightInput,
    RegionKm,
    SightInput,
    TollInput,
    compute_cost,
    food_cost,
    fuel_stop_cost,
    overnight_cost,
    sight_cost,
    ticket_prices,
)
from verst_planner.cost.recompute import recompute
from verst_planner.domain.enums import (
    Meal,
    PlaceType,
    SignType,
    Source,
    StageKey,
    StopKind,
    Tag,
    WarningCode,
)
from verst_planner.domain.errors import NotFound
from verst_planner.domain.model import (
    UNSET,
    AltUnits,
    Candidate,
    CostPatch,
    CostResult,
    CostUnits,
    Crew,
    DayPlan,
    DayResult,
    DayState,
    EngineState,
    FuelRegionUnit,
    FuelUnits,
    HotelOption,
    MealUnit,
    NightUnit,
    NormalizedInput,
    OvernightChoice,
    OvernightReason,
    Place,
    PlannedStop,
    PlanWarning,
    ScheduledStop,
    StopState,
    TicketUnit,
    TollHit,
    Town,
    TownCandidate,
    TripInput,
    TripPlan,
)
from verst_planner.events import NEVER, NULL_SINK, CancelToken, ProgressSink, StageEvent, StopEvent
from verst_planner.explain import ru
from verst_planner.explain.reasons import overnight_reason
from verst_planner.explain.templates import ReasonTemplates
from verst_planner.pipeline import Corridor, PlanContext, Ports, round_half_up
from verst_planner.pipeline import fuel as fuel_stage
from verst_planner.pipeline.alternatives import (
    Pools,
    alternatives_for_day,
    build_alternatives,
    family,
)
from verst_planner.pipeline.assemble import (
    Sched,
    StopView,
    engine_state,
    hotel_option,
    km_from_prev_row,
    region_km,
    render_day,
    stop_state,
    title,
)
from verst_planner.pipeline.base_route import build_base_route, toll_warnings
from verst_planner.pipeline.corridor import build_corridor, place_fixed
from verst_planner.pipeline.day_split import split_days
from verst_planner.pipeline.meals import covers_lunch_window, plan_meals
from verst_planner.pipeline.overnight import choose_overnights
from verst_planner.pipeline.resolve import normalize_input, resolve_points
from verst_planner.pipeline.rest import plan_rests
from verst_planner.pipeline.schedule import ScheduledDay, assign_ids, schedule_with_rerun
from verst_planner.pipeline.sights import plan_sights
from verst_planner.pipeline.timeline import (
    Profile,
    build_day_plans,
    day_duration_min,
    insert_index,
    local,
    local_minute,
    schedule_day,
)
from verst_planner.ports import (
    Clock,
    GeocodingPort,
    PlaceRepository,
    PriceRepository,
    RegionLocator,
    RoutingPort,
    TollRepository,
)


class Planner:
    def __init__(
        self,
        *,
        routing: RoutingPort,
        places: PlaceRepository,
        prices: PriceRepository,
        tolls: TollRepository,
        regions: RegionLocator,
        geocoding: GeocodingPort,
        clock: Clock,
        config: PlannerConfig,
        templates: ReasonTemplates,
    ) -> None:
        self.ports = Ports(routing, places, prices, tolls, regions, geocoding)
        self.clock = clock
        self.cfg = config
        self.templates = templates

    # ------------------------------------------------------------------------------------------ context
    def _ctx(self) -> PlanContext:
        ctx = PlanContext(self.cfg, self.templates, self.ports, self.clock)
        ctx.stop_cost = lambda s, inp: self._stop_cost(s, inp, ctx)
        return ctx

    def _stop_cost(self, s: PlannedStop, inp: NormalizedInput, ctx: PlanContext) -> int:
        """Per-stop `cost_rub` (A§7.1): tickets, a meal for the crew, the room(s), informational fuel."""
        crew = inp.crew
        if s.kind is StopKind.SIGHT and s.place is not None:
            return sight_cost(s.place, crew)
        if s.kind is StopKind.FOOD and s.place is not None:
            check = s.place.avg_check_rub or self.ports.prices.food_default_check(0)
            return food_cost(check, crew, self.cfg)
        if s.kind is StopKind.OVERNIGHT:
            if s.place is not None and s.place.price_night_rub is not None:
                return overnight_cost(s.place.price_night_rub, crew)
            pop = s.town.population if s.town is not None else 0
            return overnight_cost(self.ports.prices.lodging_default_night(pop), crew)
        if s.kind is StopKind.FUEL and s.litres > 0:
            return fuel_stop_cost(
                s.litres, self.ports.prices.fuel_price(s.region_code, inp.vehicle.fuel_type)
            )
        return 0

    # ------------------------------------------------------------------------------------------ plan
    def plan(self, raw: TripInput, sink: ProgressSink = NULL_SINK, cancel: CancelToken = NEVER) -> TripPlan:
        ctx = self._ctx()
        t = self.templates
        inp = normalize_input(raw, ctx)
        pts = resolve_points(inp, ctx)
        cancel.check()  # before stage 2
        sink.emit(StageEvent(StageKey.SPLIT, t.render("stage.route"), 0.05))
        route = build_base_route(pts, inp, ctx)
        warnings: list[PlanWarning] = list(toll_warnings(route, inp, ctx))
        cancel.check()  # before stage 3
        corridor = build_corridor(route, inp, ctx)
        split = split_days(route, corridor, inp, pts.template, ctx)
        ring = pts.template is not None and inp.round_trip
        sink.emit(
            StageEvent(
                StageKey.SPLIT,
                t.render(
                    "stage.split_ring" if ring else "stage.split",
                    n=split.n_days,
                    days_word=ru.days_word(split.n_days),
                    km=round_half_up(route.km_total / split.n_days),
                ),
                0.25,
            )
        )
        if split.n_days > 1:
            sink.emit(StageEvent(StageKey.LODGING, t.render(self._lodging_stage_key(inp)), 0.30))
        cancel.check()  # before stage 5
        profile = ctx.profile_for(route)
        nights = choose_overnights(split, corridor, inp, ctx, profile)
        warnings += nights.warnings
        for c in nights.choices:
            sign = SignType.HOTEL if c.hotel is not None else SignType.CITY
            sink.emit(
                StopEvent(
                    c.day, f"night{c.day}", StopKind.OVERNIGHT, sign, c.name_ru, round_half_up(c.km_at), True
                )
            )
        days = build_day_plans(
            route, nights.choices, place_fixed(pts, corridor, inp, ctx), inp, ctx, pts, profile
        )
        sink.emit(
            StageEvent(
                StageKey.FUEL,
                t.render(
                    "stage.fuel", consumption=ru.fmt_consumption_setting(inp.vehicle.consumption_l_per_100km)
                ),
                0.50,
            )
        )
        cancel.check()  # before stage 6
        ctx.fuel_warnings = fuel_stage.plan_fuel(days, corridor, inp, ctx)
        plan_rests(days, corridor, inp, ctx)
        plan_meals(days, corridor, inp, ctx)
        sink.emit(StageEvent(StageKey.HOURS, t.render("stage.hours"), 0.65))
        cancel.check()  # before stage 9
        plan_sights(days, corridor, inp, ctx)
        cancel.check()  # before stage 10
        sched, sched_warnings = schedule_with_rerun(days, corridor, inp, ctx)
        assign_ids(sched)
        build_alternatives(sched, corridor, inp, ctx)
        sink.emit(StageEvent(StageKey.COST, t.render("stage.cost"), 0.90))
        cancel.check()  # before stage 12
        toll_hits = self.ports.tolls.segments_on_route(route)
        all_stops = [s for sd in sched for s in sd.plan.stops]
        region_kms = region_km(route, all_stops, ctx)
        views = [_sched_view(sd) for sd in sched]
        cost = compute_cost(
            _cost_input(views, nights.choices, corridor, region_kms, toll_hits, inp, ctx, profile),
            inp,
            self.cfg,
        )
        cost = self._with_hints(cost)
        plan = self._assemble(
            inp,
            pts.labels,
            pts.template.title_ru if pts.template else None,
            sched,
            nights.choices,
            corridor,
            cost,
            warnings + ctx.fuel_warnings + sched_warnings,
            ctx,
            engine_state(profile, region_kms, toll_hits, views, corridor, ctx),
        )
        for d in plan.days_list:
            for s in d.stops:
                sink.emit(StopEvent(d.day, s.id, s.kind, s.sign, s.name_ru, s.km_at, False))
        return plan

    @staticmethod
    def _lodging_stage_key(inp: NormalizedInput) -> str:
        if inp.crew.dog:
            return "stage.lodging.dog"
        if inp.crew.children > 0:
            return "stage.lodging.family"
        return "stage.lodging.default"

    def _with_hints(self, cost: CostResult) -> CostResult:
        return dataclasses.replace(
            cost, hints_ru=tuple(self.templates.render(f"hint.{k}") for k in cost.hint_keys)
        )

    def _assemble(
        self,
        inp: NormalizedInput,
        labels: tuple[str, ...],
        template_title: str | None,
        sched: list[ScheduledDay],
        choices: list[OvernightChoice],
        corridor: Corridor,
        cost: CostResult,
        warnings: list[PlanWarning],
        ctx: PlanContext,
        state: EngineState,
    ) -> TripPlan:
        reasons: list[OvernightReason] = []
        days: list[DayResult] = []
        for sd in sched:
            views: dict[int, StopView] = {i: StopView(alternatives=a) for i, a in sd.alternatives.items()}
            if sd.plan.stops[-1].kind is StopKind.OVERNIGHT:
                c = choices[sd.plan.day - 1]
                day_km = round_half_up(
                    sd.plan.km_end - sd.plan.km_start + sum(s.detour_km for s in sd.plan.stops)
                )
                text = overnight_reason(c, day_km, inp, self.cfg, self.templates, template_title)
                note = None
                if c.nearest is not None:
                    note = ru.text(
                        "note.nearest",
                        name=c.nearest.place.name_ru,
                        town=c.nearest_town.name_ru if c.nearest_town else c.nearest.place.name_ru,
                        dkm=round_half_up(abs(c.nearest.km_at - c.km_at)),
                    )
                views[len(sd.plan.stops) - 1] = StopView(
                    overnight_text=text.text,
                    note=note,
                    hotel_options=tuple(hotel_option(h.place, inp) for h in c.hotel_options),
                )
                reasons.append(
                    OvernightReason(
                        c.day,
                        c.town.id if c.town else None,
                        c.name_ru,
                        text.text,
                        text.candidates,
                        c.fallback,
                    )
                )
            days.append(
                render_day(
                    sd.plan.stops,
                    sd.slots,
                    sd.plan.day,
                    sd.plan.km_start,
                    sd.plan.km_end,
                    sd.plan.start_at,
                    sd.plan.tz,
                    sd.over_budget,
                    sd.seq0,
                    inp,
                    ctx,
                    views,
                    sd.ids,
                )
            )
        if any(s.place is not None and s.place.source is Source.OSM for sd in sched for s in sd.plan.stops):
            warnings = [*warnings, ctx.warning(WarningCode.UNVERIFIED_PLACES, None, "osm_places")]
        return TripPlan(
            title_ru=title(labels, inp, template_title),
            km=sum(d.km for d in days),
            days=len(days),
            nights=len(days) - 1,
            round_trip=inp.round_trip,
            days_list=tuple(days),
            cost=cost,
            overnight_reasons=tuple(reasons),
            warnings=tuple(warnings),
            input=inp,
            engine_version=ENGINE_VERSION,
            engine_state=state,
        )

    # ------------------------------------------------------------------------------------------ replace
    def replace_stop(self, plan: TripPlan, stop_id: str, alternative_id: str) -> TripPlan:
        """Swap in an alternative and re-schedule only that day from `EngineState` (no routing call)."""
        found = next(
            (
                (di, si)
                for di, d in enumerate(plan.days_list)
                for si, s in enumerate(d.stops)
                if s.id == stop_id
            ),
            None,
        )
        if found is None:
            raise NotFound("stop", stop_id)
        di, si = found
        old_day = plan.days_list[di]
        old_rendered = old_day.stops[si]
        alt = next((a for a in old_rendered.alternatives if a.id == alternative_id), None)
        if alt is None:
            raise NotFound("alternative", alternative_id)
        ctx = self._ctx()
        inp = plan.input
        state = plan.engine_state
        ds = state.days[di]
        profile = Profile(state.profile_km, state.profile_min, state.drive_time_factor)
        place_ids = {st.place_id for st in ds.stops if st.place_id} | {c.place_id for c in state.candidates}
        places = self.ports.places.get_places(sorted(place_ids))
        towns = self.ports.places.get_towns(sorted({t for t, _k in state.town_kms}))
        town_cands = [TownCandidate(towns[t], km, 0.0, 0, []) for t, km in state.town_kms if t in towns]
        stops = [_planned_from_state(st, r, places) for st, r in zip(ds.stops, old_day.stops, strict=True)]
        old_planned = stops[si]
        cand = _candidate_for(alt.place_id, alt.stop.km_at, state, places)
        new = dataclasses.replace(
            old_planned,
            km_at=cand.km_at,
            name_ru=cand.place.name_ru,
            point=cand.place.point,
            place=cand.place,
            detour_km=cand.detour_km,
            detour_min=cand.detour_min,
            dwell_min=alt.stop.dwell_min,
            region_code=cand.region_code,
            score=0.0,
            reason_params=dict(old_planned.reason_params),
        )
        if new.kind is StopKind.FUEL:
            new.litres = max(
                0.0,
                old_planned.litres
                + (cand.km_at - old_planned.km_at + cand.detour_km - old_planned.detour_km)
                * inp.vehicle.consumption_l_per_100km
                / 100,
            )
        rest = [s for k, s in enumerate(stops) if k != si]
        ids = [r.id for k, r in enumerate(old_day.stops) if k != si]
        day = DayPlan(ds.day, ds.km_start, ds.km_end, ds.start_at, rest, ds.tz)
        j = insert_index(day, new)
        rest.insert(j, new)
        ids.insert(j, stop_id)
        slots = schedule_day(day, profile)
        rendered_by_id = {r.id: r for r in old_day.stops}
        rendered_by_id[stop_id] = alt.stop
        seq0 = old_day.stops[0].seq
        row = km_from_prev_row(rest)
        new_stops: list[ScheduledStop] = []
        for k, (s, slot, sid) in enumerate(zip(rest, slots, ids, strict=True)):
            base = rendered_by_id[sid]
            tz = base.tz
            new_stops.append(
                dataclasses.replace(
                    base,
                    id=sid,
                    seq=seq0 + k,
                    day=ds.day,
                    arrive_at=_lm(slot.arrive, tz),
                    depart_at=_lm(slot.depart, tz),
                    km_from_prev=row[k],
                    km_at=round_half_up(s.km_at),
                    alternatives=(),
                )
            )
        # alternatives of that day, from the persisted candidate pools
        sd = ScheduledDay(day, slots, ds.budget_min, ids=ids, seq0=seq0)
        used = {r.place_id for d in plan.days_list for r in d.stops if r.place_id} - {old_rendered.place_id}
        used.add(alt.place_id)
        pools = _pools(state, places)
        fills = _fills_after_replace(plan, stop_id, cand.km_at)
        alts = alternatives_for_day(
            sd, pools, {u for u in used if u}, inp, ctx, profile, fills, state.profile_km[-1], town_cands
        )
        new_stops = [
            dataclasses.replace(s, alternatives=alts.get(k, ())) if family(rest[k]) else s
            for k, s in enumerate(new_stops)
        ]
        duration = day_duration_min(day, slots)
        over = duration > ds.budget_min + 1e-6
        new_day = DayResult(
            day=ds.day,
            km=round_half_up(ds.km_end - ds.km_start + sum(s.detour_km for s in rest)),
            drive_min=round_half_up(sum(x.drive_min for x in slots)),
            tz=old_day.tz,
            start_at=old_day.start_at,
            end_at=_lm(slots[-1].arrive, old_day.tz) or old_day.end_at,
            stops=tuple(new_stops),
            over_budget=over,
        )
        days_list = tuple(new_day if k == di else d for k, d in enumerate(plan.days_list))
        warnings = [
            w for w in plan.warnings if not (w.code is WarningCode.DAY_OVER_BUDGET and w.day == ds.day)
        ]
        if over:
            warnings.append(
                ctx.warning(
                    WarningCode.DAY_OVER_BUDGET, ds.day, f"minutes={round_half_up(duration)}", day=ds.day
                )
            )
        units = self._units_after_replace(plan.cost.units, stop_id, alt.units, new, inp, ctx)
        cost = self._with_hints(recompute(units, inp.crew, inp.reserve_on, inp.budget_rub))
        region_kms = tuple((r.region_code, r.km) for r in units.fuel.regions)
        new_state = dataclasses.replace(
            state,
            region_km=region_kms,
            days=tuple(
                DayState(
                    ds.day,
                    ds.km_start,
                    ds.km_end,
                    ds.start_at,
                    ds.tz,
                    ds.budget_min,
                    tuple(stop_state(s, sid) for s, sid in zip(rest, ids, strict=True)),
                )
                if k == di
                else x
                for k, x in enumerate(state.days)
            ),
        )
        return dataclasses.replace(
            plan,
            days_list=days_list,
            km=sum(d.km for d in days_list),
            cost=cost,
            warnings=tuple(warnings),
            engine_state=new_state,
        )

    def _units_after_replace(
        self,
        u: CostUnits,
        stop_id: str,
        alt_units: AltUnits,
        new: PlannedStop,
        inp: NormalizedInput,
        ctx: PlanContext,
    ) -> CostUnits:
        regions = list(u.fuel.regions)
        codes = [r.region_code for r in regions]
        if alt_units.region_code in codes:
            k = codes.index(alt_units.region_code)
            r = regions[k]
            regions[k] = FuelRegionUnit(
                r.region_code, r.region_name_ru, round(r.km + alt_units.delta_km, 3), r.price_rub
            )
        elif regions:
            r = regions[0]
            regions[0] = FuelRegionUnit(
                r.region_code, r.region_name_ru, round(r.km + alt_units.delta_km, 3), r.price_rub
            )
        meals = tuple(
            MealUnit(m.day, m.meal, m.stop_id, alt_units.check_rub)
            if m.stop_id == stop_id and alt_units.check_rub is not None
            else m
            for m in u.meals
        )
        tickets = [x for x in u.tickets if x.stop_id != stop_id]
        if new.kind is StopKind.SIGHT and new.place is not None:
            adult, child = ticket_prices(new.place)
            tickets.append(TicketUnit(stop_id, new.place.id, new.place.name_ru, adult, child))
        fuel = FuelUnits(u.fuel.consumption_l_per_100km, u.fuel.fuel_type, tuple(regions), u.fuel.as_of)
        return dataclasses.replace(u, fuel=fuel, meals=meals, tickets=tuple(tickets))

    # ------------------------------------------------------------------------------------------ cost patch
    def recompute_cost(self, plan: TripPlan, patch: CostPatch) -> TripPlan:
        """PATCH /v1/trips/{id}: crew, budget, reserve or hotel choice — cost only, no re-planning."""
        inp = plan.input
        crew = patch.crew or inp.crew
        budget = inp.budget_rub if patch.budget_rub is UNSET else patch.budget_rub
        assert budget is None or isinstance(budget, int)
        reserve_on = inp.reserve_on if patch.reserve_on is None else patch.reserve_on
        units = plan.cost.units
        days_list = plan.days_list
        if patch.hotel_choice is not None:
            sid, pid = patch.hotel_choice
            night = next((n for n in units.nights if n.stop_id == sid), None)
            if night is None:
                raise NotFound("stop", sid)
            option = next((o for o in night.options if o.place_id == pid), None)
            if option is None:
                raise NotFound("place", pid)
            nights = tuple(
                NightUnit(
                    n.stop_id,
                    n.day,
                    n.town_name_ru,
                    pid,
                    option.price_night_rub,
                    n.options,
                    False,
                    option.breakfast_included,
                    n.breakfast_check_rub,
                )
                if n.stop_id == sid
                else n
                for n in units.nights
            )
            units = dataclasses.replace(units, nights=nights)
            days_list = tuple(_with_hotel(d, sid, pid, crew) for d in plan.days_list)
        new_inp = dataclasses.replace(inp, crew=crew, budget_rub=budget, reserve_on=reserve_on)
        units = dataclasses.replace(units, child_ages=crew.child_ages)
        cost = self._with_hints(recompute(units, crew, reserve_on, budget))
        return dataclasses.replace(plan, cost=cost, input=new_inp, days_list=days_list)


# ---------------------------------------------------------------------------------------------- helpers


def _lm(dt: datetime | None, tz: str) -> datetime | None:
    return None if dt is None else local_minute(dt, tz)


def _with_hotel(d: DayResult, sid: str, pid: str, crew: Crew) -> DayResult:
    out = []
    for s in d.stops:
        if s.id == sid:
            opt: HotelOption | None = next((h for h in s.hotel_options if h.place_id == pid), None)
            if opt is not None:
                s = dataclasses.replace(
                    s,
                    selected_hotel_id=pid,
                    place_id=pid,
                    tags=opt.tags,
                    cost_rub=overnight_cost(opt.price_night_rub, crew),
                )
        out.append(s)
    return dataclasses.replace(d, stops=tuple(out))


def _planned_from_state(st: StopState, r: ScheduledStop, places: dict[str, Place]) -> PlannedStop:
    return PlannedStop(
        kind=st.kind,
        km_at=st.km_at,
        name_ru=r.name_ru,
        point=r.point,
        place=places.get(st.place_id) if st.place_id else None,
        town=None,
        detour_km=st.detour_km,
        detour_min=st.detour_min,
        dwell_min=st.dwell_min,
        fixed=st.fixed,
        auto=st.auto,
        score=st.score,
        meal=st.meal,
        reason_key=st.reason_key,
        reason_params=dict(st.reason_params),
        region_code=st.region_code,
        litres=st.litres,
        coffee=st.coffee,
    )


def _candidate_for(place_id: str, km_hint: int, state: EngineState, places: dict[str, Place]) -> Candidate:
    passes = [c for c in state.candidates if c.place_id == place_id]
    if not passes or place_id not in places:
        raise NotFound("place", place_id)
    c = min(passes, key=lambda x: abs(x.km_at - km_hint))
    return Candidate(
        places[place_id], c.km_at, c.lateral_km, c.detour_km, c.detour_min, c.road_class, c.region_code
    )


def _pools(state: EngineState, places: dict[str, Place]) -> Pools:
    by: dict[PlaceType, list[Candidate]] = {t: [] for t in PlaceType}
    for c in state.candidates:
        p = places.get(c.place_id)
        if p is None:
            continue
        by[p.type].append(
            Candidate(p, c.km_at, c.lateral_km, c.detour_km, c.detour_min, c.road_class, c.region_code)
        )
    rest = [
        *by[PlaceType.REST],
        *[c for c in by[PlaceType.FUEL] if Tag.CAFE_AT_FUEL in c.place.tags],
        *[c for c in by[PlaceType.SIGHT] if (c.place.dwell_min or 60) <= 30],
    ]
    rest.sort(key=lambda c: (c.km_at, c.place.id))
    return Pools(by[PlaceType.SIGHT], by[PlaceType.FOOD], by[PlaceType.FUEL], rest)


def _fills_after_replace(plan: TripPlan, stop_id: str, new_km: float) -> list[float] | None:
    if any(w.code is WarningCode.FUEL_GAP for w in plan.warnings):
        return None
    out = []
    for d, ds in zip(plan.days_list, plan.engine_state.days, strict=True):
        for r, st in zip(d.stops, ds.stops, strict=True):
            if st.kind is StopKind.FUEL:
                out.append(new_km if r.id == stop_id else st.km_at)
    return out


def _sched_view(sd: ScheduledDay) -> Sched:
    return Sched(
        sd.plan.day,
        sd.plan.km_start,
        sd.plan.km_end,
        sd.plan.start_at,
        sd.plan.tz,
        sd.plan.stops,
        sd.slots,
        sd.ids,
        sd.budget_min,
    )


# ---------------------------------------------------------------------------------------------- cost input


def _town_check(town: Town | None, corridor: Corridor, ctx: PlanContext) -> int:
    """Median `avg_check_rub` of the town's live food places, else the default by population (A§6.8)."""
    if town is None:
        return ctx.ports.prices.food_default_check(0)
    checks = sorted(
        c.place.avg_check_rub
        for c in corridor.food
        if c.place.town_id == town.id and c.place.avg_check_rub is not None
    )
    if checks:
        return int(statistics.median_low(checks))
    return ctx.ports.prices.food_default_check(town.population)


def _time_at(km: float, d: Sched, profile: Profile) -> datetime:
    """When the car passes route km `km` during day `d`."""
    base = d.slots[0].depart
    pos = d.stops[0].km_at
    assert base is not None
    for s, slot in zip(d.stops, d.slots, strict=True):
        if s.km_at <= km and slot.depart is not None:
            base, pos = slot.depart + timedelta(minutes=s.detour_min / 2), s.km_at
    return base + timedelta(minutes=profile.drive(pos, km))


def _cost_input(
    days: Sequence[Sched],
    choices: list[OvernightChoice],
    corridor: Corridor,
    region_kms: list[tuple[str, float]],
    toll_hits: list[TollHit],
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
) -> CostInput:
    prices = ctx.ports.prices
    regions = []
    for code, km in region_kms:
        info = ctx._region_by_code.get(code)
        regions.append(
            RegionKm(code, info.name_ru if info else code, km, prices.fuel_price(code, inp.vehicle.fuel_type))
        )
    tolls = []
    for hit in toll_hits:
        d = next((x for x in days if hit.km_from <= x.km_end + 1e-9), days[-1])
        tolls.append(TollInput(hit, local(_time_at(hit.km_from, d, profile), d.tz)))
    nights = []
    for c in choices:
        d = days[c.day - 1]
        pop = c.town.population if c.town else 0
        nights.append(
            NightInput(
                d.ids[-1],
                c.day,
                c.name_ru,
                c.hotel.place if c.hotel else None,
                tuple(h.place for h in c.hotel_options),
                prices.lodging_default_night(pop),
                _town_check(c.town, corridor, ctx),
            )
        )
    day_inputs = []
    for i, d in enumerate(days):
        lunch = next((j for j, s in enumerate(d.stops) if s.meal is Meal.LUNCH), None)
        mid = (d.km_start + d.km_end) / 2
        near = (
            min(corridor.towns, key=lambda t: (abs(t.km_at - mid), t.town.id)).town
            if corridor.towns
            else None
        )
        last = i == len(days) - 1
        arrive = d.slots[-1].arrive
        plan = DayPlan(d.day, d.km_start, d.km_end, d.start_at, d.stops, d.tz)
        day_inputs.append(
            DayInput(
                day=d.day,
                lunch_overlap=covers_lunch_window(plan, d.slots, ctx),
                lunch_stop_id=d.ids[lunch] if lunch is not None else None,
                lunch_place=d.stops[lunch].place if lunch is not None else None,
                lunch_default_check=prices.food_default_check(near.population if near else 0),
                finish_arrival_local=local(arrive, d.tz) if last and arrive is not None else None,
                finish_is_origin=inp.round_trip,
                finish_check_rub=_town_check(d.stops[-1].town, corridor, ctx),
            )
        )
    sights = tuple(
        SightInput(d.ids[j], s.place)
        for d in days
        for j, s in enumerate(d.stops)
        if s.kind is StopKind.SIGHT and s.place is not None
    )
    defaults_as_of = min((r.price.as_of for r in regions), default=ctx.clock.now().date())
    return CostInput(tuple(regions), tuple(tolls), tuple(nights), tuple(day_inputs), sights, defaults_as_of)


__all__ = ["Planner"]
