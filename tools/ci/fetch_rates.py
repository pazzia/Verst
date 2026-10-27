#!/usr/bin/env python3
"""Fetch today's Central Bank of Russia rates into the app's assets (D-IR-20 currency setting).

    python3 tools/ci/fetch_rates.py android/app/src/main/assets/rates.json

The app converts the engine's rouble amounts with these rates and shows their date. On any failure the existing
file is kept (a build never fails because the CBR site is slow), and the app then shows roubles only.
"""

from __future__ import annotations

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

URL = "https://www.cbr.ru/scripts/XML_daily.asp"
CODES = ["USD", "EUR", "CNY", "KZT", "BYN", "TRY", "AED", "GEL", "AMD", "THB", "IDR"]


def parse(xml: bytes) -> dict:
    root = ET.fromstring(xml)
    as_of = datetime.strptime(root.attrib["Date"], "%d.%m.%Y").date().isoformat()
    rub = {}
    for v in root.findall("Valute"):
        code = v.findtext("CharCode")
        if code not in CODES:
            continue
        nominal = int(v.findtext("Nominal") or "1")
        value = float((v.findtext("Value") or "0").replace(",", "."))
        if nominal > 0 and value > 0:
            rub[code] = round(value / nominal, 6)
    return {"asOf": as_of, "source": "Банк России, " + URL, "rubPerUnit": rub}


def main() -> int:
    out = Path(sys.argv[1])
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "VerstBuild/1.0 (+https://github.com/pazzia/Verst)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = parse(r.read())
    except Exception as e:  # noqa: BLE001 - keep the previous file, never fail the build
        print(f"rates: CBR fetch failed ({e!r}); keeping {out}", file=sys.stderr)
        return 0
    if not data["rubPerUnit"]:
        print("rates: no known currencies in the CBR answer; keeping the file", file=sys.stderr)
        return 0
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"rates: {data['asOf']} {sorted(data['rubPerUnit'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
