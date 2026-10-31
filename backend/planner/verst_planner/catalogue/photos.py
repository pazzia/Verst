"""Wikimedia Commons URLs for a P18 file name (ADR-0012 §6).

`Special:FilePath/<file>?width=<w>` redirects to a rasterised thumbnail on upload.wikimedia.org (SVG, TIFF and
PDF become PNG/JPEG), so the app decodes only JPEG/PNG whatever the original format is.
"""

from __future__ import annotations

from urllib.parse import quote

CARD_WIDTH = 800
THUMB_WIDTH = 400
BASE = "https://commons.wikimedia.org/wiki/"


def _title(file: str) -> str:
    return quote(file.strip().replace(" ", "_"), safe="()_,-.")


def thumb_url(file: str, width: int) -> str:
    return f"{BASE}Special:FilePath/{_title(file)}?width={width}"


def page_url(file: str) -> str:
    return f"{BASE}File:{_title(file)}"


def image_urls(file: str) -> dict[str, str]:
    return {
        "card": thumb_url(file, CARD_WIDTH),
        "thumb": thumb_url(file, THUMB_WIDTH),
        "page": page_url(file),
    }
