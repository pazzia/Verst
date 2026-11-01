#!/usr/bin/env bash
# Download a Russian OSM extract from Geofabrik and build the GraphHopper graph (ADR-0017). Used by
# .github/workflows/routing.yml and, unchanged, on the future routing VM (README.md "Weekly rebuild").
#
#   infra/routing/build_graph.sh REGION DATA_DIR JAR [XMX]
#
#   REGION   central+volga  Central + Volga federal districts, merged (Moscow, Golden Ring, Nizhny, Kazan)
#            central        Central federal district only (no Kazan)
#            russia         the whole country (4.2 GB PBF on 2026-10-25, ADR-0012 as-built)
#   DATA_DIR gets osm/region.osm.pbf, graph-cache/ and build.json (what was built from what)
#   JAR      graphhopper-web-<version>.jar (README.md "Pinned versions")
#   XMX      import heap, default 10g (README.md "Sizing")
#
# Needs: curl, java >= 17, osmium-tool (only for central+volga), python3.
set -euo pipefail

REGION=${1:?usage: build_graph.sh REGION DATA_DIR JAR [XMX]}
DATA=$(realpath -m "${2:?DATA_DIR}")
JAR=$(realpath "${3:?JAR}")
XMX=${4:-10g}
HERE=$(cd "$(dirname "$0")" && pwd)
BASE=https://download.geofabrik.de/russia
case "$REGION" in
  central+volga) PARTS=(central-fed-district volga-fed-district) ;;
  central) PARTS=(central-fed-district) ;;
  russia) PARTS=(); URL_RUSSIA=https://download.geofabrik.de/russia-latest.osm.pbf ;;
  *) echo "unknown region $REGION" >&2; exit 2 ;;
esac

mkdir -p "$DATA/osm"
fetch() {  # url, out
  echo "download $1"
  if [ -n "${FETCH_PBF:-}" ]; then  # CI: tools/ci/fetch_pbf.sh, 8 ranged parts + md5 (one connection timed out, 30.10)
    "$FETCH_PBF" "$1" "$2.part"
  else
    curl -fL --retry 5 --retry-delay 20 --retry-all-errors -o "$2.part" "$1"
  fi
  mv "$2.part" "$2"
}
timestamp() {  # the replication timestamp in the PBF header (osmium-fileinfo(1)), "unknown" without osmium
  local t
  t=$(osmium fileinfo -g header.option.osmosis_replication_timestamp "$1" 2>/dev/null || true)
  echo "${t:-unknown}"
}

PBF="$DATA/osm/region.osm.pbf"
if [ "$REGION" = russia ]; then
  fetch "$URL_RUSSIA" "$PBF"
elif [ ${#PARTS[@]} -eq 1 ]; then
  fetch "$BASE/${PARTS[0]}-latest.osm.pbf" "$PBF"
else
  files=()
  for p in "${PARTS[@]}"; do
    fetch "$BASE/$p-latest.osm.pbf" "$DATA/osm/$p.osm.pbf"
    files+=("$DATA/osm/$p.osm.pbf")
  done
  # osmium merge de-duplicates the border objects both extracts contain, but only for snapshots of the same
  # moment ("Don't use this command to merge non-history files with data from different points in time",
  # osmium-merge(1)). Geofabrik builds all Russian sub-regions from one daily state, so compare the headers.
  stamps=$(for f in "${files[@]}"; do timestamp "$f"; done | sort -u)
  if [ "$(echo "$stamps" | wc -l)" -ne 1 ] || [ "$stamps" = unknown ]; then
    echo "extracts are from different replication timestamps: $stamps (re-run later)" >&2
    exit 3
  fi
  osmium merge "${files[@]}" -o "$PBF" --overwrite
  rm -f "${files[@]}"
fi
ls -l "$PBF"

# Import + CH preparation in one JVM that exits when done (`import` frees import-only memory early and
# ParallelGC lowers the import peak: graphhopper docs/core/deploy.md). Only datareader.file and graph.location are
# overridden with -Ddw: both are verified to take effect; edit config.yml for anything else.
rm -rf "$DATA/graph-cache"
cd "$HERE"
start=$(date +%s)
java "-Xmx$XMX" "-Xms$XMX" -XX:+UseParallelGC \
  "-Ddw.graphhopper.datareader.file=$PBF" "-Ddw.graphhopper.graph.location=$DATA/graph-cache" \
  -jar "$JAR" import config.yml 2>&1 | tee "$DATA/import.log" | grep -E "WARN|ERROR|took|flushed|nodes:" || true
test -f "$DATA/graph-cache/properties.txt" || { echo "import failed, see $DATA/import.log" >&2; exit 4; }
secs=$(( $(date +%s) - start ))

python3 - "$DATA" "$REGION" "$JAR" "$XMX" "$secs" "$(timestamp "$PBF")" <<'PY'
import json, os, sys
data, region, jar, xmx, secs, stamp = sys.argv[1:7]
def size(p):
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs) if os.path.isdir(p) else os.path.getsize(p)
out = {"region": region, "osmTimestamp": stamp, "jar": os.path.basename(jar), "importXmx": xmx,
       "importSeconds": int(secs), "pbfBytes": size(os.path.join(data, "osm", "region.osm.pbf")),
       "graphBytes": size(os.path.join(data, "graph-cache"))}
with open(os.path.join(data, "build.json"), "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out))
PY
