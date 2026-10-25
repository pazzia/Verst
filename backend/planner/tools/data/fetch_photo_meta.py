"""Size, MIME type and categories of the catalogue's Commons files, to choose the area photos (5.9 §3). CI only:

    python3 tools/data/fetch_photo_meta.py RAW_DIR CATALOGUE_DIR   # writes RAW_DIR/photo_meta.json

`{file: {"w": width, "h": height, "mime": "image/jpeg", "cats": [category, …]}}`. `pages_meta` is pure and
tested in the sandbox; `build_catalogue.area_ok` applies the rule.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fetch_commons_meta import API, BATCH, files_of
from http_util import Pacer, request


def pages_meta(pages: list[dict[str, Any]], into: dict[str, dict[str, Any]]) -> None:
    """Merge one API response's pages (categories may arrive over several continuation responses)."""
    for p in pages:
        title = str(p.get("title", ""))
        if not title.startswith("File:"):
            continue
        rec = into.setdefault(title[len("File:") :], {"w": None, "h": None, "mime": None, "cats": []})
        info = (p.get("imageinfo") or [None])[0]
        if info:
            rec["w"], rec["h"], rec["mime"] = info.get("width"), info.get("height"), info.get("mime")
        for c in p.get("categories") or []:
            name = str(c.get("title", "")).removeprefix("Category:")
            if name and name not in rec["cats"]:
                rec["cats"].append(name)


def main(argv: list[str]) -> int:
    raw, cat_dir = Path(argv[0]), Path(argv[1])
    files = files_of(cat_dir)
    pacer = Pacer(1.0)
    meta: dict[str, dict[str, Any]] = {}
    for i in range(0, len(files), BATCH):
        batch = files[i : i + BATCH]
        params: dict[str, str] = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "imageinfo|categories",
            "iiprop": "size|mime",
            "cllimit": "max",
            "titles": "|".join("File:" + f for f in batch),
        }
        got: dict[str, dict[str, Any]] = {}
        normalized: dict[str, str] = {}
        while True:
            doc = request(API, pacer, data=params)
            q = doc.get("query", {})
            normalized.update({n["to"]: n["from"] for n in q.get("normalized", [])})
            pages_meta(q.get("pages", []), got)
            cont = doc.get("continue")
            if not cont:
                break
            params = {**params, **{k: str(v) for k, v in cont.items()}}
        for name, rec in got.items():
            original = normalized.get("File:" + name, "File:" + name)[len("File:") :]
            meta[original] = rec
        if (i // BATCH) % 20 == 0:
            print(f"photo meta: {i + len(batch)}/{len(files)}", flush=True)
    (raw / "photo_meta.json").write_text(json.dumps(meta, ensure_ascii=False), "utf-8")
    print(f"photo meta: {len(meta)} of {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
