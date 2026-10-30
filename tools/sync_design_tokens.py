#!/usr/bin/env python3
"""Copy design/DesignTokens.kt into :core-ui (M§10.1).

Verbatim once the DES-100 fonts are in android/core-ui/src/main/res/font. Until then the `font` object is
replaced by system fallbacks (condensed sans / monospace / cursive) and everything else stays byte-identical;
`DesignTokensInSyncTest` applies the same transformation and compares.

    python3 tools/sync_design_tokens.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "design/DesignTokens.kt"
DST = ROOT / "android/core-ui/src/main/kotlin/app/verst/core/ui/theme/DesignTokens.kt"
FONT = ROOT / "android/core-ui/src/main/res/font/ibm_plex_sans_condensed_regular.ttf"

FALLBACK = """    object font {
        /** DES-100 pending: the system condensed sans until IBM Plex Sans Condensed is bundled */
        @OptIn(androidx.compose.ui.text.ExperimentalTextApi::class)
        val plexSansCondensed: FontFamily = FontFamily(
            Font(DeviceFontFamilyName("sans-serif-condensed"), FontWeight.Normal),
            Font(DeviceFontFamilyName("sans-serif-condensed"), FontWeight.Medium),
            Font(DeviceFontFamilyName("sans-serif-condensed"), FontWeight.SemiBold),
            Font(DeviceFontFamilyName("sans-serif-condensed"), FontWeight.Bold),
        )
        val plexMono: FontFamily = FontFamily.Monospace
        val marckScript: FontFamily = FontFamily.Cursive
    }"""


def transform(text: str) -> str:
    lines = text.split("\n")
    start = lines.index("    object font {")
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "    }")
    out = "\n".join([*lines[:start], FALLBACK, *lines[end + 1 :]])
    return out.replace(
        "import app.verst.core.ui.R\n", "import androidx.compose.ui.text.font.DeviceFontFamilyName\n"
    )


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(text if FONT.exists() else transform(text), encoding="utf-8")
    print(f"wrote {DST.relative_to(ROOT)} ({'verbatim' if FONT.exists() else 'font fallback'})")


if __name__ == "__main__":
    main()
