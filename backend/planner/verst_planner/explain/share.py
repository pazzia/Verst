"""Share text (A§8.2). The Kotlin `ShareTextBuilder` reproduces it from `docs/contracts/share-text/*.json`."""

from __future__ import annotations

from verst_planner.domain.enums import StopKind
from verst_planner.domain.model import TripPlan
from verst_planner.explain import ru


def share_text(plan: TripPlan) -> str:
    """Title line, one block per day («День N · km» + «HH:MM name» per stop), total line.

    The deep link (if the trip is saved) is appended by the caller.
    """
    lines = [
        ru.text(
            "share.header",
            title=plan.title_ru,
            km=ru.fmt_int(plan.km),
            days=plan.days,
            days_word=ru.days_word(plan.days),
        )
    ]
    for d in plan.days_list:
        lines.append(ru.text("share.day", day=d.day, km=ru.fmt_int(d.km)))
        for s in d.stops:
            at = s.depart_at if s.kind is StopKind.START else s.arrive_at
            hhmm = at.strftime("%H:%M") if at is not None else ""
            lines.append(ru.text("share.stop", time=hhmm, name=s.name_ru))
    people = plan.input.crew.adults + plan.input.crew.children
    lines.append(ru.text("share.total", total=ru.fmt_rub(plan.cost.total_rub), people=people))
    return "\n".join(lines)
