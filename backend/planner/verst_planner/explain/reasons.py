"""Stage 13: reason strings from templates (A§8.1, SPEC §7.5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from verst_planner.config import PlannerConfig
from verst_planner.domain.enums import OvernightFallback, Source, StopKind, Tag
from verst_planner.domain.facts import Known, tag_state
from verst_planner.domain.model import Crew, NormalizedInput, OvernightChoice, Place, PlannedStop, ScoredTown
from verst_planner.explain import ru
from verst_planner.explain.templates import ReasonTemplates

ON_TARGET_KM = 10


def _round(x: float) -> int:
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def crew_suffix(crew: Crew, cfg: PlannerConfig, t: ReasonTemplates) -> str:
    if crew.dog:
        return t.render("crew_suffix.dog")
    if crew.children > 0 and crew.people >= cfg.overnight_score.family_room_min_people:
        return t.render("crew_suffix.family")
    return t.render("crew_suffix.none")


def _dominant(pick: ScoredTown, other: ScoredTown | None, cfg: PlannerConfig) -> str:
    """argmax over (w_h·ΔH, w_q·ΔQ, w_e·ΔE); ties prefer hotels, then quality."""
    s = cfg.overnight_score
    base_h, base_q, base_e = (other.h_fit, other.q_town, other.e_evening) if other else (0.0, 0, 0)
    deltas = [
        (s.w_h * (pick.h_fit - base_h), 2, "overnight.shift.hotels"),
        (s.w_q * (pick.q_town - base_q), 1, "overnight.shift.quality"),
        (s.w_e * (pick.e_evening - base_e), 0, "overnight.shift.evening"),
    ]
    return max(deltas)[2]


@dataclass(frozen=True, slots=True)
class OvernightText:
    text: str
    candidates: tuple[str, ...]


def overnight_reason(
    choice: OvernightChoice,
    day_km: int,
    inp: NormalizedInput,
    cfg: PlannerConfig,
    t: ReasonTemplates,
    route_title: str | None = None,
) -> OvernightText:
    """One sentence for an overnight (US-08) plus the names of the towns considered."""
    candidates = tuple(st.town.name_ru for st in sorted(choice.considered, key=lambda st: st.km_at))
    if choice.fallback is OvernightFallback.TEMPLATE and choice.hotel is not None:
        return OvernightText(t.render("overnight.template", route=route_title or ""), candidates)
    if choice.fallback is OvernightFallback.NO_HOTEL or choice.hotel is None:
        return OvernightText(t.render("overnight.no_hotel"), candidates)
    if choice.fallback is OvernightFallback.WIDENED:
        dkm = _round(abs(choice.km_at - choice.target_km))
        direction = ru.text("label.dir_earlier" if choice.km_at < choice.target_km else "label.dir_later")
        return OvernightText(t.render("overnight.widened", dkm=dkm, dir=direction), candidates)
    pick = next((st for st in choice.considered if choice.town and st.town.id == choice.town.id), None)
    others = [st for st in choice.considered if not choice.town or st.town.id != choice.town.id]
    other = min(others, key=lambda st: (abs(st.km_at - choice.target_km), st.town.id)) if others else None
    if other is not None:
        dkm = _round(abs(choice.km_at - other.km_at))
    else:
        dkm = _round(abs(choice.km_at - choice.target_km))
    if dkm < ON_TARGET_KM or pick is None:
        text = t.render("overnight.on_target")
    else:
        if other is not None:
            key = "overnight.shift.later" if choice.km_at > other.km_at else "overnight.shift.earlier"
            shift = t.render(key, other_prep=ru.prepositional(other.town), dkm=dkm)
        elif choice.km_at < choice.target_km:
            # distance to the user's limit `day_start_km + daily_km`, not to the even-split target (A§16.8)
            limit_dkm = _round(choice.day_start_km + inp.daily_km - choice.km_at)
            shift = t.render("overnight.shift.limit", dkm=limit_dkm)
        else:
            shift = ""
        if not shift:
            text = t.render("overnight.on_target")
        else:
            factor = _dominant(pick, other, cfg)
            params: dict[str, str | int | float] = {"shift": shift}
            if factor == "overnight.shift.hotels":
                params["crew_suffix"] = crew_suffix(inp.crew, cfg, t)
            text = t.render(factor, **params)
    if day_km <= inp.daily_km:
        text += t.render("overnight.cap_ok", daily_km=inp.daily_km)
    return OvernightText(text, candidates)


def dog_sight_key(crew: Crew, place: Place | None) -> str:
    """ADR-0019 E-6: `sight.dog_waits` only when the place is known not to let dogs in, `sight.dog_ok` when
    it is known to; unknown says nothing here (the stop's `unknown_ru` says it is not checked)."""
    if not crew.dog or place is None:
        return "sight.default"
    state = tag_state(place, Tag.DOGS_ALLOWED)
    if state is Known.YES:
        return "sight.dog_ok"
    return "sight.dog_waits" if state is Known.NO else "sight.default"


def sight_reason(dwell: int, crew: Crew, place: Place) -> tuple[str, dict[str, str | int | float]]:
    """Reason key and params of a sight stop (also a short sight used as a rest, A§16.2)."""
    if place.source is Source.OSM:
        return "sight.osm", {}
    return dog_sight_key(crew, place), {"dwell": ru.duration_phrase(dwell)}


DETOUR_NOTE_MIN = 10  # M8: a sight this far off the road says so («Крюк ≈ 35 мин.»)


def stop_reason(
    s: PlannedStop,
    inp: NormalizedInput,
    cfg: PlannerConfig,
    t: ReasonTemplates,
    local_time: datetime | None,
    finish_is_home: bool,
) -> str:
    """Reason of a non-overnight stop; `local_time` = departure for START, arrival otherwise. In the
    open-data world (`sights.diversity`) a sight with a real detour ends with the honest «Крюк ≈ N мин.»."""
    text = _stop_reason(s, inp, cfg, t, local_time, finish_is_home)
    if cfg.sights.diversity and s.kind is StopKind.SIGHT and s.detour_min >= DETOUR_NOTE_MIN:
        note = t.render("sight.detour", minutes=5 * round(s.detour_min / 5))
        return f"{text} {note}" if text else note
    return text


def _stop_reason(
    s: PlannedStop,
    inp: NormalizedInput,
    cfg: PlannerConfig,
    t: ReasonTemplates,
    local_time: datetime | None,
    finish_is_home: bool,
) -> str:
    if s.kind is StopKind.START:
        assert local_time is not None
        return t.render("start.default", time=local_time.strftime("%H:%M"))
    if s.kind is StopKind.FINISH:
        if finish_is_home and local_time is not None:
            return t.render("finish.home", part_of_day=ru.part_of_day(local_time.time()))
        return t.render("finish.default")
    if s.kind is StopKind.VIA:
        return t.render("via.user")
    if (
        s.place is not None
        and s.place.source is Source.OSM
        and s.kind is StopKind.SIGHT
        and not s.reason_key.startswith("rest.fun.")  # ADR-0015 §5: the fun stop says why it was chosen
    ):
        return t.render("sight.osm")
    if s.kind is StopKind.SIGHT and s.fixed:
        dwell = ru.duration_phrase(s.dwell_min)
        return t.render(dog_sight_key(inp.crew, s.place), dwell=dwell)
    if not s.reason_key:
        return ""
    return t.render(s.reason_key, **s.reason_params)
