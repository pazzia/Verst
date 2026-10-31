"""What the engine knows about a place: yes / no / unknown (ADR-0019, the ADR-0018 §10 follow-ups E-1…E-6).

One module owns every "is this fact known?" rule, so the pipeline, the cost model, the stop rendering and the
mobile bridge read the same answer. A missing value is never read as a convenient default:

* E-1 `opening_hours` None = hours unknown (not «always open»); `24/7` or the `24h` tag = round the clock.
* E-2 ticket None without `free_entry` = price unknown (not free); `0` or `free_entry` = free.
* E-3 `breakfast_included` None = unknown; the cost model budgets the breakfast (`breakfast_confirmed`).
* E-4 `fuel_kinds` / `fuel_kinds_no` = the fuels a station sells / does not sell; neither = unknown.
* E-5 `rating_internal` None = no rating; it ranks below every rated place (`rank_rating`).
* E-6 `tags` / `tags_no` = confirmed yes / confirmed no; a tag in neither set is unknown.
"""

from __future__ import annotations

from enum import StrEnum

from verst_planner.domain.enums import FuelType, PlaceType, Tag
from verst_planner.domain.model import Place

UNRATED_RANK = 0.0
"""E-5: the rating an unrated place ranks with — below any real rating (the 0..5 scale), so it is only a
fallback when no rated place fits; never the old silent 3.0."""

HOURS_TYPES = frozenset({PlaceType.SIGHT, PlaceType.FOOD, PlaceType.FUEL})
"""E-1: place types whose stop depends on an opening time the user can check. A rest area is open-air and a
hotel's reception is confirmed by the booking, so the engine claims nothing about their hours."""


class Known(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class Fact(StrEnum):
    """The wire keys of `ScheduledStop.unknown_facts` (stop JSON `unknownFacts`)."""

    HOURS = "hours"
    TICKET = "ticket"
    FUEL = "fuel"
    DOGS = "dogs"
    PRICE = "price"  # CEO 29.10: a night or a meal abroad — no price data there (never a rouble default)


def rank_rating(p: Place) -> float:
    """E-5: the rating used for ranking; an unrated place ranks with `UNRATED_RANK`."""
    return UNRATED_RANK if p.rating_internal is None else p.rating_internal


def hours_known(p: Place) -> bool:
    """E-1: the place has opening hours (any text, `24/7` included) or the `24h` tag."""
    return p.opening_hours is not None or Tag.H24 in p.tags


def ticket_known(p: Place) -> bool:
    """E-2: the entry is confirmed free (`free_entry`) or has a price (`0` = free)."""
    return Tag.FREE_ENTRY in p.tags or p.ticket_adult_rub is not None


def ticket_prices(p: Place) -> tuple[int, int]:
    """(adult, child) ticket as costed (A§7.1): `free_entry` -> 0; the child price falls back to the adult
    one. An unknown price (E-2) is also (0, 0): it stays out of every sum and is named instead
    (`ticket_known`)."""
    if Tag.FREE_ENTRY in p.tags or p.ticket_adult_rub is None:
        return 0, 0
    adult = p.ticket_adult_rub
    return adult, p.ticket_child_rub if p.ticket_child_rub is not None else adult


def confirmed_free(p: Place) -> bool:
    """E-2: entry is known to cost nothing (the `sights_free` budget lever keeps only these)."""
    return Tag.FREE_ENTRY in p.tags or p.ticket_adult_rub == 0


def breakfast_confirmed(p: Place) -> bool:
    """E-3: breakfast is known to be included; unknown is costed as not included (conservative)."""
    return p.breakfast_included is True


def tag_state(p: Place, tag: Tag) -> Known:
    """E-6: yes / no / unknown of one tag."""
    if tag in p.tags:
        return Known.YES
    if tag in p.tags_no:
        return Known.NO
    return Known.UNKNOWN


def fuel_state(p: Place, fuel: FuelType) -> Known:
    """E-4: whether a station sells `fuel`."""
    if fuel in p.fuel_kinds:
        return Known.YES
    if fuel in p.fuel_kinds_no:
        return Known.NO
    return Known.UNKNOWN
