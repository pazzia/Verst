#!/usr/bin/env python3
"""Paste the current output of the investor-pack scripts between their BEGIN/END markers.

Stdlib only. Run after changing any assumptions JSON, then verify with each script's --check.

    python3 tools/biz/embed_outputs.py            # rewrites the blocks in docs/investor/*.md
    python3 tools/biz/embed_outputs.py --dry-run  # only says which blocks are stale

docs/traction/unit-economics.md is not touched here (its owner pastes it by hand); add it to PAIRS if wanted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import financial_model as fmod
import market_sizing as msz
import unit_economics as ue

PAIRS = [
    (ROOT / "docs/investor/market-sizing.md", msz.BEGIN, msz.END,
     lambda: msz.report(msz.load(msz.DEFAULT_MARKET), ue.load(ue.DEFAULT_ASSUMPTIONS))),
    (ROOT / "docs/investor/financial-model.md", fmod.BEGIN, fmod.END,
     lambda: fmod.report(fmod.load(fmod.DEFAULT_FM), ue.load(ue.DEFAULT_ASSUMPTIONS),
                         msz.load(msz.DEFAULT_MARKET), founder_on=False)),
]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    for path, begin, end, make in PAIRS:
        md = path.read_text(encoding="utf-8")
        assert begin in md and end in md, f"{path}: markers not found"
        head, rest = md.split(begin, 1)
        old, tail = rest.split(end, 1)
        new = "\n" + make()
        if old == new:
            print(f"{path.relative_to(ROOT)}: up to date")
            continue
        if args.dry_run:
            print(f"{path.relative_to(ROOT)}: STALE")
            continue
        path.write_text(head + begin + new + end + tail, encoding="utf-8")
        print(f"{path.relative_to(ROOT)}: block rewritten ({len(new.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
