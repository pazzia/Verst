"""Apply `curated_wikidata.tsv` to the shipped catalogue without a full rebuild (CEO 04.11, photos):

    python3 tools/data/apply_curated_links.py

Only `catalogue_meta.json.gz` changes: each reviewed fixture sight gets its Wikidata link and Commons photo,
and the photo's credit is appended to `credits` (or reused when the same author, licence and URL are already
there). `catalogue.lock` gets the new meta size, sha256 and counts. A later `build_catalogue.py` run reads the
same table (`curated_links`), so a rebuild keeps these links.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from build_catalogue import clean_author, curated_links, gfdl_only  # noqa: E402

from verst_planner.catalogue import FILES, dump_gz, load_gz  # noqa: E402

RES = HERE.parents[1] / "verst_planner" / "resources"
LOCK = HERE / "catalogue.lock"


def apply(meta: dict[str, Any], links: dict[str, dict[str, Any]]) -> list[str]:
    """Pure: set the links in `meta` (in place); returns the fixture ids changed."""
    credits: list[dict[str, Any]] = meta["credits"]
    index = {(c["author"], c["licence"], c["url"]): i for i, c in enumerate(credits)}
    changed = []
    for fid, link in sorted(links.items()):
        c = link["credit"]
        if gfdl_only(c["licence"]):
            raise ValueError(f"{fid}: GFDL-only photo {link['image']} (R-10)")
        author = clean_author(c["author"]) if c["author"] else None
        key = (author, c["licence"], c["url"])
        if key not in index:
            index[key] = len(credits)
            credits.append({"author": author, "licence": c["licence"], "url": c["url"]})
        new = {"wikidata": link["wikidata"], "image": link["image"], "credit": index[key]}
        if meta["links"].get(fid) != new:
            meta["links"][fid] = new
            changed.append(fid)
    meta["links"] = dict(sorted(meta["links"].items()))
    return changed


def main() -> int:
    path = RES / FILES["meta"]
    meta = load_gz(path.read_bytes(), "meta")
    changed = apply(meta, curated_links())
    data = dump_gz(meta)
    path.write_bytes(data)
    lock = json.loads(LOCK.read_text("utf-8"))
    lock["files"][FILES["meta"]] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    lock["counts"]["links"] = len(meta["links"])
    lock["counts"]["credits"] = len(meta["credits"])
    lock["totalBytes"] = sum(int(f["bytes"]) for f in lock["files"].values())
    LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"links changed: {len(changed)} ({', '.join(changed)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
