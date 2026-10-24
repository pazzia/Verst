"""The offline open-data catalogue (ADR-0012 §3): Russian towns, POIs (Wikidata) and bars (OSM).

The files are columnar gzip JSON in `verst_planner/resources/` (``catalogue_*.json.gz``), written by
`backend/planner/tools/data/build_catalogue.py` in CI and read here with the zip-safe resource loader.
A table document is ``{"v": 1, "n": N, "cols": {"name": [v0, v1, …], …}}``; coordinates are integers in
1e-5 degrees. This module is the single definition of the format: the builder imports `encode_table`,
`dump_gz` and the column lists from here, so writer and reader cannot drift.
"""

from __future__ import annotations

import gzip
import io
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from verst_planner import resources
from verst_planner.domain.model import LatLon, RegionInfo

FORMAT_VERSION = 1
COORD_SCALE = 100_000

POI_KINDS = (
    "museum",
    "kremlin",
    "monastery",
    "church",
    "monument",
    "park",
    "viewpoint",
    "embankment",
    "square",
    "attraction",
)
BAR_KINDS = ("ryumochnaya", "pub", "craft", "bar")

TOWN_COLS = ("id", "name", "gen", "prep", "lat", "lon", "pop", "region", "image", "credit")
POI_COLS = ("id", "name", "desc", "kind", "lat", "lon", "town", "sitelinks", "heritage", "image", "credit")
BAR_COLS = ("id", "name", "kind", "lat", "lon", "town", "hours")

FILES = {
    "meta": "catalogue_meta.json.gz",
    "towns": "catalogue_towns.json.gz",
    "pois": "catalogue_pois.json.gz",
    "bars": "catalogue_bars.json.gz",
}


class CatalogueError(Exception):
    """Missing or malformed catalogue resources (`NO_CATALOGUE` at the bridge)."""


@dataclass(frozen=True, slots=True)
class Credit:
    author: str | None
    licence: str | None
    url: str | None


@dataclass(frozen=True, slots=True)
class CatTown:
    id: str
    name: str
    gen: str | None
    prep: str | None
    point: LatLon
    population: int
    region: str
    image: str | None
    credit: int | None


@dataclass(frozen=True, slots=True)
class CatPoi:
    id: str
    name: str
    desc: str | None
    kind: str
    point: LatLon
    town: str
    sitelinks: int
    heritage: bool
    image: str | None
    credit: int | None


@dataclass(frozen=True, slots=True)
class CatBar:
    id: str
    name: str
    kind: str
    point: LatLon
    town: str
    hours: str | None


@dataclass(frozen=True, slots=True)
class FixtureLink:
    """A fixture town/place matched to Wikidata in CI (id, image, credit index)."""

    wikidata: str
    image: str | None
    credit: int | None


@dataclass(slots=True)
class Catalogue:
    version: str
    built_at: str
    regions: dict[str, RegionInfo]
    towns: list[CatTown]
    pois: list[CatPoi]
    bars: list[CatBar]
    credits: list[Credit]
    links: dict[str, FixtureLink]
    sources: dict[str, Any] = field(default_factory=dict)
    town_by_id: dict[str, CatTown] = field(default_factory=dict)
    poi_by_id: dict[str, CatPoi] = field(default_factory=dict)
    bar_by_id: dict[str, CatBar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.town_by_id = {t.id: t for t in self.towns}
        self.poi_by_id = {p.id: p for p in self.pois}
        self.bar_by_id = {b.id: b for b in self.bars}

    def credit(self, idx: int | None) -> Credit | None:
        if idx is None or not 0 <= idx < len(self.credits):
            return None
        return self.credits[idx]

    def info(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "builtAt": self.built_at,
            "towns": len(self.towns),
            "pois": len(self.pois),
            "bars": len(self.bars),
        }


# ------------------------------------------------------------------------------------------- format


def encode_table(rows: Sequence[dict[str, Any]], cols: Sequence[str]) -> dict[str, Any]:
    """Rows → the columnar document (missing keys become null)."""
    return {"v": FORMAT_VERSION, "n": len(rows), "cols": {c: [r.get(c) for r in rows] for c in cols}}


def columns(doc: Any, cols: Sequence[str], name: str) -> list[list[Any]]:
    """The validated columns of a table document, in `cols` order (no per-row dicts)."""
    decode_table(doc, (), name)
    out = []
    for c in cols:
        col = doc["cols"].get(c)
        if not isinstance(col, list) or len(col) != doc["n"]:
            raise CatalogueError(f"{name}: column {c!r} missing or of the wrong length")
        out.append(col)
    return out


def decode_table(doc: Any, cols: Sequence[str], name: str) -> list[dict[str, Any]]:
    if not isinstance(doc, dict) or doc.get("v") != FORMAT_VERSION:
        raise CatalogueError(f"{name}: unsupported format {doc.get('v') if isinstance(doc, dict) else doc!r}")
    n = doc.get("n")
    columns = doc.get("cols")
    if not isinstance(n, int) or not isinstance(columns, dict):
        raise CatalogueError(f"{name}: bad table header")
    for c in cols:
        col = columns.get(c)
        if not isinstance(col, list) or len(col) != n:
            raise CatalogueError(f"{name}: column {c!r} missing or of the wrong length")
    return [{c: columns[c][i] for c in cols} for i in range(n)]


def dump_gz(doc: Any) -> bytes:
    """Compact JSON, gzip level 9 with a zero mtime and no file name (byte-identical re-runs)."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, compresslevel=9, mtime=0) as f:
        f.write((json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    return buf.getvalue()


def load_gz(data: bytes, name: str) -> Any:
    try:
        return json.loads(gzip.decompress(data).decode("utf-8"))
    except (OSError, EOFError, ValueError) as e:
        raise CatalogueError(f"{name}: unreadable ({e})") from e


def coord(v: Any) -> float:
    return int(v) / COORD_SCALE


def to_coord(x: float) -> int:
    return round(x * COORD_SCALE)


def from_docs(meta: Any, towns: Any, pois: Any, bars: Any) -> Catalogue:
    """Build the in-memory catalogue from the four decoded documents (validated)."""
    if not isinstance(meta, dict) or meta.get("v") != FORMAT_VERSION:
        raise CatalogueError("meta: unsupported format")
    regions = {
        str(r["code"]): RegionInfo(str(r["code"]), str(r["nameRu"]), str(r["tz"])) for r in meta["regions"]
    }
    kinds = list(meta.get("poiKinds", POI_KINDS))
    bar_kinds = list(meta.get("barKinds", BAR_KINDS))
    region_codes = [str(r["code"]) for r in meta["regions"]]
    credits = [Credit(c.get("author"), c.get("licence"), c.get("url")) for c in meta.get("credits", [])]
    t_id, t_name, t_gen, t_prep, t_lat, t_lon, t_pop, t_region, t_image, t_credit = columns(
        towns, TOWN_COLS, "towns"
    )
    out_towns = [
        CatTown(
            str(a),
            str(b),
            c,
            d,
            LatLon(e / COORD_SCALE, f / COORD_SCALE),
            int(g or 0),
            region_codes[int(h)],
            i,
            j,
        )
        for a, b, c, d, e, f, g, h, i, j in zip(
            t_id, t_name, t_gen, t_prep, t_lat, t_lon, t_pop, t_region, t_image, t_credit, strict=True
        )
    ]
    town_ids = [t.id for t in out_towns]
    p_cols = columns(pois, POI_COLS, "pois")
    out_pois = [
        CatPoi(
            str(a),
            str(b),
            c,
            kinds[int(d)],
            LatLon(e / COORD_SCALE, f / COORD_SCALE),
            town_ids[int(g)],
            int(h or 0),
            bool(i),
            j,
            k,
        )
        for a, b, c, d, e, f, g, h, i, j, k in zip(*p_cols, strict=True)
    ]
    b_cols = columns(bars, BAR_COLS, "bars")
    out_bars = [
        CatBar(
            str(a), str(b), bar_kinds[int(c)], LatLon(d / COORD_SCALE, e / COORD_SCALE), town_ids[int(f)], g
        )
        for a, b, c, d, e, f, g in zip(*b_cols, strict=True)
    ]
    links = {
        str(k): FixtureLink(str(v["wikidata"]), v.get("image"), v.get("credit"))
        for k, v in meta.get("links", {}).items()
    }
    return Catalogue(
        version=str(meta.get("version", "")),
        built_at=str(meta.get("builtAt", "")),
        regions=regions,
        towns=out_towns,
        pois=out_pois,
        bars=out_bars,
        credits=credits,
        links=links,
        sources=dict(meta.get("sources", {})),
    )


def load_packaged() -> Catalogue:
    """The catalogue shipped in `verst_planner/resources` (raises `CatalogueError`)."""
    docs = {}
    for key, name in FILES.items():
        try:
            data = resources.read_bytes(name)
        except (FileNotFoundError, OSError) as e:
            raise CatalogueError(f"{name}: missing") from e
        docs[key] = load_gz(data, name)
    try:
        return from_docs(docs["meta"], docs["towns"], docs["pois"], docs["bars"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise CatalogueError(f"catalogue: malformed ({e!r})") from e


__all__ = [
    "BAR_COLS",
    "BAR_KINDS",
    "FILES",
    "POI_COLS",
    "POI_KINDS",
    "TOWN_COLS",
    "CatBar",
    "CatPoi",
    "CatTown",
    "Catalogue",
    "CatalogueError",
    "Credit",
    "FixtureLink",
    "decode_table",
    "dump_gz",
    "encode_table",
    "from_docs",
    "load_gz",
    "load_packaged",
    "to_coord",
]
