#!/usr/bin/env bash
# Record the adapter's unit-test fixtures from a REAL GraphHopper server on the synthetic mini map
# (make_mini_osm.py). Needs Java >= 17 and the pinned graphhopper-web jar; no internet, no OSM extract.
#
#   infra/routing/dev/record_fixtures.sh /path/to/graphhopper-web-11.0.jar [OUT_DIR]
#
# OUT_DIR defaults to backend/planner/tests/data/graphhopper. Each file is {"_meta", "request", "status", "body"}:
# `body` is the server's response byte-for-byte parsed as JSON. CI (.github/workflows/routing.yml) records the
# same request shapes on the real Central + Volga extract; after review they are added next to these, under
# tests/data/graphhopper/real/ (these stay: a real extract cannot reproduce every error case).
set -euo pipefail

JAR=${1:?usage: record_fixtures.sh GRAPHHOPPER_JAR [OUT_DIR]}
JAR=$(realpath "$JAR")
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
OUT=$(realpath -m "${2:-$ROOT/backend/planner/tests/data/graphhopper}")
PORT=${PORT:-8989}
WORK=$(mktemp -d)
trap 'kill "$(cat "$WORK/pid" 2>/dev/null)" 2>/dev/null || true; rm -rf "$WORK"' EXIT

# Keep the 6-edge island (upstream drops components under 200 edges). A -Ddw override does not reach this key:
# Dropwizard splits it at the dot while config.yml holds it flat, so the copy is edited instead.
sed 's/^  prepare.min_network_size: 200$/  prepare.min_network_size: 0/' "$HERE/../config.yml" > "$WORK/config.yml"
grep -q '^  prepare.min_network_size: 0$' "$WORK/config.yml"
cp -r "$HERE/../custom_models" "$WORK/"
python3 "$HERE/make_mini_osm.py" "$WORK/mini.osm"
cd "$WORK"
OPTS=(-Xmx512m
  -Ddw.graphhopper.datareader.file=mini.osm
  "-Ddw.server.application_connectors[0].bind_host=127.0.0.1"
  "-Ddw.server.application_connectors[0].port=$PORT"
  "-Ddw.server.admin_connectors[0].bind_host=127.0.0.1"
  "-Ddw.server.admin_connectors[0].port=$((PORT + 1))")
java "${OPTS[@]}" -jar "$JAR" import config.yml > import.log 2>&1
java "${OPTS[@]}" -jar "$JAR" server config.yml > server.log 2>&1 &
echo $! > pid
for _ in $(seq 1 60); do curl -fs "http://127.0.0.1:$PORT/health" > /dev/null && break; sleep 1; done
curl -fs "http://127.0.0.1:$PORT/health" > /dev/null || { tail -50 server.log; exit 1; }
VERSION=$(curl -fs "http://127.0.0.1:$PORT/info" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')

mkdir -p "$OUT"
# The request body is built by the adapter itself (verst_planner.adapters.graphhopper.request_body), so the
# fixtures always match what GraphHopperRouting sends.
record() {  # name, profile, points-json, note
  PYTHONPATH="$ROOT/backend/planner" python3 - "$OUT/$1.json" "$2" "$3" "$4" "$VERSION" "http://127.0.0.1:$PORT/route" <<'PY'
import json, sys, urllib.error, urllib.request
from verst_planner.adapters.graphhopper import request_body
from verst_planner.domain.model import LatLon
out, profile, points, note, version, url = sys.argv[1:7]
req = request_body([LatLon(lat, lon) for lon, lat in json.loads(points)], profile)
r = urllib.request.Request(url, json.dumps(req).encode(), {"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(r, timeout=10) as resp:
        status, body = resp.status, resp.read()
except urllib.error.HTTPError as e:
    status, body = e.code, e.read()
doc = {"_meta": {"source": f"GraphHopper {version} server, synthetic mini map (infra/routing/dev/make_mini_osm.py)",
                 "recordedBy": "infra/routing/dev/record_fixtures.sh", "note": note,
                 "schema": "https://github.com/graphhopper/graphhopper/blob/11.0/docs/web/api-doc.md",
                 "replaceWith": "real Russia responses from .github/workflows/routing.yml (artifact routing-recordings)"},
       "request": req, "status": status, "body": json.loads(body)}
with open(out, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)
    f.write("\n")
print(f"{out}: HTTP {status}")
PY
}
W='[37.0,56.0]'; E='[37.3,56.0]'; S='[37.15,55.95]'
record route_toll car "[$W,$E]" "W -> E on the toll motorway М-11"
record route_avoid_tolls car_avoid_tolls "[$W,$E]" "W -> E avoiding tolls: trunk М-10 with refs 'М-10;Е105' and Latin 'M-10'"
record route_via car "[$W,$S,$E]" "W -> village S (via, Р-132 out and back) -> E"
record route_snap_far car "[$W,[37.10,55.975]]" "point 2 is 1.1 km south of М-10: snapped, within 2 km"
record route_snap_too_far car "[$W,[37.10,55.962]]" "point 2 is 2.55 km south of М-10: GraphHopper snaps (index.max_region_search 8), the adapter must refuse"
record error_point_not_found car "[$W,[37.25,56.05]]" "inside the bbox, but no road within GraphHopper's search radius"
record error_out_of_bounds car "[$W,[38.5,56.0]]" "outside the graph's bbox"
record error_connection_not_found car "[$W,[37.145,56.0501]]" "the island: snapped, but no connection"
record error_unknown_profile bus "[$W,$E]" "a profile the server does not have (configuration error)"
# ConnectionNotFound on a 3-point request: the adapter re-routes the legs to find the unreachable point.
I='[37.145,56.0501]'
record error_connection_not_found_via car "[$W,$S,$I]" "W -> S -> the island: no connection, leg unknown"
record leg_w_s car "[$W,$S]" "leg 1 of the request above: fine"
record leg_s_island car "[$S,$I]" "leg 2 of the request above: no connection"
