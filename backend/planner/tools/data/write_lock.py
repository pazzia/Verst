"""Write `catalogue.lock` (ADR-0012 §1): versions, counts, sizes and sha256 of the packaged catalogue.

python3 tools/data/write_lock.py RAW_DIR OUT_DIR LOCK_PATH
python3 tools/data/write_lock.py abroad ABROAD_DIR LOCK_PATH   # CEO 29.10: merge the per-country locks

Abroad (`data-abroad.yml`) each country job writes `<cc>/lock.json` with the first form and `<cc>/parks.lock.json`
with `build_parks.py --lock`; the publish job merges them into `abroad.lock` (`merge_abroad`) and deletes them.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from verst_planner.catalogue import FILES, load_gz


def lock(raw: Path, out: Path) -> dict[str, object]:
    files = {}
    for name in FILES.values():
        data = (out / name).read_bytes()
        files[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    meta = load_gz((out / FILES["meta"]).read_bytes(), "meta")
    counts = {k: load_gz((out / FILES[k]).read_bytes(), k)["n"] for k in ("towns", "pois", "bars", "food")}

    def opt(name: str) -> object:
        p = raw / name
        return json.loads(p.read_text("utf-8")) if p.exists() else None

    return {
        "version": meta["version"],
        "builtAt": meta["builtAt"],
        "counts": {**counts, "links": len(meta["links"]), "credits": len(meta["credits"])},
        "totalBytes": sum(int(f["bytes"]) for f in files.values()),
        "files": files,
        "sources": meta.get("sources", {}),
        "classCheck": opt("class_check.json"),
        "forms": opt("forms_report.json"),
        "failedTowns": {"pois": opt("pois_failed.json"), "bars": opt("bars_failed.json")},
    }


def merge_abroad(root: Path) -> dict[str, object]:
    """{countries: {cc: lock + parks}, totalBytes} over the `<cc>/lock.json` pieces under `root`."""
    countries: dict[str, dict[str, object]] = {}
    total = 0
    for d in sorted(p for p in root.iterdir() if p.is_dir() and (p / "lock.json").exists()):
        doc = json.loads((d / "lock.json").read_text("utf-8"))
        parks = d / "parks.lock.json"
        if parks.exists():
            doc["parks"] = json.loads(parks.read_text("utf-8"))
        total += int(doc["totalBytes"]) + int((doc.get("parks") or {}).get("bytes", 0))
        countries[d.name] = doc
    return {"countries": countries, "totalBytes": total}


if __name__ == "__main__" and sys.argv[1] == "abroad":
    root, path = Path(sys.argv[2]), Path(sys.argv[3])
    path.write_text(json.dumps(merge_abroad(root), ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(path.read_text("utf-8")[:3000])
elif __name__ == "__main__":
    raw, out, path = (Path(a) for a in sys.argv[1:4])
    path.write_text(json.dumps(lock(raw, out), ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(path.read_text("utf-8")[:2000])
