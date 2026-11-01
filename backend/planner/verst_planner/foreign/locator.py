"""Which supported country a point is in (CEO 29.10): the nearest catalogue town within `INSIDE_KM`.

There are no country polygons in the data. A point within 60 km of a catalogue town (the app's
`insideRussia` radius) belongs to the country of the nearest one — Russia or a loaded catalogue abroad. A
point with no town within 60 km keeps the engine's old rule (coordinator, 29.10: no regression for Russia):
inside the Russia box of A§6.2 (`pipeline.resolve.in_russia`; it covers Crimea, which has no town in the
Russian catalogue) it is Russia and is routed as before (Телецкое озеро); outside the box it is unsupported.
Near a border the nearest town can be across it: the result is the country of that town, and the trip says
the border point is approximate.
"""

from __future__ import annotations

from collections.abc import Iterable

from verst_planner.domain.model import LatLon, Town
from verst_planner.foreign.rules import RUSSIA
from verst_planner.geo.grid import GridIndex
from verst_planner.pipeline.resolve import in_russia

INSIDE_KM = 60.0
"""The app's `insideRussia` radius (`mobile.INSIDE_RUSSIA_KM`), for every country."""
class CountryLocator:
    def __init__(self, russian: Iterable[Town], abroad: Iterable[tuple[str, Town]]) -> None:
        self.russian: GridIndex[Town] = GridIndex(0.25)
        for t in sorted(russian, key=lambda t: t.id):
            self.russian.add(t.point, t)
        self.abroad: GridIndex[tuple[str, Town]] = GridIndex(0.25)
        self.countries: set[str] = set()
        for code, t in sorted(abroad, key=lambda ct: (ct[0], ct[1].id)):
            self.abroad.add(t.point, (code, t))
            self.countries.add(code)

    def nearest(self, p: LatLon, max_km: float = INSIDE_KM) -> tuple[float, str, Town] | None:
        """(km, country, town) of the nearest catalogue town within `max_km` (Russia wins a tie)."""
        ru = self.russian.nearest(p, max_km)
        ab = self.abroad.nearest(p, max_km)
        if ab is not None and (ru is None or ab[0] < ru[0]):
            return ab[0], ab[1][0], ab[1][1]
        if ru is not None:
            return ru[0], RUSSIA, ru[1]
        return None

    def town_country(self, p: LatLon) -> str | None:
        """The country of the nearest catalogue town within 60 km only (no box): where a border is."""
        hit = self.nearest(p)
        return hit[1] if hit is not None else None

    def country_at(self, p: LatLon) -> str | None:
        """The town's country; with no town within 60 km, Russia inside the old box (Crimea included)."""
        hit = self.nearest(p)
        if hit is not None:
            return hit[1]
        return RUSSIA if in_russia(p) else None

    def nearest_of(self, p: LatLon, country: str, max_km: float) -> Town | None:
        """The nearest town of one country within `max_km`."""
        if country == RUSSIA:
            hit = self.russian.nearest(p, max_km)
            return hit[1] if hit is not None else None
        best = None
        for d, (code, t) in self.abroad.within(p, max_km):
            if code == country:
                best = (d, t)
                break
        return best[1] if best is not None else None


__all__ = ["INSIDE_KM", "CountryLocator"]
