"""Fetch author/licence of the Commons files the catalogue selected (ADR-0012 §1, §6). CI only:

    python3 tools/data/fetch_commons_meta.py RAW_DIR CATALOGUE_DIR   # writes RAW_DIR/credits.json

The catalogue directory is a first build without credits; its towns, POIs and links name the files.
`files_of` and `credits_from_pages` are pure and tested in the sandbox.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from http_util import Pacer, request

from verst_planner.catalogue import FILES, POI_COLS, TOWN_COLS, decode_table, load_gz

API = "https://commons.wikimedia.org/w/api.php"
BATCH = 50
TAG = re.compile(r"<[^>]+>")
NON_FREE = ("fair use", "non-free")


def files_of(cat_dir: Path) -> list[str]:
    meta = load_gz((cat_dir / FILES["meta"]).read_bytes(), "meta")
    towns = decode_table(load_gz((cat_dir / FILES["towns"]).read_bytes(), "towns"), TOWN_COLS, "towns")
    pois = decode_table(load_gz((cat_dir / FILES["pois"]).read_bytes(), "pois"), POI_COLS, "pois")
    names = {r["image"] for r in towns + pois if r["image"]}
    names |= {v["image"] for v in meta.get("links", {}).values() if v.get("image")}
    return sorted(names)


def _meta(ext: dict[str, Any], key: str) -> str | None:
    v = ext.get(key, {}).get("value")
    if v is None:
        return None
    text = TAG.sub("", str(v)).strip()
    return text or None


def credits_from_pages(pages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for p in pages:
        title = str(p.get("title", ""))
        if not title.startswith("File:"):
            continue
        info = (p.get("imageinfo") or [{}])[0]
        ext = info.get("extmetadata") or {}
        licence = _meta(ext, "LicenseShortName")
        non_free = (_meta(ext, "NonFree") or "").lower() == "true"
        free = licence is not None and not non_free and not any(x in licence.lower() for x in NON_FREE)
        out[title[len("File:") :]] = {
            "author": _meta(ext, "Artist"),
            "licence": licence,
            "url": _meta(ext, "LicenseUrl"),
            "free": free,
        }
    return out


def main(argv: list[str]) -> int:
    raw, cat_dir = Path(argv[0]), Path(argv[1])
    files = files_of(cat_dir)
    pacer = Pacer(1.0)
    credits: dict[str, dict[str, Any]] = {}
    for i in range(0, len(files), BATCH):
        titles = "|".join("File:" + f for f in files[i : i + BATCH])
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "imageinfo",
            "iiprop": "extmetadata",
            "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|NonFree",
            "titles": titles,
        }
        doc = request(API, pacer, data=params)
        pages = doc.get("query", {}).get("pages", [])
        normalized = {n["to"]: n["from"] for n in doc.get("query", {}).get("normalized", [])}
        for name, c in credits_from_pages(pages).items():
            original = normalized.get("File:" + name, "File:" + name)[len("File:") :]
            credits[original] = c
        if (i // BATCH) % 20 == 0:
            print(f"credits: {i + BATCH}/{len(files)}", flush=True)
    (raw / "credits.json").write_text(json.dumps(credits, ensure_ascii=False), "utf-8")
    print(f"credits: {len(credits)} of {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
