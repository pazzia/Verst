"""Countries of the catalogue pipeline (CEO 29.10: trips abroad, wave 1). One `Country` per catalogue.

`RU` reproduces the Russian pipeline exactly (the queries, the label language, the `RU-` regions): the fetchers
and the builder take a country code and default to `RU`, so the Russian catalogue stays byte-for-byte the same.
The wave-1 countries are the neighbours Russians drive to; their catalogues are planned on the server only and
are written under `backend/planner/abroad/<cc>/` (outside `verst_planner/`, so the APK never packs them).

What is written here is configuration, not place data: the Wikidata ids the CEO named (checked by
`fetch_wikidata.py country`, which fails the run when an English label does not match), the label languages,
the ISO 3166-2 prefix of the first-level divisions and the ISO 4217 currency (checked against Wikidata P38/P498
by the same step). Time zones are in `region_tz_abroad.tsv` (IANA, checked against Wikidata P421 in the build).

Abkhazia (Q23334): Wikidata files its places under P17 Georgia (Q230) and/or Abkhazia, and its region code is
ISO 3166-2 `GE-AB`. Both the `GE` and the `AB` catalogues fetch P17 ∈ {Q230, Q23334}; a town belongs to the
`AB` catalogue when its region is `GE-AB` or its P17 includes Q23334, else to `GE` (`carve`, `inside`). The `AB`
region is labelled «Абхазия».
"""

from __future__ import annotations

from dataclasses import dataclass, field

ABROAD_DIR = "abroad"
"""Under `backend/planner/`: `abroad/<cc>/catalogue_*.json.gz` and `abroad/abroad.lock` (server only)."""


@dataclass(frozen=True, slots=True)
class Country:
    code: str  # the catalogue code (ISO 3166-1 alpha-2; «AB» for Abkhazia, which has none)
    qids: tuple[str, ...]  # Wikidata P17 values that pull a town in; the first is the country's own item
    name_ru: str
    expect: tuple[str, ...]  # English label keywords of qids[0] (`fetch_wikidata.py country` checks them)
    iso_prefix: str  # ISO 3166-2 prefix of the first-level divisions (P300)
    label_langs: str  # wikibase:label languages, Russian first (readable scripts only, then English)
    currency: str  # ISO 4217
    geofabrik_iso: str  # the Geofabrik extract, found by its `iso3166-1:alpha2` in the Geofabrik index
    town_classes: tuple[str, ...] = ("Q7930989",)  # city or town (+ subclasses, `Q_SUBCLASSES`)
    carve: tuple[str, str] | None = None  # (region code, P17 qid) of a territory with its own catalogue
    inside: bool = False  # True: keep only the carved territory; False: drop it
    region_names: dict[str, str] = field(default_factory=dict)  # region code → nameRu (wins over Wikidata)

    @property
    def abroad(self) -> bool:
        return self.code != "RU"

    @property
    def dir_name(self) -> str:
        return self.code.lower()


RU = Country(
    code="RU",
    qids=("Q159",),
    name_ru="Россия",
    expect=("russia",),
    iso_prefix="RU-",
    label_langs="ru",
    currency="RUB",
    geofabrik_iso="RU",
    town_classes=("Q7930989", "Q183342"),  # город России; город федерального значения
)

ABKHAZIA_CARVE = ("GE-AB", "Q23334")

WAVE1: tuple[Country, ...] = (
    Country("BY", ("Q184",), "Беларусь", ("belarus",), "BY-", "ru,be,en", "BYN", "BY"),
    Country("KZ", ("Q232",), "Казахстан", ("kazakhstan",), "KZ-", "ru,kk,en", "KZT", "KZ"),
    Country(
        "GE", ("Q230", "Q23334"), "Грузия", ("georgia",), "GE-", "ru,en", "GEL", "GE", carve=ABKHAZIA_CARVE
    ),
    Country(
        "AB",
        ("Q23334", "Q230"),  # the first id is the one checked (label, capital, currency)
        "Абхазия",
        ("abkhazia",),
        "GE-",
        "ru,ab,en",
        "RUB",
        "GE",  # Geofabrik's Georgia extract covers Abkhazia
        carve=ABKHAZIA_CARVE,
        inside=True,
        region_names={"GE-AB": "Абхазия"},
    ),
    Country("AM", ("Q399",), "Армения", ("armenia",), "AM-", "ru,en", "AMD", "AM"),
    Country("AZ", ("Q227",), "Азербайджан", ("azerbaijan",), "AZ-", "ru,az,en", "AZN", "AZ"),
    Country("UZ", ("Q265",), "Узбекистан", ("uzbekistan",), "UZ-", "ru,uz,en", "UZS", "UZ"),
    Country("KG", ("Q813",), "Киргизия", ("kyrgyzstan", "kyrgyz"), "KG-", "ru,ky,en", "KGS", "KG"),
    Country("TR", ("Q43",), "Турция", ("turkey", "türkiye"), "TR-", "ru,tr,en", "TRY", "TR"),
)

COUNTRIES: dict[str, Country] = {c.code: c for c in (RU, *WAVE1)}


def get(code: str | None) -> Country:
    """The country of a catalogue code (case-insensitive; None = Russia)."""
    key = (code or "RU").upper()
    if key not in COUNTRIES:
        raise SystemExit(f"unknown country {code!r}; known: {' '.join(COUNTRIES)}")
    return COUNTRIES[key]


def in_carve(country: Country, region: str | None, countries: list[str] | tuple[str, ...]) -> bool:
    """Is this town inside the carved territory (Abkhazia: region GE-AB, or P17 includes Q23334)?"""
    if country.carve is None:
        return False
    code, qid = country.carve
    return region == code or qid in countries


def keeps(country: Country, region: str | None, countries: list[str] | tuple[str, ...]) -> bool:
    """Does this country's catalogue keep a town of this region and these P17 values?"""
    if country.carve is None:
        return True
    return in_carve(country, region, countries) == country.inside
