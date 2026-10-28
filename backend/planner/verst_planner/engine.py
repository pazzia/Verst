"""`Planner` facade (A§6.1): stages 0-13, progress events (A§8.3), cancellation, replace and cost patches."""

from __future__ import annotations

import dataclasses
import statistics
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

from verst_planner import ENGINE_VERSION
from verst_planner import fit as fit_mod
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
    people_weight,
    sight_cost,
)
from verst_planner.cost.money import round_to
from verst_planner.cost.recompute import effective_parking, effective_tickets, recompute, rooms_for
from verst_planner.domain.enums import (
    FuelType,
    Meal,
    PlaceType,
    SignType,
    Source,
    StageKey,
    StopKind,
    Tag,
    WarningCode,
)
from verst_planner.domain.errors import InvalidInput, NotFound, TooShort
from verst_planner.domain.model import (
    UNSET,
    Alternative,
    AltUnits,
    Candidate,
    CostOverrides,
    CostPatch,
    CostResult,
    CostUnits,
    Crew,
    DayPlan,
    DayResult,
    DayState,
    EngineState,
    FitKnobs,
    FuelRegionUnit,
    HotelOption,
    MealUnit,
    NightUnit,
    NormalizedInput,
    OvernightChoice,
    OvernightReason,
    ParkingUnit,
    Place,
    PlannedStop,
    PlanWarning,
    PointInput,
    ReadyRoute,
    RegionPrice,
    ScheduledStop,
    StopState,
    TollHit,
    Town,
    TownCandidate,
    TripInput,
    TripPlan,
)
from verst_planner.domain.rooms import room_plan
from verst_planner.events import NEVER, NULL_SINK, CancelToken, ProgressSink, StageEvent, StopEvent
from verst_planner.explain import ru
from verst_planner.explain.reasons import overnight_reason
from verst_planner.explain.templates import ReasonTemplates
from verst_planner.geo.distance import haversine_km
from verst_planner.pipeline import Corridor, PlanContext, Ports, round_half_up
from verst_planner.pipeline import fuel as fuel_stage
from verst_planner.pipeline.alternatives import (
    Pools,
    alternatives_for_day,
    build_alternatives,
    day_patch,
    family,
    lunch_check,
    trial_day,
)
from verst_planner.pipeline.assemble import (
    Sched,
    StopView,
    engine_state,
    hotel_option,
    region_km,
    render_day,
    stop_state,
    title,
)
from verst_planner.pipeline.base_route import build_base_route, toll_warnings
from verst_planner.pipeline.checks import budget_limit, covers_lunch_window
from verst_planner.pipeline.corridor import build_corridor, place_fixed
from verst_planner.pipeline.day_split import split_days
from verst_planner.pipeline.overnight import choose_overnights
from verst_planner.pipeline.resolve import normalize_input, resolve_points
from verst_planner.pipeline.rest import plan_rests
from verst_planner.pipeline.schedule import ScheduledDay, assign_ids, schedule_with_rerun
from verst_planner.pipeline.sights import admit_sights, plan_lunch_after_sights, plan_lunches, plan_sights
from verst_planner.pipeline.timeline import (
    Profile,
    build_day_plans,
    day_duration_min,
    detour_halves,
    local,
    local_minute,
)
from verst_planner.pipeline.town_visit import plan_town_visits
from verst_planner.ports import (
    Clock,
    GeocodingPort,
    ParkingPort,
    PlaceRepository,
    PriceRepository,
    RegionLocator,
    RoutingPort,
    TollRepository,
)

ECONOMY_CHECK_FACTOR = Decimal("0.75")
NO_KNOBS = FitKnobs()


class _EconomyPrices:
    """ADR-0011 `food_economy`: default meal checks at the «кафе попроще» tier (x 0.75, to 10 ₽)."""

    def __init__(self, inner: PriceRepository) -> None:
        self.inner = inner

    def fuel_price(self, region_code: str, fuel_type: FuelType) -> RegionPrice:
        return self.inner.fuel_price(region_code, fuel_type)

    def food_default_check(self, town_population: int) -> int:
        return round_to(Decimal(self.inner.food_default_check(town_population)) * ECONOMY_CHECK_FACTOR, 10)

    def lodging_default_night(self, town_population: int) -> int:
        return self.inner.lodging_default_night(town_population)

    def defaults_as_of(self) -> date:
        return self.inner.defaults_as_of()


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
        parking: ParkingPort | None = None,
    ) -> None:
        self.ports = Ports(routing, places, prices, tolls, regions, geocoding, parking)
        self.clock = clock
        self.cfg = config
        self.templates = templates

    # ------------------------------------------------------------------------------------------ context
    def _ctx(self, knobs: FitKnobs = NO_KNOBS) -> PlanContext:
        ports = self.ports
        if knobs.food_economy:
            ports = dataclasses.replace(ports, prices=_EconomyPrices(ports.prices))
        ctx = PlanContext(self.cfg, self.templates, ports, self.clock, knobs=knobs)
        ctx.stop_cost = lambda s, inp: self._stop_cost(s, inp, ctx)
        return ctx

    def _stop_cost(self, s: PlannedStop, inp: NormalizedInput, ctx: PlanContext) -> int:
        """Per-stop `cost_rub` (A§7.1): tickets, a meal for the crew, the room(s), informational fuel."""
        crew = inp.crew
        if s.kind is StopKind.SIGHT and s.place is not None:
            return sight_cost(s.place, crew)
        if s.kind is StopKind.FOOD and s.place is not None:
            return food_cost(lunch_check(s, ctx), crew, self.cfg)
        if s.kind is StopKind.OVERNIGHT:
            if s.place is not None and s.place.price_night_rub is not None:
                rooms, price, _explicit = room_plan(s.place, crew, ctx.knobs.family_rooms)
                return overnight_cost(price, crew, rooms)
            pop = s.town.population if s.town is not None else 0
            return overnight_cost(self.ports.prices.lodging_default_night(pop), crew)
        if s.kind is StopKind.FUEL and s.litres > 0:
            return fuel_stop_cost(
                s.litres, self.ports.prices.fuel_price(s.region_code, inp.vehicle.fuel_type)
            )
        return 0

    # ------------------------------------------------------------------------------------------ estimate
    def estimate_km(self, raw: TripInput, check_too_short: bool = True) -> int:
        """Road km of the base route (stages 0 to 2, no corridor): the pre-plan distance the app shows.

        The same normalisation, point resolution, routing and snap check as `plan`, so a plan of the same
        input has `km == estimate_km + round(Σ stop detours)` (± 1 for per-day rounding). Raises what `plan`
        raises for these stages (`TooShort` only when `check_too_short`, `Unreachable`, `InvalidInput`)."""
        ctx = self._ctx()
        inp = normalize_input(raw, ctx)
        pts = resolve_points(inp, ctx)
        try:
            route = build_base_route(pts, inp, ctx)
        except TooShort as e:
            if check_too_short:
                raise
            return round_half_up(e.road_km)
        return round_half_up(route.km_total)

    # ------------------------------------------------------------------------------------------ plan
    def plan(
        self,
        raw: TripInput,
        sink: ProgressSink = NULL_SINK,
        cancel: CancelToken = NEVER,
        split_km_hint: int | None = None,
    ) -> TripPlan:
        """Plan and fit to the budget (ADR-0011): the plain plan when it fits or there is no budget, else the
        fitted plan (`budget_fit` set), else `fit.NoFit` (the minimum and the options).

        `split_km_hint`: the trip km of an earlier identical plan (mobile `estimate`), so the split stage
        says «по ≈ {km}» with the trip km (incl. stop detours), not the base route km (slice-2 N-10)."""
        s0 = self._plan_once(raw, sink, cancel, split_km_hint, NO_KNOBS)
        try:
            plan = fit_mod.fit(raw, s0, _FitEnv(self, cancel))
        except fit_mod.NoFit as nf:
            sink.emit(StageEvent(StageKey.BUDGET, self.templates.render("stage.budget"), 0.92))
            self._emit_final(nf.minimum, sink)
            raise
        if plan.budget_fit is not None:
            sink.emit(StageEvent(StageKey.BUDGET, self.templates.render("stage.budget"), 0.92))
        self._emit_final(plan, sink)
        return plan

    @staticmethod
    def _emit_final(plan: TripPlan, sink: ProgressSink) -> None:
        for d in plan.days_list:
            for s in d.stops:
                sink.emit(StopEvent(d.day, s.id, s.kind, s.sign, s.name_ru, s.km_at, False))

    def _plan_once(
        self,
        raw: TripInput,
        sink: ProgressSink,
        cancel: CancelToken,
        split_km_hint: int | None,
        knobs: FitKnobs,
    ) -> TripPlan:
        """Stages 0-12 with the budget levers `knobs` (ADR-0011); no final stop events."""
        ctx = self._ctx(knobs)
        t = self.templates
        inp = normalize_input(raw, ctx)
        pts = resolve_points(inp, ctx)
        cancel.check()  # before stage 2
        sink.emit(StageEvent(StageKey.SPLIT, t.render("stage.route"), 0.05))
        route = build_base_route(pts, inp, ctx)
        warnings: list[PlanWarning] = list(toll_warnings(route, inp, ctx))
        cancel.check()  # before stage 3
        corridor = build_corridor(route, inp, ctx)
        admit_sights(corridor, inp, ctx)
        ctx.corridor_towns = corridor.towns
        split = split_days(route, corridor, inp, pts.template, ctx)
        ring = pts.template is not None and inp.round_trip
        sink.emit(
            StageEvent(
                StageKey.SPLIT,
                t.render(
                    "stage.split_ring" if ring else "stage.split",
                    n=split.n_days,
                    days_word=ru.days_word(split.n_days),
                    km=round_half_up((split_km_hint or route.km_total) / split.n_days),
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
        # execution order A§16.2: 6 fuel → 8 lunch → 9 sights → 8b lunch → 7 rests → 10 schedule/repair
        ctx.fuel_warnings = fuel_stage.plan_fuel(days, corridor, inp, ctx)
        plan_lunches(days, corridor, inp, ctx)
        sink.emit(StageEvent(StageKey.HOURS, t.render("stage.hours"), 0.65))
        cancel.check()  # before stage 9
        plan_sights(days, corridor, inp, ctx)
        plan_lunch_after_sights(days, corridor, inp, ctx)
        plan_town_visits(days, corridor, inp, ctx)
        plan_rests(days, corridor, inp, ctx)
        cancel.check()  # before stage 10
        sched, sched_warnings = schedule_with_rerun(days, corridor, inp, ctx)
        assign_ids(sched)
        build_alternatives(sched, corridor, inp, ctx)
        sink.emit(StageEvent(StageKey.COST, t.render("stage.cost"), 0.90))
        cancel.check()  # before stage 12
        # QA B-1: an approximate route has no road refs; its toll corridor (if any) is priced by the tolls
        # port. «Избегать платных» there means the free parallel roads (M-10, M-7, the old M-4): no tolls.
        avoid_approx = route.synthetic and inp.avoid_tolls
        toll_hits = [] if avoid_approx else self.ports.tolls.segments_on_route(route)
        tolls_unknown = route.synthetic and not avoid_approx and not toll_hits
        all_stops = [s for sd in sched for s in sd.plan.stops]
        region_kms = region_km(route, all_stops, ctx)
        views = [_sched_view(sd) for sd in sched]
        cost = compute_cost(
            dataclasses.replace(
                _cost_input(views, nights.choices, corridor, region_kms, toll_hits, inp, ctx, profile),
                tolls_unknown=tolls_unknown,
            ),
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
            views: dict[int, StopView] = {
                i: StopView(alternatives=a, alternatives_note=sd.alternatives_note.get(i))
                for i, a in sd.alternatives.items()
            }
            if sd.plan.stops[-1].kind is StopKind.OVERNIGHT:
                c = choices[sd.plan.day - 1]
                day_km = round_half_up(
                    sd.plan.km_end - sd.plan.km_start + sum(s.detour_km for s in sd.plan.stops)
                )
                text = overnight_reason(
                    c, day_km, inp, self.cfg, self.templates, template_title, ctx.knobs.norm_from_km
                )
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
                    hotel_options=tuple(
                        hotel_option(h.place, inp, h.lateral_km, ctx.knobs.family_rooms)
                        for h in c.hotel_options
                    ),
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
        crossing = next((d.day for d in days if any(s.local_tz is not None for s in d.stops)), None)
        if crossing is not None:  # QA B-4: say once that a day's clock is the one it started with
            warnings = [*warnings, ctx.warning(WarningCode.TIME_ZONE, crossing, "tz_change", day=crossing)]
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
            approx_distances=corridor.route.synthetic,
        )

    # ------------------------------------------------------------------------------------------ replace
    def replace_stop(self, plan: TripPlan, stop_id: str, alternative_id: str) -> TripPlan:
        """Swap in an alternative and re-schedule only that day from `EngineState` (no routing call).

        The new day is built exactly as stage 11 built the alternative (`trial_day`), so it equals the
        alternative's `day_patch` (A§16.6); then that day's alternatives and the cost are recomputed.
        """
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
        ctx.corridor_towns = town_cands
        stops = [_planned_from_state(st, r, places) for st, r in zip(ds.stops, old_day.stops, strict=True)]
        day = DayPlan(ds.day, ds.km_start, ds.km_end, ds.start_at, stops, ds.tz)
        cand = _candidate_for(alt.place_id, alt.stop.km_at, state, places)
        trial = trial_day(day, si, cand, inp, ctx, profile, town_cands)
        old_ids = [r.id for r in old_day.stops]
        seq0 = old_day.stops[0].seq
        patch = day_patch(trial, old_ids, si, seq0, ctx)
        ids = [p.stop_id for p in patch]
        rendered_by_id = {r.id: r for r in old_day.stops}
        rendered_by_id[stop_id] = alt.stop
        new_stops = [
            dataclasses.replace(
                rendered_by_id[p.stop_id],
                seq=p.seq,
                day=ds.day,
                arrive_at=p.arrive_at,
                depart_at=p.depart_at,
                km_from_prev=p.km_from_prev,
                km_at=round_half_up(s.km_at),
                alternatives=(),
                alternatives_note_ru=None,
            )
            for p, s in zip(patch, trial.plan.stops, strict=True)
        ]
        # alternatives of that day, from the persisted candidate pools
        sd = ScheduledDay(trial.plan, trial.slots, ds.budget_min, ids=ids, seq0=seq0)
        used = {r.place_id for d in plan.days_list for r in d.stops if r.place_id} - {old_rendered.place_id}
        used.add(alt.place_id)
        fills = _fills_after_replace(plan, stop_id, cand.km_at)
        alts, notes = alternatives_for_day(
            sd,
            _pools(state, places),
            {u for u in used if u},
            inp,
            ctx,
            profile,
            fills,
            state.profile_km[-1],
            town_cands,
        )
        new_stops = [
            dataclasses.replace(s, alternatives=alts.get(k, ()), alternatives_note_ru=notes.get(k))
            if family(trial.plan.stops[k])
            else s
            for k, s in enumerate(new_stops)
        ]
        duration = day_duration_min(trial.plan, trial.slots)
        over = duration > budget_limit(trial.plan, profile, ds.budget_min) + 1e-6
        new_day = DayResult(
            day=ds.day,
            km=round_half_up(ds.km_end - ds.km_start + sum(s.detour_km for s in trial.plan.stops)),
            drive_min=round_half_up(sum(x.drive_min for x in trial.slots)),
            tz=old_day.tz,
            start_at=old_day.start_at,
            end_at=_lm(trial.slots[-1].arrive, old_day.tz) or old_day.end_at,
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
        trip_km = sum(d.km for d in days_list)
        units = _units_after_replace(plan.cost.units, stop_id, alt.units)
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
                    tuple(stop_state(s, sid) for s, sid in zip(trial.plan.stops, ids, strict=True)),
                )
                if k == di
                else x
                for k, x in enumerate(state.days)
            ),
        )
        return self._flagged(
            dataclasses.replace(
                plan,
                days_list=days_list,
                km=trip_km,
                cost=cost,
                warnings=tuple(warnings),
                engine_state=new_state,
            )
        )

    def _flagged(self, plan: TripPlan) -> TripPlan:
        """ADR-0011: re-mark `breaksBudget` on the alternatives after an edit."""
        budget = plan.input.budget_rub
        env = _FitEnv(self, NEVER)
        if budget is None:
            return fit_mod.flag_alternatives(plan, 10**12, env)
        return fit_mod.flag_alternatives(plan, fit_mod.allowed_rub(budget), env)

    # ------------------------------------------------------------------------------------------ cost patch
    def recompute_cost(self, plan: TripPlan, patch: CostPatch) -> TripPlan:
        """PATCH /v1/trips/{id}: crew, budget, reserve or hotel choice — cost only, no re-planning."""
        inp = plan.input
        crew = patch.crew or inp.crew
        if crew.dog != inp.crew.dog or (crew.children > 0) != (inp.crew.children > 0):
            # the lodging filters change (US-05): only a re-plan may pick other hotels (A§16.9)
            raise InvalidInput("crew", "replan_required")
        if crew != inp.crew and any(
            n.rooms is not None or any(o.rooms is not None for o in n.options) for n in plan.cost.units.nights
        ):
            raise InvalidInput("crew", "replan_required")  # ADR-0011: fitted family rooms depend on the crew
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
                    option.rooms,
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
        if crew != inp.crew:
            days_list = tuple(_recrew_day(d, units, new_inp, self.cfg) for d in days_list)
        return self._flagged(dataclasses.replace(plan, cost=cost, input=new_inp, days_list=days_list))


# ---------------------------------------------------------------------------------------------- fitting


CLOSER_MIN_FRAC, CLOSER_MAX_FRAC, CLOSER_BEST_FRAC = 0.40, 0.75, 0.60
CLOSER_MIN_POPULATION = 20_000
CLOSER_CORRIDOR_KM = 60.0
HUB_RADIUS_KM = 50.0


class _FitEnv:
    """`fit.FitEnv` over this planner and its ports (ADR-0011)."""

    def __init__(self, planner: Planner, cancel: CancelToken) -> None:
        self.p = planner
        self.cancel = cancel

    def plan(self, raw: TripInput, knobs: FitKnobs) -> TripPlan:
        return self.p._plan_once(raw, NULL_SINK, self.cancel, None, knobs)

    def variants(self, ready_route_id: str) -> list[ReadyRoute]:
        get = getattr(self.p.ports.places, "variants_of", None)
        return list(get(ready_route_id)) if get is not None else []

    def hub_routes(self, ready_route_id: str) -> list[ReadyRoute]:
        places = self.p.ports.places
        rr = places.get_ready_route(ready_route_id)
        if rr is None:
            return []
        hub = places.get_towns([rr.hub_town_id]).get(rr.hub_town_id)
        if hub is None:
            return []
        routes = places.ready_routes_near(hub.point, HUB_RADIUS_KM, 20)
        out = [r for r in routes if r.id != ready_route_id and r.id != rr.parent_id]
        return sorted(out, key=lambda r: (r.km_total, r.id))

    def towns_towards(self, raw: TripInput, plan: TripPlan, limit: int) -> list[PointInput]:
        if raw.destination is None:
            return []
        a, b = raw.origin.point, raw.destination.point
        total = haversine_km(a, b)
        if total <= 0:
            return []
        places = self.p.ports.places
        towns = places.towns_in_corridor((a, b), CLOSER_CORRIDOR_KM)
        lodgings = places.lodgings_of_towns([t.id for t in towns])
        picks = []
        for t in towns:
            frac = haversine_km(a, t.point) / total
            if not CLOSER_MIN_FRAC <= frac <= CLOSER_MAX_FRAC or t.population < CLOSER_MIN_POPULATION:
                continue
            if not lodgings.get(t.id):
                continue
            picks.append((abs(frac - CLOSER_BEST_FRAC), t.id, t))
        picks.sort(key=lambda x: (x[0], x[1]))
        return [PointInput(t.point, t.name_ru, None, t.id) for _f, _i, t in picks[:limit]]

    def check_cancel(self) -> None:
        self.cancel.check()

    def text(self, key: str, **params: str | int) -> str:
        return ru.text(key, **params)

    def recompute_total(self, plan: TripPlan, overrides: CostOverrides) -> int:
        inp = plan.input
        return recompute(plan.cost.units, inp.crew, inp.reserve_on, inp.budget_rub, overrides).total_rub


# ---------------------------------------------------------------------------------------------- helpers


def _units_after_replace(u: CostUnits, stop_id: str, alt: AltUnits) -> CostUnits:
    """Bake a replace into the units so that `recompute(units')` equals
    `recompute(units, replaced={stop_id: alt})` (A§16.11.4 rules 1-4, parking rule 5)."""
    regions = list(u.fuel.regions)
    codes = [r.region_code for r in regions]
    if alt.region_code in codes:
        k = codes.index(alt.region_code)
        r = regions[k]
        km = max(0.0, round(r.km + alt.delta_km, 3))
        regions[k] = FuelRegionUnit(r.region_code, r.region_name_ru, km, r.price_rub)
    elif alt.price_rub is not None and alt.delta_km > 0:
        regions.append(
            FuelRegionUnit(alt.region_code, alt.region_name_ru, round(alt.delta_km, 3), alt.price_rub)
        )
    meals = tuple(
        MealUnit(m.day, m.meal, m.stop_id, alt.check_rub)
        if m.stop_id == stop_id and alt.check_rub is not None
        else m
        for m in u.meals
    )
    ov = CostOverrides(replaced={stop_id: alt})
    tickets = tuple(effective_tickets(u, ov))
    parking = tuple(effective_parking(u, ov)) if u.parking else ()  # rule 5 (API v3)
    trip_km = None if u.fuel.trip_km is None else u.fuel.trip_km + alt.trip_km_delta
    fuel = dataclasses.replace(u.fuel, regions=tuple(regions), trip_km=trip_km)
    return dataclasses.replace(u, fuel=fuel, meals=meals, tickets=tickets, parking=parking)


def _recrew_day(d: DayResult, units: CostUnits, inp: NormalizedInput, cfg: PlannerConfig) -> DayResult:
    """A§16.9: after a crew change, re-render every stop's `cost_rub` (tickets, the lunch, the rooms),
    the hotel options' rooms and crew price, and the alternatives' costs, so Road ahead agrees with the
    Waybill."""
    crew = inp.crew
    tickets = {t.stop_id: t for t in units.tickets}
    lunches = {m.stop_id: m.check_rub for m in units.meals if m.meal is Meal.LUNCH and m.stop_id}
    nights = {n.stop_id: n for n in units.nights}
    parks = {p.stop_id: p.rub or 0 for p in units.parking}  # crew-independent, kept in the alt deltas
    rooms = rooms_for(crew)
    cons = Decimal(repr(units.fuel.consumption_l_per_100km))

    def ticket_cost(adult: int, child: int) -> int:
        return round_to(Decimal(crew.adults * adult + crew.children * child), 10)

    def exact(sid: str, au: AltUnits | None) -> Decimal:
        """Unrounded stop cost (tickets or the crew's lunch) of the stop or of an alternative."""
        if au is not None:
            if au.adult_rub is not None:
                child = au.child_rub if au.child_rub is not None else au.adult_rub
                return Decimal(crew.adults * au.adult_rub + crew.children * child)
            if au.check_rub is not None:
                return Decimal(repr(people_weight(crew, cfg))) * au.check_rub
            return Decimal(0)
        if sid in tickets:
            t = tickets[sid]
            return Decimal(crew.adults * t.adult_rub + crew.children * t.child_rub)
        if sid in lunches:
            return Decimal(repr(people_weight(crew, cfg))) * lunches[sid]
        return Decimal(0)

    def alt_cost(a: Alternative) -> int:
        au = a.units
        if au.adult_rub is not None:
            return ticket_cost(au.adult_rub, au.child_rub if au.child_rub is not None else au.adult_rub)
        if au.check_rub is not None:
            return food_cost(au.check_rub, crew, cfg)
        return a.stop.cost_rub

    out = []
    for s in d.stops:
        cost = s.cost_rub
        if s.id in tickets:
            cost = ticket_cost(tickets[s.id].adult_rub, tickets[s.id].child_rub)
        elif s.id in lunches:
            cost = food_cost(lunches[s.id], crew, cfg)
        elif s.id in nights:
            cost = overnight_cost(nights[s.id].price_night_rub, crew)
        options = tuple(
            dataclasses.replace(h, rooms=rooms, price_crew_rub=rooms * h.price_night_rub)
            for h in s.hotel_options
        )
        alts = []
        for a in s.alternatives:
            au = a.units
            fuel = Decimal(repr(au.delta_km)) * cons / 100 * (au.price_rub or Decimal(0))
            park = (0 if au.parking is None else au.parking.rub or 0) - parks.get(s.id, 0)
            delta = round_to(exact(s.id, au) - exact(s.id, None) + fuel + park, 10)
            alts.append(
                dataclasses.replace(
                    a, delta_rub=delta, stop=dataclasses.replace(a.stop, cost_rub=alt_cost(a))
                )
            )
        out.append(dataclasses.replace(s, cost_rub=cost, hotel_options=options, alternatives=tuple(alts)))
    return dataclasses.replace(d, stops=tuple(out))


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
                    cost_rub=overnight_cost(opt.price_night_rub, crew, opt.rooms),
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
        pool=st.pool,
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
            if st.kind is StopKind.FUEL and st.pool in ("fuel", ""):
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
        # ADR-0011 `food_economy`: the cheapest place in town instead of the median one
        return checks[0] if ctx.knobs.food_economy else int(statistics.median_low(checks))
    return ctx.ports.prices.food_default_check(town.population)


def _time_at(km: float, d: Sched, profile: Profile) -> datetime:
    """When the car passes route km `km` during day `d`."""
    base = d.slots[0].depart
    pos = d.stops[0].km_at
    assert base is not None
    for s, slot, (_in, out) in zip(d.stops, d.slots, detour_halves(d.stops), strict=True):
        if s.km_at <= km and slot.depart is not None:
            base, pos = slot.depart + timedelta(minutes=out), s.km_at
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
        info = ctx.region_info(code)
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
                ctx.knobs.family_rooms,
            )
        )
    day_inputs = []
    for i, d in enumerate(days):
        lunch = next((j for j, s in enumerate(d.stops) if s.meal is Meal.LUNCH), None)
        ref_km = d.stops[lunch].km_at if lunch is not None else (d.km_start + d.km_end) / 2
        last = i == len(days) - 1
        arrive = d.slots[-1].arrive
        plan = DayPlan(d.day, d.km_start, d.km_end, d.start_at, d.stops, d.tz)
        day_inputs.append(
            DayInput(
                day=d.day,
                lunch_overlap=covers_lunch_window(plan, d.slots, ctx),
                lunch_stop_id=d.ids[lunch] if lunch is not None else None,
                lunch_place=d.stops[lunch].place if lunch is not None else None,
                lunch_default_check=ctx.default_check_at(ref_km),
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
    trip_km = sum(round_half_up(d.km_end - d.km_start + sum(s.detour_km for s in d.stops)) for d in days)
    return CostInput(
        tuple(regions),
        tuple(tolls),
        tuple(nights),
        tuple(day_inputs),
        sights,
        prices.defaults_as_of(),
        trip_km,
        _parking(days, ctx),
        ctx.ports.parking.as_of if ctx.ports.parking is not None else None,
    )


PARKED_KINDS = frozenset({StopKind.SIGHT, StopKind.FOOD, StopKind.REST})


def _parking(days: Sequence[Sched], ctx: PlanContext) -> tuple[ParkingUnit, ...]:
    """ADR-0015 §4: the car is parked at every stop where the crew leaves it — sights, cafés and rest areas
    (M9: in a paid zone a lunch costs its parking too); not at a fuel pump, a roadside break or a hotel."""
    model = ctx.ports.parking
    if model is None:
        return ()
    out = []
    for d in days:
        for j, (s, slot) in enumerate(zip(d.stops, d.slots, strict=True)):
            if s.kind in PARKED_KINDS and s.place is not None and slot.arrive is not None:
                out.append(model.unit(d.ids[j], s.name_ru, s.point, local(slot.arrive, d.tz), s.dwell_min))
    return tuple(out)


__all__ = ["Planner"]
