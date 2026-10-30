"""Rooms for a crew in one hotel (A§7.1 [D-15], ADR-0011 family rooms)."""

from __future__ import annotations

import math

from verst_planner.domain.enums import Tag
from verst_planner.domain.model import Crew, Place

FAMILY_ROOM_GUESTS = 4
FAMILY_PRICE_FACTOR = 1.4


def standard_rooms(crew: Crew) -> int:
    """`ceil(adults / 2)`; children share."""
    return -(-crew.adults // 2)


def family_price(p: Place) -> int:
    if p.family_price_rub is not None:
        return p.family_price_rub
    return math.floor((p.price_night_rub or 0) * FAMILY_PRICE_FACTOR / 100 + 0.5) * 100


def room_plan(p: Place, crew: Crew, family: bool) -> tuple[int, int, bool]:
    """`(rooms, price per room, explicit)`: standard rooms, or family rooms (≤ 4 guests each) when the knob
    is on, the hotel has them and they cost less in total. `explicit`: store the result in the units."""
    price = p.price_night_rub or 0
    std = standard_rooms(crew)
    if not family or Tag.FAMILY_ROOM not in p.tags or not price:
        return std, price, False
    fam_rooms = -(-(crew.adults + crew.children) // FAMILY_ROOM_GUESTS)
    fam_price = family_price(p)
    if fam_rooms * fam_price < std * price:
        return fam_rooms, fam_price, True
    return std, price, False
