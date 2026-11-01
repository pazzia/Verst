#!/usr/bin/env bash
# A Geofabrik extract in 8 ranged parts in parallel, glued and checked against the published md5 (read before
# and after, so a mid-download update of *-latest fails here instead of giving a broken extract). One
# connection got ~1 MB/s at night and timed out on russia-latest (data-abroad run 2, 30.10).
#   tools/ci/fetch_pbf.sh https://download.geofabrik.de/russia-latest.osm.pbf "$RUNNER_TEMP/ru.osm.pbf"
set -euo pipefail
URL="$1"
OUT="$2"
UA="${UA:-VerstDataBot/0.3 (+https://github.com/pazzia/Verst; data pipeline)}"
N="${PARTS:-8}"
MD5=$(curl -fsSL --retry 3 -A "$UA" "$URL.md5" | cut -d' ' -f1)
LEN=$(curl -fsSIL --retry 3 -A "$UA" "$URL" | tr -d '\r' | awk 'tolower($1)=="content-length:"{n=$2} END{print n}')
echo "$(basename "$URL"): $LEN bytes, md5 $MD5"
P=$(( (LEN + N - 1) / N ))
pids=()
for i in $(seq 0 $((N - 1))); do
  S=$((i * P)); E=$((S + P - 1)); [ "$E" -ge "$LEN" ] && E=$((LEN - 1))
  curl -fsSL --retry 5 --retry-all-errors -A "$UA" -r "$S-$E" -o "$OUT.part$i" "$URL" &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p"; done
for i in $(seq 0 $((N - 1))); do cat "$OUT.part$i"; rm -f "$OUT.part$i"; done > "$OUT"
echo "$MD5  $OUT" | md5sum -c -
[ "$(curl -fsSL --retry 3 -A "$UA" "$URL.md5" | cut -d' ' -f1)" = "$MD5" ]
