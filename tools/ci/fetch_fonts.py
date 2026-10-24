#!/usr/bin/env python3
"""Fetch the OFL fonts of design v5 at pinned sources (DES-100).

Run only by .github/workflows/fonts.yml (needs network and fontTools). Writes:
  android/core-ui/src/main/res/font/<resource>.ttf      (names used by design/DesignTokens.kt)
  android/core-ui/src/main/assets/licenses/OFL-<family>.txt
  android/fonts.lock                                    (sources, sha256, glyph check, probe report)
  design/fonts-probe/*.ttf + report                     (only when a family fails: candidate files for the
                                                         Designer's decision; never merged to main)

Sources are tried in order per family; the first one whose files pass the family's glyph check wins:
  1. github.com/google/fonts at one pinned commit (static file, or a variable font instanced with fontTools)
  2. npm packages of the upstream project (IBM ships @ibm/plex-sans-condensed and the monolithic @ibm/plex)
Run 1 (40091925830) showed google/fonts' IBM Plex Sans Condensed v1.3 has no Cyrillic, hence source 2.

Glyph rules (open-issues OI-12): the UI family needs А–я Ёё № ₽ ≈ « » — → ↓ ↑ · and U+00A0; Plex Mono is used
only for odometer digits; Marck Script needs Cyrillic + digits (its «₽ ≈ →» are set in Plex per OI-12).
U+202F is reported but not required: no Plex v1.x/v2.x file maps it and Android falls back per character
(an invisible space). The fonts are never modified: Plex and Marck Script carry Reserved Font Names (OFL §3).
Exit 1 when a family has no passing source.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/google/fonts"
RAW = "https://raw.githubusercontent.com/google/fonts"
NPM = "https://registry.npmjs.org"
ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT / "android/core-ui/src/main/res/font"
LIC_DIR = ROOT / "android/core-ui/src/main/assets/licenses"
LOCK = ROOT / "android/fonts.lock"
PROBE = ROOT / "design/fonts-probe"

CYR = [chr(c) for c in range(0x410, 0x450)] + ["Ё", "ё"]
DIGITS = list("0123456789")
UI = CYR + DIGITS + list("№₽≈«»—→↓↑·") + [" "]
SOFT = [" "]

# family → google/fonts dir, npm packages (searched for the file name), required glyphs, licence name
FAMILIES = {
    "ibmplexsanscondensed": ("ofl/ibmplexsanscondensed", ["@ibm/plex-sans-condensed", "@ibm/plex"], UI),
    "ibmplexmono": ("ofl/ibmplexmono", ["@ibm/plex-mono", "@ibm/plex"], DIGITS),
    "marckscript": ("ofl/marckscript", [], CYR + DIGITS),
}
# resource name → (family, static file name, weight for a variable-font fallback)
FONTS = {
    "ibm_plex_sans_condensed_regular": ("ibmplexsanscondensed", "IBMPlexSansCondensed-Regular.ttf", 400),
    "ibm_plex_sans_condensed_medium": ("ibmplexsanscondensed", "IBMPlexSansCondensed-Medium.ttf", 500),
    "ibm_plex_sans_condensed_semibold": ("ibmplexsanscondensed", "IBMPlexSansCondensed-SemiBold.ttf", 600),
    "ibm_plex_sans_condensed_bold": ("ibmplexsanscondensed", "IBMPlexSansCondensed-Bold.ttf", 700),
    "ibm_plex_mono_semibold": ("ibmplexmono", "IBMPlexMono-SemiBold.ttf", 600),
    "marck_script_regular": ("marckscript", "MarckScript-Regular.ttf", 400),
}
# Cyrillic condensed OFL candidates, fetched for the Designer only if Plex Sans Condensed fails everywhere
CANDIDATES = {
    "firasanscondensed": ["FiraSansCondensed-Regular.ttf", "FiraSansCondensed-Medium.ttf",
                          "FiraSansCondensed-SemiBold.ttf", "FiraSansCondensed-Bold.ttf"],
    "robotocondensed": ["RobotoCondensed-Regular.ttf", "RobotoCondensed-Bold.ttf"],
    "ptsansnarrow": ["PT_Sans-Narrow-Web-Regular.ttf", "PT_Sans-Narrow-Web-Bold.ttf"],
    "ibmplexsans": ["IBMPlexSans-Regular.ttf", "IBMPlexSans-Bold.ttf"],
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "verst-ci"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok and url.startswith(API):
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=120) as r:
        return bytes(r.read())


def check(data: bytes, required: list[str]) -> dict:
    from fontTools.ttLib import TTFont

    font = TTFont(io.BytesIO(data))
    cmap = font.getBestCmap() or {}
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "version": font["name"].getDebugName(5),
        "usWeightClass": font["OS/2"].usWeightClass,
        "cyrillic": sum(1 for c in cmap if 0x400 <= c < 0x500),
        "missingGlyphs": [f"U+{ord(ch):04X}" for ch in required if ord(ch) not in cmap],
        "missingSoft": [f"U+{ord(ch):04X}" for ch in SOFT if ord(ch) not in cmap],
    }


class GoogleFonts:
    def __init__(self, sha: str):
        self.sha, self.listings = sha, {}

    def names(self, folder: str) -> list[str]:
        if folder not in self.listings:
            try:
                self.listings[folder] = [e["name"] for e in json.loads(get(f"{API}/contents/{folder}?ref={self.sha}"))]
            except Exception as e:  # noqa: BLE001 - reported in the lock
                print(f"google/fonts {folder}: {e}")
                self.listings[folder] = []
        return self.listings[folder]

    def file(self, folder: str, name: str) -> bytes:
        return get(f"{RAW}/{self.sha}/{folder}/{name}")

    def font(self, folder: str, static: str, weight: int) -> tuple[bytes, dict] | None:
        names = self.names(folder)
        if static in names:
            return self.file(folder, static), {"source": f"google/fonts@{self.sha[:12]}:{folder}/{static}"}
        var = next((n for n in names if n.endswith(".ttf") and "[" in n and "Italic" not in n), None)
        if var is None:
            return None
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer

        vf = TTFont(io.BytesIO(self.file(folder, var)))
        limits = {a.axisTag: a.defaultValue for a in vf["fvar"].axes}
        limits["wght"] = weight
        buf = io.BytesIO()
        instancer.instantiateVariableFont(vf, limits).save(buf)
        return buf.getvalue(), {"source": f"google/fonts@{self.sha[:12]}:{folder}/{var}", "instancedAt": limits}

    def licence(self, folder: str) -> bytes | None:
        lic = next((n for n in self.names(folder) if n.upper().startswith("OFL")), None)
        return self.file(folder, lic) if lic else None


class Npm:
    def __init__(self):
        self.cache: dict[str, tuple[str, dict[str, bytes]] | None] = {}

    def package(self, name: str) -> tuple[str, dict[str, bytes]] | None:
        if name not in self.cache:
            try:
                meta = json.loads(get(f"{NPM}/{name.replace('/', '%2f')}"))
                ver = meta["dist-tags"]["latest"]
                tgz = get(meta["versions"][ver]["dist"]["tarball"])
                files: dict[str, bytes] = {}
                with tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz") as tar:
                    for m in tar.getmembers():
                        base = m.name.rsplit("/", 1)[-1]
                        low = m.name.lower()
                        if m.isfile() and (base.endswith(".ttf") and "/ttf/" in low and "unhinted" not in low
                                           or base.upper().startswith(("LICENSE", "OFL"))):
                            # prefer the "complete" set over subsets when names collide
                            if base not in files or "complete" in low:
                                files[base] = tar.extractfile(m).read()  # type: ignore[union-attr]
                self.cache[name] = (f"npm:{name}@{ver}", files)
                print(f"npm {name}@{ver}: {len(files)} files")
            except Exception as e:  # noqa: BLE001 - reported in the lock
                print(f"npm {name}: {e}")
                self.cache[name] = None
        return self.cache[name]


def main() -> int:
    ref = os.environ.get("FONTS_REF", "main")
    sha = json.loads(get(f"{API}/commits/{ref}"))["sha"]
    gf, npm = GoogleFonts(sha), Npm()
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    LIC_DIR.mkdir(parents=True, exist_ok=True)
    lock: dict = {"googleFontsCommit": sha, "files": {}, "rejected": [], "ok": True}
    chosen: dict[str, str] = {}

    for family, (folder, packages, required) in FAMILIES.items():
        members = {r: v for r, v in FONTS.items() if v[0] == family}
        attempts = [("google", None)] + [("npm", p) for p in packages]
        done = False
        for kind, pkg in attempts:
            got: dict[str, tuple[bytes, dict]] = {}
            licence: bytes | None = None
            for res, (_, static, weight) in members.items():
                if kind == "google":
                    r = gf.font(folder, static, weight)
                else:
                    p = npm.package(pkg)  # type: ignore[arg-type]
                    r = (p[1][static], {"source": f"{p[0]}:{static}"}) if p and static in p[1] else None
                if r is None:
                    break
                got[res] = r
            if len(got) != len(members):
                lock["rejected"].append({"family": family, "source": kind + (f":{pkg}" if pkg else ""), "why": "files not found"})
                continue
            entries = {res: {**meta, **check(data, required)} for res, (data, meta) in got.items()}
            bad = {res: e["missingGlyphs"] for res, e in entries.items() if e["missingGlyphs"]}
            if bad:
                first = next(iter(entries.values()))
                lock["rejected"].append({"family": family, "source": first["source"].rsplit(":", 1)[0],
                                         "version": first["version"], "cyrillic": first["cyrillic"],
                                         "missing": next(iter(bad.values()))[:12]})
                print(f"::warning title=fonts::{family} from {kind} {pkg or ''}: missing {next(iter(bad.values()))[:12]}")
                continue
            for res, (data, _) in got.items():
                (FONT_DIR / f"{res}.ttf").write_bytes(data)
                lock["files"][res] = entries[res]
            if kind == "google":
                licence = gf.licence(folder)
            else:
                p = npm.package(pkg)  # type: ignore[arg-type]
                licence = next((v for k, v in (p[1] if p else {}).items() if k.upper().startswith(("LICENSE", "OFL"))), None)
            if licence:
                (LIC_DIR / f"OFL-{family}.txt").write_bytes(licence)
            else:
                print(f"::error title=fonts::{family}: no licence text at the chosen source")
                lock["ok"] = False
            chosen[family] = kind + (f":{pkg}" if pkg else "")
            done = True
            break
        if not done:
            print(f"::error title=fonts::{family}: no source passes the glyph check")
            lock["ok"] = False

    if "ibmplexsanscondensed" not in chosen:
        PROBE.mkdir(parents=True, exist_ok=True)
        report = {}
        for fam, files in CANDIDATES.items():
            folder = f"ofl/{fam}"
            for name in files:
                weight = 700 if "Bold" in name else 600 if "SemiBold" in name else 500 if "Medium" in name else 400
                try:
                    r = gf.font(folder, name, weight)
                except Exception as e:  # noqa: BLE001
                    r, err = None, str(e)
                if r is None:
                    report[f"{fam}/{name}"] = {"error": "not found"}
                    continue
                data, meta = r
                (PROBE / f"{fam}-{weight}.ttf").write_bytes(data)
                report[f"{fam}/{name}"] = {**meta, **check(data, UI)}
            lic = gf.licence(folder)
            if lic:
                (PROBE / f"OFL-{fam}.txt").write_bytes(lic)
        lock["probe"] = report

    LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in lock.items() if k != "files"}, ensure_ascii=False, indent=2))
    return 0 if lock["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
