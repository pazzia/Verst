"""Check that the catalogue's Commons photos resolve (Manager, Sprint 3 data round). CI only:

    python3 tools/data/check_photos.py CATALOGUE_DIR REPORT_JSON [--n 50] [--seed RUN_ID]

Samples `n` image file names from the built catalogue (towns, POIs and fixture links), requests each one's
`Special:FilePath` URL exactly as the app builds it (`catalogue.photos.image_urls`) and, for comparison, at the
standard Wikimedia thumbnail widths, and fails (exit 1) when fewer than 95 % of the app's card URLs resolve to an
image. `sample` and `summary` are pure and tested in the sandbox.
"""

from __future__ import annotations

import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fetch_commons_meta import files_of
from http_util import USER_AGENT

from verst_planner.catalogue.photos import CARD_WIDTH, THUMB_WIDTH, thumb_url

THRESHOLD = 0.95
# The app's widths first; 500 and 960 are standard Wikimedia thumbnail steps, measured to choose a fallback.
WIDTHS = (CARD_WIDTH, THUMB_WIDTH, 500, 960)
GAP_S = 0.5


def sample(names: list[str], n: int, seed: str) -> list[str]:
    pool = sorted(set(names))
    if len(pool) <= n:
        return pool
    return sorted(random.Random(seed).sample(pool, n))


def resolve(url: str, timeout: float = 30.0) -> tuple[bool, str]:
    """GET the first byte; ok when the final response is 2xx with an image content type."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ctype = resp.headers.get("Content-Type", "")
                resp.read(1)
                return ctype.startswith("image/"), f"{resp.status} {ctype}"
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(5.0 * 2**attempt)
                continue
            return False, f"HTTP {e.code}"
        except Exception as e:  # reported per URL
            if attempt < 2:
                time.sleep(2.0)
                continue
            return False, repr(e)[:120]
    return False, "retries"


def summary(results: dict[int, list[tuple[str, bool, str]]], total_images: int) -> dict[str, Any]:
    rates = {str(w): (sum(ok for _f, ok, _s in r) / len(r) if r else 1.0) for w, r in results.items()}
    card = results.get(CARD_WIDTH, [])
    return {
        "imagesInCatalogue": total_images,
        "sampled": len(card),
        "rates": rates,
        "threshold": THRESHOLD,
        "ok": rates.get(str(CARD_WIDTH), 1.0) >= THRESHOLD,
        "failures": {str(w): [{"file": f, "status": s} for f, ok, s in r if not ok] for w, r in results.items()},
    }


def main(argv: list[str]) -> int:
    cat_dir, report = Path(argv[0]), Path(argv[1])
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 50
    seed = argv[argv.index("--seed") + 1] if "--seed" in argv else "0"
    names = files_of(cat_dir)
    picked = sample(names, n, seed)
    results: dict[int, list[tuple[str, bool, str]]] = {}
    for w in WIDTHS:
        rows = []
        for f in picked:
            time.sleep(GAP_S)
            ok, status = resolve(thumb_url(f, w))
            rows.append((f, ok, status))
        results[w] = rows
        print(f"photos width={w}: {sum(ok for _f, ok, _s in rows)}/{len(rows)}", flush=True)
    doc = summary(results, len(names))
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(doc["rates"]))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
