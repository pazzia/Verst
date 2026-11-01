"""The catalogues abroad (CEO 29.10): `<dir>/<cc>/catalogue_*.json.gz`, one folder per country.

The format is the Russian catalogue's (`verst_planner.catalogue.from_docs`) plus `meta.country`
{code, wikidata, nameRu, currency, labelLangs} (docs/plan/abroad-wave1-data.md). The folder is outside the
package (`backend/planner/abroad/`, built by CI on `bot/data-abroad-<N>`), so it is read by path, never as a
package resource, and only on the server. A missing folder means no catalogue abroad: the world is Russia.

CEO 30.10 (option «в»): Turkish, Azerbaijani and Uzbek labels are shown in Cyrillic and descriptions or
extracts without Russian are dropped when a country is loaded (`russian_labels`, `foreign/translit.py`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from verst_planner import resources
from verst_planner.catalogue import FILES, OPTIONAL_FILES, Catalogue, CatalogueError, from_docs, load_gz
from verst_planner.foreign.translit import cyrillic, russian_or_none

LOCK = "abroad.lock"


@dataclass(frozen=True, slots=True)
class CountryCatalogue:
    code: str  # BY KZ GE AB AM AZ UZ KG TR
    name_ru: str
    currency: str
    catalogue: Catalogue
    folder: str


def _lock(root: Path) -> dict[str, Any]:
    path = root / LOCK
    if not path.is_file():
        return {}
    doc = json.loads(resources.read_file(path).decode("utf-8"))
    countries = doc.get("countries") if isinstance(doc, dict) else None
    return countries if isinstance(countries, dict) else {}


def _check_sha(folder: str, name: str, data: bytes, lock: dict[str, Any]) -> None:
    """When `abroad.lock` lists the file with a sha256, the bytes must match (a half-copied deploy fails)."""
    files = (lock.get(folder) or {}).get("files")
    if not isinstance(files, dict):
        return
    entry = files.get(name)
    want = entry.get("sha256") if isinstance(entry, dict) else None
    if isinstance(want, str) and hashlib.sha256(data).hexdigest() != want:
        raise CatalogueError(f"abroad/{folder}/{name}: sha256 differs from {LOCK}")


def russian_labels(towns: Any, pois: Any) -> None:
    """In place, on the decoded columnar documents: names (and town case forms) in Cyrillic by their
    `nameLang`, POI `desc` / `extract` kept only when Russian (`extractSrc` cleared with it)."""
    for doc, forms in ((towns, ("name", "gen", "prep")), (pois, ("name",))):
        cols = doc.get("cols") if isinstance(doc, dict) else None
        if not isinstance(cols, dict) or "nameLang" not in cols:
            continue
        for col in forms:
            if col in cols:
                cols[col] = [
                    cyrillic(v, lang) if isinstance(v, str) else v
                    for v, lang in zip(cols[col], cols["nameLang"], strict=True)
                ]
    cols = pois.get("cols") if isinstance(pois, dict) else None
    if isinstance(cols, dict):
        if "desc" in cols:
            cols["desc"] = [russian_or_none(v) for v in cols["desc"]]
        if "extract" in cols:
            cols["extract"] = [russian_or_none(v) for v in cols["extract"]]
            if "extractSrc" in cols:
                cols["extractSrc"] = [
                    s if e else None for e, s in zip(cols["extract"], cols["extractSrc"], strict=True)
                ]


def load_country(folder: Path, lock: dict[str, Any] | None = None) -> CountryCatalogue:
    docs: dict[str, Any] = {}
    for key, name in FILES.items():
        path = folder / name
        if not path.is_file():
            if key in OPTIONAL_FILES:
                continue
            raise CatalogueError(f"abroad/{folder.name}/{name}: missing")
        data = resources.read_file(path)
        _check_sha(folder.name, name, data, lock or {})
        docs[key] = load_gz(data, f"abroad/{folder.name}/{name}")
    try:
        russian_labels(docs["towns"], docs["pois"])
        cat = from_docs(docs["meta"], docs["towns"], docs["pois"], docs["bars"], docs.get("food"))
        country = docs["meta"]["country"]
        code = str(country["code"]).upper()
        name_ru = str(country.get("nameRu") or code)
        currency = str(country["currency"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise CatalogueError(f"abroad/{folder.name}: malformed ({e!r})") from e
    if code.lower() != folder.name.lower():
        raise CatalogueError(f"abroad/{folder.name}: meta.country.code is {code}")
    return CountryCatalogue(code, name_ru, currency, cat, folder.name)


def load_dir(root: Path) -> list[CountryCatalogue]:
    """Every country folder with a `catalogue_meta.json.gz`, in folder order; [] when `root` is missing."""
    if not root.is_dir():
        return []
    lock = _lock(root)
    return [
        load_country(d, lock)
        for d in sorted(root.iterdir(), key=lambda p: p.name)
        if d.is_dir() and (d / FILES["meta"]).is_file()
    ]


__all__ = ["CountryCatalogue", "load_country", "load_dir", "russian_labels"]
