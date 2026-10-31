# S4 investigation: reproduces the Фрязино «Свой маршрут» walks on the real engine (see s4-walk-filters.md).
# Run from the repo root: python3 -I docs/bugs/s4-walk-filters-repro.py
import json, sys, glob, os  # noqa: E401
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend", "planner"))
from verst_planner import mobile as m
root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# the app loads the fixture worlds from assets, then the catalogue
for f in sorted(glob.glob(root + "/android/app/src/main/assets/worlds/*.json")) or sorted(glob.glob(root + "/backend/planner/fixtures/worlds/*.json")):
    r = json.loads(m.load_world(open(f, encoding="utf-8").read())); print("world", os.path.basename(f), r["ok"])
print("catalogue", json.loads(m.load_catalogue())["ok"])
m.set_clock("2026-10-25T11:00:00+03:00")
start = {"lat": 55.9606, "lon": 38.0456, "label": "Фрязино, проезд Павла Блинова, 8"}
p = json.loads(m.city_presets("russia_v1", start["lat"], start["lon"]))
print("presets", json.dumps(p, ensure_ascii=False)[:700])
def walk(**kw):
    inp = dict(start=start, preset="custom", interests=["history", "architecture"], durationMin=240, pace="normal",
               returnToStart=True, crew={"adults": 2, "children": 0})
    inp.update(kw)
    r = json.loads(m.city_route("russia_v1", "x", json.dumps(inp, ensure_ascii=False)))
    if not r["ok"]:
        return None, r["error"]
    w = r["result"]
    return w, [(s.get("poiId"), s["nameRu"]) for s in w["stops"]]
w, stops = walk(); print("base", stops if w else stops)
exclude = [pid for pid, _ in stops if pid] if w else []  # «Другой вариант» = the same walk without these
for i in range(1, 9):
    w, stops = walk(exclude=exclude)
    if w is None:
        print(f"other #{i}: ERROR {stops}"); break
    print(f"other #{i}: {len(stops)} stops {[n for _, n in stops]} dur={w['durationMin']} shorter={w.get('shorter')}")
    exclude += [pid for pid, _ in stops if pid]
for kw in [dict(interests=["parks"]), dict(interests=["views"]), dict(interests=["history"]), dict(interests=["architecture"]), dict(interests=["food","parks"]), dict(durationMin=120), dict(durationMin=480), dict(pace="slow"), dict(pace="fast"), dict(returnToStart=False)]:
    w, stops = walk(**kw)
    print("filter", kw, "->", [n for _, n in stops] if w else stops, (w or {}).get("durationMin"))
