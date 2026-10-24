#!/usr/bin/env python3
"""Fetch the OFL fonts of design v5 from github.com/google/fonts at one pinned commit (DES-100).

Run only by .github/workflows/fonts.yml (needs network and fontTools). Writes:
  android/core-ui/src/main/res/font/<resource>.ttf      (names used by design/DesignTokens.kt)
  android/core-ui/src/main/assets/licenses/OFL-<family>.txt
  android/fonts.lock                                    (commit, source paths, sha256, glyph check)

Static files are preferred. If google/fonts only ships a variable font for a family, the static
instance is cut with fontTools.varLib.instancer at the required weight (recorded in the lock).
Fails (exit 1) when any required glyph is missing: А–я Ё ё № ₽ ≈ « » — U+202F U+00A0 → ·.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/google/fonts"
RAW = "https://raw.githubusercontent.com/google/fonts"
ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT / "android/core-ui/src/main/res/font"
LIC_DIR = ROOT / "android/core-ui/src/main/assets/licenses"
LOCK = ROOT / "android/fonts.lock"

# resource name → (google/fonts dir, static file, weight for a variable-font fallback)
FONTS = {
    "ibm_plex_sans_condensed_regular": ("ofl/ibmplexsanscondensed", "IBMPlexSansCondensed-Regular.ttf", 400),
    "ibm_plex_sans_condensed_medium": ("ofl/ibmplexsanscondensed", "IBMPlexSansCondensed-Medium.ttf", 500),
    "ibm_plex_sans_condensed_semibold": ("ofl/ibmplexsanscondensed", "IBMPlexSansCondensed-SemiBold.ttf", 600),
    "ibm_plex_sans_condensed_bold": ("ofl/ibmplexsanscondensed", "IBMPlexSansCondensed-Bold.ttf", 700),
    "ibm_plex_mono_semibold": ("ofl/ibmplexmono", "IBMPlexMono-SemiBold.ttf", 600),
    "marck_script_regular": ("ofl/marckscript", "MarckScript-Regular.ttf", 400),
}
REQUIRED = [chr(c) for c in range(0x410, 0x450)] + list("Ёё№₽≈«»—→·") + [" ", " "]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "verst-ci"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok and url.startswith(API):
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return bytes(r.read())


def main() -> int:
    from fontTools.ttLib import TTFont  # installed by the workflow

    ref = os.environ.get("FONTS_REF", "main")
    sha = json.loads(get(f"{API}/commits/{ref}"))["sha"]
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    LIC_DIR.mkdir(parents=True, exist_ok=True)
    lock: dict[str, object] = {"source": "github.com/google/fonts", "commit": sha, "files": {}}
    listings: dict[str, list[str]] = {}
    ok = True
    for res, (folder, static, weight) in FONTS.items():
        if folder not in listings:
            listings[folder] = [e["name"] for e in json.loads(get(f"{API}/contents/{folder}?ref={sha}"))]
            lic = next((n for n in listings[folder] if n.upper().startswith("OFL")), None)
            if lic:
                (LIC_DIR / f"OFL-{folder.split('/')[-1]}.txt").write_bytes(get(f"{RAW}/{sha}/{folder}/{lic}"))
        names = listings[folder]
        entry: dict[str, object] = {}
        if static in names:
            data = get(f"{RAW}/{sha}/{folder}/{static}")
            entry["path"] = f"{folder}/{static}"
        else:
            var = next((n for n in names if n.endswith(".ttf") and "[" in n and "Italic" not in n), None)
            if var is None:
                print(f"::error title=fonts::{folder}: neither {static} nor a variable font; listing: {names}")
                ok = False
                continue
            from fontTools.varLib import instancer

            vf = TTFont(io.BytesIO(get(f"{RAW}/{sha}/{folder}/{var}")))
            axes = {a.axisTag: a for a in vf["fvar"].axes}
            limits = {"wght": weight}
            limits.update({t: a.defaultValue for t, a in axes.items() if t != "wght"})
            inst = instancer.instantiateVariableFont(vf, limits)
            buf = io.BytesIO()
            inst.save(buf)
            data = buf.getvalue()
            entry["path"] = f"{folder}/{var}"
            entry["instancedAt"] = limits
        font = TTFont(io.BytesIO(data))
        cmap = font.getBestCmap() or {}
        missing = [f"U+{ord(ch):04X}" for ch in REQUIRED if ord(ch) not in cmap]
        entry.update({"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "missingGlyphs": missing})
        if missing:
            print(f"::error title=fonts::{res}: missing glyphs {missing}")
            ok = False
        (FONT_DIR / f"{res}.ttf").write_bytes(data)
        lock["files"][res] = entry  # type: ignore[index]
    LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(lock, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
