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
  3. a variable font of a sibling family cut at a fixed axis position (IBM Plex Sans v3 [wdth,wght] at
     wdth 75 = Condensed, the axis minimum), as architecture-android-mvp §10.2 allows for variable-only families
Run 1 (40091925830) showed google/fonts' IBM Plex Sans Condensed v1.3 has no Cyrillic; run 2 (40092439867)
found no npm static files and IBM Plex Sans v3.201 with Cyrillic and a wdth axis 75–100, hence source 3.
Run 3 (40092620704) cut wdth 85: Latin advances 4.3 % wider than v1.3 Condensed; wdth 75 matches v1.3 to
0.01 (sum of advances of a Latin sample), so the mockup metrics hold.

Glyph rules (open-issues OI-12): the UI family needs А–я Ёё № ₽ ≈ « » — → ↓ ↑ · and U+00A0; Plex Mono is used
only for odometer digits; Marck Script needs Cyrillic + digits (its «₽ ≈ →» are set in Plex per OI-12).
U+202F is reported but not required: no Plex v1.x/v2.x file maps it and Android falls back per character
(an invisible space). Files taken as published are never modified. The instanced Plex Sans statics are
derived fonts, so (OFL §3, Reserved Font Name «Plex», Manager decision 2026-10-24) their name table is
renamed to «Verst Sans Narrow» (IDs 1/2/3/4/6/16/17, Plex dropped from every other record except 0/13/14)
and assets/licenses/NOTICE.txt states the derivation. Resource file names stay, so DesignTokens.kt is unchanged.
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

# family → google/fonts dir, npm packages (searched for the file name), required glyphs
FAMILIES = {
    "ibmplexsanscondensed": ("ofl/ibmplexsanscondensed", ["@ibm/plex-sans-condensed", "@ibm/plex"], UI),
    "ibmplexmono": ("ofl/ibmplexmono", ["@ibm/plex-mono", "@ibm/plex"], DIGITS),
    "marckscript": ("ofl/marckscript", [], CYR + DIGITS),
}
# family → (sibling google/fonts dir with a variable font, fixed axes) — source 3
VF_SIBLING = {"ibmplexsanscondensed": ("ofl/ibmplexsans", {"wdth": 75})}
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
        "advance_n_o": [font["hmtx"][cmap[c]][0] if c in cmap else None for c in (0x6E, 0x43E)],
        "unitsPerEm": font["head"].unitsPerEm,
        "missingGlyphs": [f"U+{ord(ch):04X}" for ch in required if ord(ch) not in cmap],
        "missingSoft": [f"U+{ord(ch):04X}" for ch in SOFT if ord(ch) not in cmap],
    }


# OFL §3 (Manager decision 2026-10-24): a derived font must not use the Reserved Font Name «Plex».
# Instanced statics (source 3) are renamed; unmodified files keep their names.
RENAMED_FAMILY = {"ibmplexsanscondensed": ("Verst Sans Narrow", "VerstSansNarrow")}
STYLE = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}
KEEP_IDS = {0, 13, 14}  # copyright, licence, licence URL: kept verbatim as OFL §2 requires
RFN = "Plex"


def rename(data: bytes, family: str, weight: int, note: str) -> bytes:
    from fontTools.ttLib import TTFont

    fam, ps = RENAMED_FAMILY[family]
    style = STYLE[weight]
    font = TTFont(io.BytesIO(data))
    name = font["name"]
    version = font["head"].fontRevision
    ribbi = style in ("Regular", "Bold")
    fixed = {
        1: fam if ribbi else f"{fam} {style}",
        2: style if ribbi else "Regular",
        3: f"Verst;{ps}-{style};{version:.3f}",
        4: f"{fam} {style}",
        6: f"{ps}-{style}",
        10: note,
        16: fam,
        17: style,
    }
    name.names = [r for r in name.names if r.nameID not in fixed and r.nameID not in (7, 18, 21, 22, 25)]
    for rec in name.names:
        if rec.nameID in KEEP_IDS:
            continue
        text = rec.toUnicode()
        if RFN in text:
            text = (text.replace("IBM Plex Sans", fam).replace("IBMPlexSans", ps)
                        .replace("IBM Plex", "Verst").replace(RFN, "Verst"))
            rec.string = text
    for nid, text in fixed.items():
        name.setName(text, nid, 3, 1, 0x409)
    os2, head = font["OS/2"], font["head"]
    os2.fsSelection &= ~((1 << 0) | (1 << 5) | (1 << 6))
    os2.fsSelection |= (1 << 5) if style == "Bold" else (1 << 6) if style == "Regular" else 0
    head.macStyle = (head.macStyle & ~1) | (1 if style == "Bold" else 0)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def rfn_names(data: bytes) -> list[str]:
    from fontTools.ttLib import TTFont

    return [f"{r.nameID}:{r.toUnicode()[:60]}" for r in TTFont(io.BytesIO(data))["name"].names
            if RFN in r.toUnicode() and r.nameID not in KEEP_IDS]


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

    def axes(self, folder: str) -> dict:
        from fontTools.ttLib import TTFont

        var = next((n for n in self.names(folder) if n.endswith(".ttf") and "[" in n and "Italic" not in n), None)
        if var is None:
            return {}
        vf = TTFont(io.BytesIO(self.file(folder, var)))
        return {"file": var, "axes": {a.axisTag: [a.minValue, a.defaultValue, a.maxValue] for a in vf["fvar"].axes}}

    def font(self, folder: str, static: str, weight: int, fixed: dict | None = None) -> tuple[bytes, dict] | None:
        names = self.names(folder)
        if static in names and not fixed:
            return self.file(folder, static), {"source": f"google/fonts@{self.sha[:12]}:{folder}/{static}"}
        var = next((n for n in names if n.endswith(".ttf") and "[" in n and "Italic" not in n), None)
        if var is None:
            return None
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer

        vf = TTFont(io.BytesIO(self.file(folder, var)))
        limits = {a.axisTag: a.defaultValue for a in vf["fvar"].axes}
        limits["wght"] = weight
        for tag, value in (fixed or {}).items():
            if tag not in limits:
                return None
            limits[tag] = value
        buf = io.BytesIO()
        instancer.instantiateVariableFont(vf, limits).save(buf)
        return buf.getvalue(), {"source": f"google/fonts@{self.sha[:12]}:{folder}/{var}", "instancedAt": limits}

    def licence(self, folder: str) -> bytes | None:
        lic = next((n for n in self.names(folder) if n.upper().startswith("OFL")), None)
        return self.file(folder, lic) if lic else None


class Npm:
    def __init__(self):
        self.cache: dict[str, tuple[str, dict[str, bytes]] | None] = {}
        self.report: dict[str, dict] = {}

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
                self.report[name] = {"version": ver, "ttf": sorted(k for k in files if k.endswith(".ttf"))[:40]}
            except Exception as e:  # noqa: BLE001 - reported in the lock
                self.report[name] = {"error": repr(e)[:300]}
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
        if family in VF_SIBLING:
            attempts.append(("vf", None))
        done = False
        for kind, pkg in attempts:
            got: dict[str, tuple[bytes, dict]] = {}
            licence: bytes | None = None
            for res, (_, static, weight) in members.items():
                if kind == "google":
                    r = gf.font(folder, static, weight)
                elif kind == "vf":
                    r = gf.font(VF_SIBLING[family][0], static, weight, VF_SIBLING[family][1])
                    if r is not None and family in RENAMED_FAMILY:
                        # no RFN in any name record, not even the description: the attribution is in NOTICE.txt
                        note = (f"Static instance {r[1].get('instancedAt')} of an IBM Corp. font under OFL 1.1, "
                                f"renamed per OFL \u00a73; see assets/licenses/NOTICE.txt.")
                        r = (rename(r[0], family, weight, note), {**r[1], "renamedTo": RENAMED_FAMILY[family][0]})
                else:
                    p = npm.package(pkg)  # type: ignore[arg-type]
                    r = (p[1][static], {"source": f"{p[0]}:{static}"}) if p and static in p[1] else None
                if r is None:
                    break
                got[res] = r
            if len(got) != len(members):
                lock["rejected"].append({"family": family, "source": kind + (f":{pkg}" if pkg else ""), "why": "files not found"})
                continue
            entries = {res: {**meta, **check(data, required), "rfnInNames": rfn_names(data)} for res, (data, meta) in got.items()}
            bad = {res: e["missingGlyphs"] for res, e in entries.items() if e["missingGlyphs"]}
            if bad:
                first = next(iter(entries.values()))
                lock["rejected"].append({"family": family, "source": first["source"].rsplit(":", 1)[0],
                                         "version": first["version"], "cyrillic": first["cyrillic"],
                                         "missing": next(iter(bad.values()))[:12]})
                print(f"::warning title=fonts::{family} from {kind} {pkg or ''}: missing {next(iter(bad.values()))[:12]}")
                continue
            for res, e in entries.items():
                if e.get("renamedTo") and e["rfnInNames"]:
                    print(f"::error title=fonts::{res}: Reserved Font Name left in name records {e['rfnInNames']}")
                    lock["ok"] = False
            for res, (data, _) in got.items():
                (FONT_DIR / f"{res}.ttf").write_bytes(data)
                lock["files"][res] = entries[res]
            if kind == "google":
                licence = gf.licence(folder)
            elif kind == "vf":
                licence = gf.licence(VF_SIBLING[family][0])
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

    if any(e.get("renamedTo") for e in lock["files"].values()):
        (LIC_DIR / "NOTICE.txt").write_text(
            "Verst Sans Narrow (res/font/ibm_plex_sans_condensed_*.ttf) is derived from IBM Plex Sans v3 "
            "(Copyright 2019 IBM Corp.) under the SIL Open Font License 1.1: static instances at wdth 75, "
            "renamed because \u00abPlex\u00bb is a Reserved Font Name. Licence: OFL-ibmplexsanscondensed.txt. "
            "IBM Plex Mono and Marck Script are unmodified (OFL-ibmplexmono.txt, OFL-marckscript.txt).\n",
            encoding="utf-8")
    lock["chosen"] = chosen
    lock["npm"] = npm.report
    lock["vfAxes"] = {fam: gf.axes(d) for fam, (d, _) in VF_SIBLING.items()}
    lock["referenceLatinCondensed"] = {}
    try:  # Latin-only v1.3 Condensed, for the width comparison with the cut instance (not shipped)
        lock["referenceLatinCondensed"] = check(gf.file("ofl/ibmplexsanscondensed", "IBMPlexSansCondensed-Regular.ttf"), [])
    except Exception as e:  # noqa: BLE001
        lock["referenceLatinCondensed"] = {"error": repr(e)[:200]}
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
