"""Wikidata sitelinks for the corridor's places: the notability signal of the open layer (ADR-0015 §2 uses the
same signal). One SPARQL POST per 200 ids; failures leave sitelinks at 0 and are counted in the report."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Iterable

ENDPOINT = "https://query.wikidata.org/sparql"
UA = "VerstSpike01/0.1 (https://github.com/pazzia/Verst; research prototype)"


def sitelinks(qids: Iterable[str], batch: int = 200, pause_s: float = 1.0) -> tuple[dict[str, int], int]:
    ids = sorted({q for q in qids if q and q.startswith("Q") and q[1:].isdigit()})
    out: dict[str, int] = {}
    failed = 0
    for i in range(0, len(ids), batch):
        chunk = ids[i : i + batch]
        query = "SELECT ?item ?sl WHERE { VALUES ?item { %s } ?item wikibase:sitelinks ?sl }" % " ".join(
            f"wd:{q}" for q in chunk
        )
        body = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
        req = urllib.request.Request(
            ENDPOINT, data=body, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            for b in data["results"]["bindings"]:
                out[b["item"]["value"].rsplit("/", 1)[-1]] = int(b["sl"]["value"])
        except Exception:  # noqa: BLE001 - a research run reports failures instead of stopping
            failed += len(chunk)
        time.sleep(pause_s)
    return out, failed
