#!/usr/bin/env bash
# The road graph built and published by .github/workflows/routing.yml (publish: true) onto a VM, no GitHub login
# (D-IR-21: built on the 16 GB CI runner, never imported on the VM; served from disk with MMAP and a 1 GB heap).
#
#   sudo infra/routing/fetch_graph.sh                 # → /srv/verst/routing/current (the previous one kept aside)
#   sudo infra/routing/fetch_graph.sh /srv/verst/routing routing-graph-latest
#
# The release holds graph.tar.gz.partNN (≤ 1.9 GB each: GitHub's 2 GB limit per file), SHA256SUMS and build.json.
set -euo pipefail
DIR="${1:-/srv/verst/routing}"
TAG="${2:-routing-graph-latest}"
REL="https://github.com/pazzia/Verst/releases/download/$TAG"
DL="$DIR/download"
mkdir -p "$DL"
curl -fsSL --retry 5 -o "$DL/SHA256SUMS" "$REL/SHA256SUMS"
for f in $(awk '{print $2}' "$DL/SHA256SUMS"); do
  echo "download $f"
  curl -fL --retry 10 --retry-all-errors -C - -o "$DL/$f" "$REL/$f"   # -C -: a broken download resumes
done
(cd "$DL" && sha256sum -c SHA256SUMS)
rm -rf "$DIR/next"
mkdir -p "$DIR/next"
cat "$DL"/graph.tar.gz.part* | tar -xz -C "$DIR/next"
[ -n "$(ls -A "$DIR/next/graph-cache" 2>/dev/null)" ] || { echo "no graph-cache in the download" >&2; exit 1; }
rm -rf "$DL" "$DIR/previous"
if [ -d "$DIR/current" ]; then mv "$DIR/current" "$DIR/previous"; fi
mv "$DIR/next" "$DIR/current"
chown -R 10001 "$DIR/current"   # the image runs as uid 10001 (Dockerfile)
du -sh "$DIR/current/graph-cache"
cat "$DIR/current/build.json"; echo
echo "graph ready in $DIR/current; restart: docker compose ... --profile routing up -d graphhopper"
