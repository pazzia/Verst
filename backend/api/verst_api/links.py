"""Partner link builder, stub until LEG-02 (ADR-0020 §2): a plain Yandex Travel city search for the hotel's
town with the stay dates and the crew, never an affiliate link (`affiliate: false`, no marker, no wrapper).
The wrapper of architecture §10.7 lands with ENG-03, after LEG-02 (legal entity, Travelpayouts account,
38-FZ labelling)."""

from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlencode

YANDEX_TRAVEL_SEARCH = "https://travel.yandex.ru/hotels/search/"
PARTNER = "yandex_travel"


def hotel_search_url(town: str, checkin: date, nights: int, adults: int, children_ages: list[int]) -> str:
    query = {
        "text": town,
        "checkinDate": checkin.isoformat(),
        "checkoutDate": (checkin + timedelta(days=nights)).isoformat(),
        "adults": str(adults),
    }
    if children_ages:
        query["childrenAges"] = ",".join(str(a) for a in children_ages)
    return YANDEX_TRAVEL_SEARCH + "?" + urlencode(query)
