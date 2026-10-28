"""Writes the mobile API v2 contract examples (ARCH-305, M§5.4) into `docs/contracts/v2/`.

One file per function and case: ``{"request": {"function", "args"}, "response": <envelope>}``. Arguments
named ``*_json`` are passed to the bridge as JSON text; here they are shown parsed. The envelope's ``ms`` is
written as 0 and ``selfcheck``'s ``python`` as `APP_PYTHON` (HYG-01: the host interpreter is environment
data, like ``ms``; it made the file differ between 3.13.16, 3.13.17 and 3.12.3 hosts). Everything runs in-process on the golden clock with both fixture worlds and the packaged
catalogue, so a re-run is byte-identical. ``index.json`` lists the files.

Run from `backend/planner`: ``python3 tools/gen_api_contracts.py``. With ``VERST_GEN_IN_MEMORY=1`` nothing
is written and `GENERATED` (file name → text) holds the output (compared by `test_api_contracts`).
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from verst_planner import mobile  # noqa: E402
from verst_planner.domain.model import LatLon  # noqa: E402

OUT = ROOT.parents[1] / "docs" / "contracts" / "v2"
GENERATED: dict[str, str] = {}
# The app's interpreter line: Chaquopy `version = "3.12"` (android/app/build.gradle.kts), architecture §selfcheck.
APP_PYTHON = "3.12.x"
R = "russia_v1"
FUEL_ID = json.loads((ROOT / "fixtures" / "worlds" / "central_russia_v1.json").read_text("utf-8"))["places"]
FUEL_ID = next(p["id"] for p in FUEL_ID if p["type"] == "fuel")
YAR = {"lat": 57.6261, "lon": 39.8845, "label": "Ярославль, Советская площадь"}
SPB = {"lat": 59.9386, "lon": 30.3141, "label": "Санкт-Петербург, Дворцовая площадь"}


def text(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def call(name, function, refs=None, **args):
    shown = {k: (json.loads(v) if k.endswith("_json") and isinstance(v, str) else v) for k, v in args.items()}
    shown.update(refs or {})
    envelope = json.loads(getattr(mobile, function)(*args.values()))
    envelope["ms"] = 0
    if function == "load_catalogue" and envelope.get("ok"):
        envelope["result"]["ms"] = 0
    if function == "selfcheck" and envelope.get("ok"):
        envelope["result"]["python"] = APP_PYTHON
    GENERATED[f"{name}.json"] = text({"request": {"function": function, "args": shown}, "response": envelope})
    return envelope


def setup():
    for w in ("central_russia_v1", "edge_cases_v1"):
        assert json.loads(mobile.load_world((ROOT / "fixtures" / "worlds" / f"{w}.json").read_text("utf-8")))[
            "ok"
        ]
    mobile.set_clock("golden")


def poi_id(q, near):
    rows = json.loads(mobile.geo_search(R, q, near["lat"], near["lon"], 5, '["poi"]'))["result"]
    return rows[0]["id"]


def town_without_bars():
    """A small catalogue town with no bar within 6 km (the NOT_ENOUGH_POIS example), deterministic."""
    from verst_planner.geo.distance import haversine_km

    cat = mobile._CATALOGUE[0]
    for t in sorted(cat.towns, key=lambda t: (t.population, t.id)):
        if t.population >= 5000 and all(haversine_km(t.point, b.point) > 6 for b in cat.bars):
            return {"lat": t.point.lat, "lon": t.point.lon, "label": t.name}
    raise AssertionError("no town without bars")


def unpriced_sight():
    """ADR-0019 E-2: the first catalogue sight (by id) whose kind has no default ticket and whose OSM data has
    no `fee` — its price is unknown, so the card says «цена билета неизвестна», deterministic."""
    cat = mobile._CATALOGUE[0]
    places = mobile._WORLDS[R].world.places
    return min(p.id for p in cat.pois if p.kind == "attraction" and p.fee is None and p.id in places)


def dry_town_with_sights():
    """A catalogue town with no bar within 6 km where an overview walk works: a beer walk there fails with
    checked suggestions (the NOT_ENOUGH_POIS suggestions example), deterministic."""
    from verst_planner.geo.distance import haversine_km

    cat = mobile._CATALOGUE[0]
    for t in sorted(cat.towns, key=lambda t: (-t.population, t.id)):
        if all(haversine_km(t.point, b.point) > 6 for b in cat.bars):
            start = {"lat": t.point.lat, "lon": t.point.lon, "label": t.name}
            probe = json.loads(mobile.city_route(R, "probe", json.dumps({"start": start, "preset": "overview"})))
            if probe["ok"]:
                return start
    raise AssertionError("no dry town with sights")


def bar_in(near):
    from verst_planner.geo.distance import haversine_km

    cat = mobile._CATALOGUE[0]
    return min(cat.bars, key=lambda b: (haversine_km(b.point, LatLon(near["lat"], near["lon"])), b.id)).id


def trip_input(origin, destination, **extra):
    return json.dumps(
        {"origin": origin, "destination": destination, "crew": {"adults": 2}, "dailyKm": 500, **extra}
    )


setup()
call("load_catalogue", "load_catalogue")
call("selfcheck", "selfcheck")
call("geo_search-city", "geo_search", world=R, q="Санкт", lat=55.7558, lon=37.6173, limit=5, kinds=None)
call(
    "geo_search-poi", "geo_search", world=R, q="Эрми", lat=59.93, lon=30.31, limit=5, kinds='["poi", "place"]'
)
call("geo_nearest", "geo_nearest", world=R, lat=57.6205, lon=39.8730)
call("geo_nearest-outside", "geo_nearest", world=R, lat=48.8566, lon=2.3522)
ekb = {"lat": 56.8389, "lon": 60.6057, "label": "Екатеринбург"}
tyu = {"lat": 57.153, "lon": 65.5343, "label": "Тюмень"}
plan = call(
    "plan-synthetic", "plan", world=R, request_id="c-plan-1", input_json=trip_input(ekb, tyu), listener=None
)
call("estimate-synthetic", "estimate", world=R, request_id="c-est-1", input_json=trip_input(ekb, tyu))
msk = {"lat": 55.7558, "lon": 37.6173, "label": "Москва"}
yar = {"lat": 57.6261, "lon": 39.8845, "label": "Ярославль"}
graph_plan = mobile.plan(R, "c-plan-2", trip_input(msk, yar), None)
# ADR-0011: the CEO's case (fitted) and a «doesn't fit» outcome
CEO = {
    "origin": msk,
    "readyRouteId": "rr_golden_ring",
    "crew": {"adults": 4, "children": 1, "dog": True},
    "dailyKm": 300,
}
call(
    "plan-budget-fit",
    "plan",
    world=R,
    request_id="c-fit-1",
    input_json=json.dumps({**CEO, "budget": 30000}),
    listener=None,
)
call(
    "estimate-budget-fit",
    "estimate",
    world=R,
    request_id="c-fit-2",
    input_json=json.dumps({**CEO, "budget": 30000}),
)
call(
    "plan-no-fit",
    "plan",
    world=R,
    request_id="c-fit-3",
    input_json=json.dumps({**CEO, "budget": 20000}),
    listener=None,
)
call(
    "estimate-no-fit",
    "estimate",
    world=R,
    request_id="c-fit-4",
    input_json=json.dumps({**CEO, "budget": 20000}),
)
# API v3 (ADR-0015 §4): paid street parking at the Moscow Kremlin — `parking` sheet on the stop and its line
call(
    "plan-moscow-parking",
    "plan",
    world=R,
    request_id="c-park-1",
    input_json=trip_input(
        msk, {"lat": 54.1961, "lon": 37.6182, "label": "Тула"}, startAt="2026-10-26T09:00", mood="calm"
    ),
    listener=None,
)
call("city_presets", "city_presets", world=R, lat=YAR["lat"], lon=YAR["lon"])
walk = call(
    "city_route-overview",
    "city_route",
    world=R,
    request_id="c-walk-1",
    input_json=json.dumps({"start": YAR, "preset": "overview", "durationMin": 240, "crew": {"adults": 2}}),
)
call(
    "city_route-museums-spb",
    "city_route",
    world=R,
    request_id="c-walk-2",
    input_json=json.dumps(
        {"start": SPB, "preset": "museums", "durationMin": 360, "crew": {"adults": 2, "children": 1}}
    ),
)
call(
    "city_route-ryumochnye",
    "city_route",
    world=R,
    request_id="c-walk-3",
    # CEO 2026-10-29: «По рюмочным» walks рюмочные only — СПб has them (Ярославль one: NOT_ENOUGH_POIS)
    input_json=json.dumps(
        {"start": SPB, "preset": "ryumochnye", "adultConfirmed": True, "crew": {"adults": 2}}
    ),
)
call(
    "city_route-custom",
    "city_route",
    world=R,
    request_id="c-walk-4",
    input_json=json.dumps(
        {
            "start": YAR,
            "preset": "custom",
            "interests": ["parks", "views", "food"],
            "durationMin": 240,
            "pace": "slow",
        }
    ),
)
call(
    "city_route-shorter",
    "city_route",
    world=R,
    request_id="c-walk-8",
    input_json=json.dumps({"start": YAR, "preset": "museums", "durationMin": 480, "crew": {"adults": 2}}),
)
# P0-01: late in the evening (the Developer's UTC emulator showed 22:45 MSK) → tomorrow at the opening.
mobile.set_clock("2026-10-23T22:45:00+03:00")
call("city_presets-late", "city_presets", world=R, lat=YAR["lat"], lon=YAR["lon"])
call(
    "city_route-tomorrow",
    "city_route",
    world=R,
    request_id="c-walk-9",
    input_json=json.dumps({"start": YAR, "preset": "overview", "durationMin": 240, "crew": {"adults": 2}}),
)
mobile.set_clock("golden")
call(
    "city_route-error-adult",
    "city_route",
    world=R,
    request_id="c-walk-5",
    input_json=json.dumps({"start": YAR, "preset": "beer"}),
)
call(
    "city_route-error-not-enough",
    "city_route",
    world=R,
    request_id="c-walk-6",
    input_json=json.dumps(
        {
            "start": town_without_bars(),
            "preset": "beer",
            "adultConfirmed": True,
        }
    ),
)
# CEO 2026-10-29: the catalogue has no bar data for Фрязино — `reason: no_data`, `noData`, `messageRu` (never «мало
# мест»: we did not load them)
call(
    "city_route-error-no-data",
    "city_route",
    world=R,
    request_id="c-walk-15",
    input_json=json.dumps(
        {"start": {"lat": 55.9606, "lon": 38.0456, "label": "Фрязино"}, "preset": "beer", "adultConfirmed": True}
    ),
)
call(
    "city_route-error-no-city",
    "city_route",
    world=R,
    request_id="c-walk-7",
    input_json=json.dumps({"start": {"lat": 61.5, "lon": 90.0, "label": "тайга"}, "preset": "overview"}),
)


# API v3 (ADR-0015 §6): the group, the dog walk, «без ограничения», crew warnings, checked suggestions
KZN = {"lat": 55.7963, "lon": 49.1088, "label": "Казань, Кремлёвская ул."}
call(
    "city_route-dog-walk",
    "city_route",
    world=R,
    request_id="c-walk-10",
    input_json=json.dumps({"start": KZN, "preset": "dog_walk", "crew": {"adults": 2, "dog": True}}),
)
call(
    "city_route-unlimited",
    "city_route",
    world=R,
    request_id="c-walk-11",
    input_json=json.dumps({"start": KZN, "preset": "overview", "durationMin": None, "crew": {"adults": 2}}),
)
call(
    "city_route-beer-with-child",
    "city_route",
    world=R,
    request_id="c-walk-12",
    input_json=json.dumps(
        {"start": KZN, "preset": "beer", "adultConfirmed": True, "crew": {"adults": 2, "children": 1}}
    ),
)
call(
    "city_route-museums-with-dog",
    "city_route",
    world=R,
    request_id="c-walk-13",
    input_json=json.dumps(
        {"start": KZN, "preset": "museums", "durationMin": 240, "crew": {"adults": 2, "dog": True}}
    ),
)
call(
    "city_route-error-suggestions",
    "city_route",
    world=R,
    request_id="c-walk-14",
    input_json=json.dumps(
        {"start": dry_town_with_sights(), "preset": "beer", "adultConfirmed": True, "durationMin": 240}
    ),
)

call("poi_details-sight", "poi_details", world=R, place_id=poi_id("Эрмитаж", SPB))
call("poi_details-fixture-sight", "poi_details", world=R, place_id="pl_yar_ilya")
call("poi_details-hotel", "poi_details", world=R, place_id="pl_yar_hotel_strelka")
call("poi_details-bar", "poi_details", world=R, place_id=bar_in(YAR))
call("poi_details-not-found", "poi_details", world=R, place_id=FUEL_ID)
# ADR-0019 E-1 / E-2: a card whose opening hours nobody checked, and one whose ticket price is unknown
call("poi_details-hours-unknown", "poi_details", world=R, place_id="pl_yar_strelka")
call("poi_details-ticket-unknown", "poi_details", world=R, place_id=unpriced_sight())
# The Windshield's three ready routes from Москва, each estimated for one crew (G02's: 2 adults + child + dog,
# 40 000 ₽, Saturday 07.11 08:00) on the curated world: the km the screenshot fixture shows next to each ready
# route (never a free trip's km, never the template's kmTotal)
for slug, rid in (
    ("tula", "rr_tula_yasnaya"),
    ("yaroslavl", "rr_yaroslavl"),
    ("golden-ring", "rr_golden_ring"),
):
    call(
        f"estimate-ready-{slug}",
        "estimate",
        world="central_russia_v1",
        request_id=f"c-rr-{slug}",
        input_json=json.dumps(
            {
                "origin": msk,
                "readyRouteId": rid,
                "crew": {"adults": 2, "children": 1, "dog": True},
                "dailyKm": 300,
                "budget": 40000,
                "startAt": "2026-11-07T08:00",
            },
            ensure_ascii=False,
        ),
    )
trip = json.loads(graph_plan)["result"]["trip"]
first_sight = next(s["id"] for d in trip["daysList"] for s in d["stops"] if s["kind"] == "sight")
TRIP_REF = {
    "route_json": {"$ref": "result.trip of plan(russia_v1, Москва → Ярославль, 2 adults, 500 km/day)"}
}
call(
    "handoff-car-day",
    "handoff",
    refs=TRIP_REF,
    world=R,
    route_json=json.dumps(trip, ensure_ascii=False),
    options_json=json.dumps({"mode": "car", "day": 1, "fromHere": True}),
)
call(
    "handoff-car-from-stop",
    "handoff",
    refs=TRIP_REF,
    world=R,
    route_json=json.dumps(trip, ensure_ascii=False),
    options_json=json.dumps({"mode": "car", "fromStopId": first_sight, "fromHere": False}),
)
call(
    "handoff-walk",
    "handoff",
    refs={"route_json": {"$ref": "result of city_route-overview.json"}},
    world=R,
    route_json=json.dumps(walk["result"], ensure_ascii=False),
    options_json=json.dumps({"mode": "walk", "fromHere": False}),
)
assert plan["ok"], plan

GENERATED["index.json"] = text({"apiVersion": mobile.API_VERSION, "files": sorted(GENERATED)})

if not os.environ.get("VERST_GEN_IN_MEMORY"):
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.iterdir():
        if old.name not in GENERATED:
            old.unlink()
    for name, body in GENERATED.items():
        (OUT / name).write_text(body, "utf-8")
    print(f"{len(GENERATED)} files, {sum(len(v.encode()) for v in GENERATED.values())} bytes")
