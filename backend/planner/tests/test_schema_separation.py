"""ADR-0018 / DATA-01: Verst's curated tables hold no OSM-copied attributes.

Checked by parsing the SQL migrations (`backend/migrations/sql/NNNN_*.sql`, `.down.sql` excluded),
stdlib only. The planner suite is the only Python suite that CI runs (`make check` in planner.yml, and the
planner job in android.yml), and no PostgreSQL + PostGIS runs in CI yet (DEV-B02). The rules are data: the
tables and allowlists below. A new table, column or migration form that they do not cover fails the test
until someone decides where it belongs. Rules:

R1  Every table is classified (Verst layer, OSM reference, open reference data, config, runtime).
R2  OSM identifiers (`osm_*`) exist only in the OSM reference tables, which hold exactly the allowed
    columns.
R3  Verst tables: coordinates, OSM-key-named columns and JSON/hstore columns only where allowlisted,
    with a reason.
R4  Verst tables: no CHECK list admits an OSM-derived source value ('osm', 'overpass', ...); every URL column
    has a CHECK that rejects openstreetmap.org and friends.
R5  Every fact column of core.place / core.town has an evidence property (core.evidence) or is computed from a
    Verst child table.
R6  152-FZ: no personal-data-shaped columns in Verst tables; every `*_by` column references core.curator.
R7  0001 is immutable (pinned hash).
"""

from __future__ import annotations

import hashlib
import re
import unittest
from dataclasses import dataclass, field
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[2] / "migrations" / "sql"
SQL_0001_SHA256 = "41d83238031d4dcc28655b317cbfd8fa641c522d481624e9490549e70a40d2f3"

# ------------------------------------------------------------------------------------------- rules (data)
VERST = "verst"  # layer B: our own observations (ADR-0018 §2)
OSM_REF = "osm_ref"  # link to an OSM object by id only
OPEN_REF = "open_reference"  # open data we do not curate as the moat (OSM boundaries / toll lines, layer A)
CONFIG = "config"
RUNTIME = "runtime"

LAYER: dict[str, str] = {
    "core.region": OPEN_REF,  # ISO codes; geometry = OSM admin_level=4 (layer A, ODbL)
    "core.toll_segment": OPEN_REF,  # operator tariffs on a road line (line from layer A)
    "core.app_config": CONFIG,
    "app.device": RUNTIME,
    "app.trip": RUNTIME,
    "app.trip_stop": RUNTIME,
    "app.feedback": RUNTIME,
    "app.pro_waitlist": RUNTIME,
    "core.town": VERST,
    "core.place": VERST,
    "core.ready_route": VERST,
    "core.ready_route_point": VERST,
    "core.region_price": VERST,
    "core.curator": VERST,
    "core.evidence": VERST,
    "core.place_check": VERST,
    "core.place_tag": VERST,
    "core.place_fuel": VERST,
    "core.place_photo": VERST,
    "core.road": VERST,
    "core.place_road": VERST,
    "core.ready_route_road": VERST,
    "core.place_osm_ref": OSM_REF,
    "core.town_osm_ref": OSM_REF,
}

OSM_REF_COLUMNS: dict[str, frozenset[str]] = {
    "core.place_osm_ref": frozenset(
        {"place_id", "osm_type", "osm_id", "match_method", "linked_at", "linked_by"}
    ),
    "core.town_osm_ref": frozenset(
        {"town_id", "osm_type", "osm_id", "match_method", "linked_at", "linked_by"}
    ),
}

OSM_ID_COLUMN = re.compile(r"(^|_)osm(_|$)")
COORDINATE_COLUMN = re.compile(
    r"^(geom|geog|the_geom|way|lat|lon|lng|latitude|longitude|point|location|coords?)$"
)
# Coordinates the lawyer's default allows (risk register R-02: captured independently, never from OSM; the
# evidence CHECK `evidence_geom_source` limits the sources). LEG-01 question 7 may narrow this.
ALLOWED_COORDINATES: dict[tuple[str, str], str] = {
    (
        "core.place",
        "geom",
    ): "own capture: GNSS visit, venue site, partner feed, registry, Wikidata (ADR-0018 §4)",
    ("core.town", "geom"): "town centre from Wikidata (CC0) or own capture (ADR-0018 §4)",
}

# OSM keys that a careless import would copy (':' written as '_'). Matching column names are refused in Verst
# tables unless allowlisted below with the reason why the column is our own observation.
# fmt: off
OSM_KEYS: frozenset[str] = frozenset(
    {
        "name", "name_ru", "name_en", "int_name", "old_name", "alt_name", "official_name", "short_name",
        "addr_street", "addr_housenumber", "addr_city", "addr_postcode", "addr_full", "addr_place",
        "amenity", "tourism", "shop", "leisure", "highway", "building", "historic", "craft", "office",
        "cuisine", "diet_vegetarian", "website", "url", "phone", "email", "contact_phone", "contact_website",
        "contact_email", "contact_vk", "contact_telegram", "opening_hours", "check_in", "check_out",
        "wheelchair", "brand", "brand_wikidata", "operator", "wikidata", "wikipedia", "fee", "charge", "dog",
        "stars", "rooms", "beds", "capacity", "internet_access", "smoking", "toilets", "takeaway",
        "outdoor_seating", "drive_through", "payment_cash", "payment_cards", "fuel_diesel", "fuel_octane_92",
        "fuel_octane_95", "fuel_octane_98", "fuel_lpg", "fuel_cng", "description", "description_ru", "image",
        "wikimedia_commons", "population", "ref", "int_ref", "maxspeed", "lanes", "surface", "toll",
    }
)
# fmt: on
ALLOWED_OSM_KEY_NAMES: dict[tuple[str, str], str] = {
    ("core.place", "name_ru"): "name on the sign / official site; evidence property name_ru",
    ("core.place", "opening_hours"): "our observation in OSM hours syntax (hours.py); evidence opening_hours",
    ("core.place", "description_ru"): "our own text (checklist §3.5); evidence description_ru",
    ("core.town", "name_ru"): "official town name; evidence property name_ru",
    ("core.town", "population"): "Rosstat figure (checklist §3.6); evidence population, source registry",
    ("core.road", "ref"): "official road number (Government Decree No. 928), not OSM ref",
    ("core.road", "name_ru"): "official road name (Government Decree No. 928)",
}
JSON_TYPE = re.compile(r"^\s*(jsonb?|hstore)\b", re.IGNORECASE)
ALLOWED_JSON: dict[tuple[str, str], str] = {}  # none: a JSON bag in a curated table could carry raw OSM tags

OSM_SOURCE_VALUES: frozenset[str] = frozenset(
    {"osm", "openstreetmap", "overpass", "nominatim", "photon", "geofabrik", "osm_import", "import_osm"}
)

# R5: columns that are not facts about the world (ids, workflow, timestamps, derived region).
STRUCTURAL: dict[str, frozenset[str]] = {
    "core.place": frozenset(
        {"id", "region_code", "source", "sponsored", "status", "hidden_reason", "created_at", "updated_at"}
    ),
    "core.town": frozenset({"id", "region_code", "status", "created_at", "updated_at"}),
}
# Columns computed by triggers from a Verst table that carries its own provenance.
DERIVED: dict[str, dict[str, str]] = {
    "core.place": {
        "tags": "core.place_tag",
        "photo_keys": "core.place_photo",
        "verified_at": "core.place_check",
        "verified_by": "core.place_check",
    },
    "core.town": {"lodging_count_cache": "core.place"},
}
EVIDENCE_CONSTRAINT = {"core.place": "evidence_place_property", "core.town": "evidence_town_property"}
EVIDENCE_PSEUDO = frozenset({"tag", "fuel", "road"})  # properties kept in child tables, qualified by name

PERSONAL_DATA_COLUMN = re.compile(
    r"(e_?mail|phone|full_name|first_name|last_name|surname|patronymic|fio|passport|birth|snils|inn$)"
)


# ------------------------------------------------------------------------------------------- DDL parser
class UnsupportedDDL(Exception):
    """A migration uses a form the parser does not understand: extend the parser, never skip silently."""


@dataclass
class Table:
    columns: dict[str, str] = field(default_factory=dict)  # name -> definition
    checks: dict[str, str] = field(default_factory=dict)  # constraint name -> expression
    fks: dict[str, tuple[str, tuple[str, ...]]] = field(default_factory=dict)  # name -> (target, columns)


@dataclass
class Schema:
    tables: dict[str, Table] = field(default_factory=dict)
    views: set[str] = field(default_factory=set)

    def fk_target(self, table: str, column: str) -> str | None:
        for target, cols in self.tables[table].fks.values():
            if cols == (column,):
                return target
        return None


def statements(sql: str) -> list[str]:
    """Split SQL into statements; drop comments, keep quoted literals, replace $tag$ bodies by `$BODY$`."""
    out: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif sql[i] == "'":
            j = i + 1
            while True:
                j = sql.find("'", j)
                if j < 0:
                    raise UnsupportedDDL("unterminated string literal")
                if sql.startswith("''", j):
                    j += 2
                    continue
                break
            buf.append(sql[i : j + 1])
            i = j + 1
        elif (m := re.match(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$", sql[i:])) is not None:
            tag = m.group(0)
            end = sql.find(tag, i + len(tag))
            if end < 0:
                raise UnsupportedDDL(f"unterminated {tag} body")
            buf.append(" $BODY$ ")
            i = end + len(tag)
        elif sql[i] == ";":
            if stmt := " ".join("".join(buf).split()):
                out.append(stmt)
            buf = []
            i += 1
        else:
            buf.append(sql[i])
            i += 1
    if stmt := " ".join("".join(buf).split()):
        out.append(stmt)
    return out


def split_top(text: str) -> list[str]:
    """Split on commas outside parentheses and quotes."""
    parts: list[str] = []
    depth, quoted, start = 0, False, 0
    for k, ch in enumerate(text):
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        elif not quoted and depth == 0 and ch == ",":
            parts.append(text[start:k].strip())
            start = k + 1
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def paren_body(text: str, open_at: int) -> str:
    """The text inside the parenthesis that opens at `open_at`."""
    depth, quoted = 0, False
    for k in range(open_at, len(text)):
        ch = text[k]
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_at + 1 : k]
    raise UnsupportedDDL(f"unbalanced parentheses: {text[:80]}")


def short(table: str) -> str:
    return table.split(".")[-1]


def add_column(schema: Schema, table: str, item: str) -> None:
    m = re.match(r'"?(\w+)"?\s+(.*)$', item, re.S)
    if m is None:
        raise UnsupportedDDL(f"{table}: cannot read column {item[:60]}")
    col, definition = m.group(1).lower(), m.group(2)
    t = schema.tables[table]
    t.columns[col] = definition
    if (c := re.search(r"\bCHECK\s*\(", definition, re.I)) is not None:
        t.checks[f"{short(table)}_{col}_check"] = paren_body(definition, c.end() - 1)
    if (r := re.search(r"\bREFERENCES\s+([\w.]+)", definition, re.I)) is not None:
        t.fks[f"{short(table)}_{col}_fkey"] = (r.group(1).lower(), (col,))


def add_constraint(schema: Schema, table: str, item: str, auto_index: int) -> None:
    t = schema.tables[table]
    m = re.match(r"(?:CONSTRAINT\s+(\w+)\s+)?(.*)$", item, re.S | re.I)
    assert m is not None
    name, body = m.group(1), m.group(2)
    if re.match(r"CHECK\s*\(", body, re.I):
        t.checks[name or f"{short(table)}_check{auto_index}"] = paren_body(body, body.index("("))
    elif (f := re.match(r"FOREIGN\s+KEY\s*\(([^)]*)\)\s*REFERENCES\s+([\w.]+)", body, re.I)) is not None:
        cols = tuple(c.strip().lower() for c in f.group(1).split(","))
        t.fks[name or f"{short(table)}_{'_'.join(cols)}_fkey"] = (f.group(2).lower(), cols)
    elif not re.match(r"(PRIMARY\s+KEY|UNIQUE|EXCLUDE)\b", body, re.I):
        raise UnsupportedDDL(f"{table}: unknown constraint {item[:60]}")


def drop_column(schema: Schema, table: str, col: str) -> None:
    t = schema.tables[table]
    if col not in t.columns:
        raise UnsupportedDDL(f"{table}: DROP COLUMN {col} that does not exist")
    del t.columns[col]
    t.checks = {k: v for k, v in t.checks.items() if k != f"{short(table)}_{col}_check"}
    t.fks = {k: v for k, v in t.fks.items() if col not in v[1]}


def apply_alter(schema: Schema, table: str, actions: str) -> None:
    if table not in schema.tables:
        raise UnsupportedDDL(f"ALTER TABLE on unknown table {table}")
    t = schema.tables[table]
    for k, action in enumerate(split_top(actions)):
        a = action
        if m := re.match(r"ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(.*)$", a, re.S | re.I):
            add_column(schema, table, m.group(1))
        elif m := re.match(r"ADD\s+(CONSTRAINT\s+.*)$", a, re.S | re.I):
            add_constraint(schema, table, re.sub(r"\s+NOT\s+VALID\s*$", "", m.group(1), flags=re.I), k)
        elif m := re.match(r"DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?\"?(\w+)\"?", a, re.I):
            drop_column(schema, table, m.group(1).lower())
        elif m := re.match(r"DROP\s+CONSTRAINT\s+(?:IF\s+EXISTS\s+)?(\w+)", a, re.I):
            t.checks.pop(m.group(1), None)
            t.fks.pop(m.group(1), None)
        elif m := re.match(r"RENAME\s+COLUMN\s+\"?(\w+)\"?\s+TO\s+\"?(\w+)\"?$", a, re.I):
            old, new = m.group(1).lower(), m.group(2).lower()
            t.columns[new] = t.columns.pop(old)
        elif m := re.match(r"RENAME\s+TO\s+(\w+)$", a, re.I):
            new_name = f"{table.split('.')[0]}.{m.group(1).lower()}"
            schema.tables[new_name] = schema.tables.pop(table)
            table = new_name
        elif not re.match(
            r"(ALTER\s+COLUMN|VALIDATE\s+CONSTRAINT|OWNER\s+TO|(ENABLE|DISABLE)\s+TRIGGER)\b", a, re.I
        ):
            raise UnsupportedDDL(f"ALTER TABLE {table}: unsupported action {a[:60]}")


def apply(schema: Schema, sql: str) -> Schema:
    for stmt in statements(sql):
        if m := re.match(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.]+)\s*\(", stmt, re.I):
            name = m.group(1).lower()
            if name in schema.tables:
                raise UnsupportedDDL(f"table {name} created twice")
            schema.tables[name] = Table()
            for k, item in enumerate(split_top(paren_body(stmt, m.end() - 1))):
                if re.match(r"(CONSTRAINT|CHECK|PRIMARY\s+KEY|UNIQUE|FOREIGN\s+KEY|EXCLUDE)\b", item, re.I):
                    add_constraint(schema, name, item, k)
                else:
                    add_column(schema, name, item)
        elif m := re.match(
            r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?:IF\s+EXISTS\s+)?([\w.]+)\s+(.*)$", stmt, re.S | re.I
        ):
            apply_alter(schema, m.group(1).lower(), m.group(2))
        elif m := re.match(r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(.*?)(\s+(CASCADE|RESTRICT))?$", stmt, re.I):
            for name in split_top(m.group(1)):
                schema.tables.pop(name.lower(), None)
        elif m := re.match(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([\w.]+)", stmt, re.I):
            schema.views.add(m.group(1).lower())
        elif m := re.match(r"DROP\s+VIEW\s+(?:IF\s+EXISTS\s+)?([\w.]+)", stmt, re.I):
            schema.views.discard(m.group(1).lower())
        elif re.match(
            r"(CREATE|ALTER)\s+(\w+\s+)*(TABLE|MATERIALIZED\s+VIEW)\b|SELECT\b.*\bINTO\b", stmt, re.I
        ):
            raise UnsupportedDDL(f"unsupported statement: {stmt[:80]}")
    return schema


def up_migrations() -> list[Path]:
    files = sorted(p for p in SQL_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql") if not p.name.endswith(".down.sql"))
    numbers = [p.name[:4] for p in files]
    if numbers != [f"{k:04d}" for k in range(1, len(files) + 1)]:
        raise UnsupportedDDL(f"migration numbers must be 0001..N without gaps: {numbers}")
    return files


def build(files: list[Path]) -> Schema:
    schema = Schema()
    for path in files:
        apply(schema, path.read_text(encoding="utf-8"))
    return schema


def literals(expr: str) -> list[str]:
    return [s.replace("''", "'") for s in re.findall(r"'((?:[^']|'')*)'", expr)]


# ------------------------------------------------------------------------------------------- the rules
def violations(schema: Schema) -> list[str]:
    out: list[str] = []
    # R1
    for name in sorted(set(schema.tables) - set(LAYER)):
        out.append(f"R1 {name}: table not classified in LAYER (decide where it belongs)")
    for name in sorted(set(LAYER) - set(schema.tables)):
        out.append(f"R1 {name}: classified in LAYER but not in the schema (stale rule)")
    for name, table in sorted(schema.tables.items()):
        layer = LAYER.get(name)
        # R2
        if layer == OSM_REF:
            extra = set(table.columns) - OSM_REF_COLUMNS[name]
            out += [
                f"R2 {name}.{c}: OSM reference tables hold only {sorted(OSM_REF_COLUMNS[name])}"
                for c in extra
            ]
        elif layer != OPEN_REF:
            out += [
                f"R2 {name}.{c}: OSM identifier outside an OSM reference table"
                for c in table.columns
                if OSM_ID_COLUMN.search(c)
            ]
        if layer != VERST:
            continue
        for col, definition in table.columns.items():
            # R3
            if COORDINATE_COLUMN.match(col) and (name, col) not in ALLOWED_COORDINATES:
                out.append(f"R3 {name}.{col}: coordinates without an ALLOWED_COORDINATES entry")
            if col in OSM_KEYS and (name, col) not in ALLOWED_OSM_KEY_NAMES:
                out.append(f"R3 {name}.{col}: named like an OSM key; allowlist it with the reason it is ours")
            if JSON_TYPE.match(definition) and (name, col) not in ALLOWED_JSON:
                out.append(f"R3 {name}.{col}: JSON/hstore bag in a Verst table (could carry raw OSM tags)")
            # R4 (URL columns)
            if col.endswith("url") and not any(
                col in expr and "openstreetmap" in expr for expr in table.checks.values()
            ):
                out.append(f"R4 {name}.{col}: no CHECK rejects openstreetmap.org URLs")
            # R6
            if PERSONAL_DATA_COLUMN.search(col):
                out.append(f"R6 {name}.{col}: personal-data column in a Verst table (152-FZ, ADR-0018 §6)")
            if col.endswith("_by") and schema.fk_target(name, col) != "core.curator":
                out.append(f"R6 {name}.{col}: must reference core.curator (pseudonymous id, not a name)")
        # R4 (source values)
        for cname, expr in table.checks.items():
            bad = {v.lower() for v in literals(expr)} & OSM_SOURCE_VALUES
            if bad:
                out.append(f"R4 {name} {cname}: admits OSM-derived value(s) {sorted(bad)}")
    # R5
    evidence = schema.tables.get("core.evidence")
    for name, constraint in EVIDENCE_CONSTRAINT.items():
        if evidence is None or constraint not in evidence.checks:
            out.append(f"R5 core.evidence: missing constraint {constraint} (evidence properties of {name})")
            continue
        props = set(literals(evidence.checks[constraint]))
        if name not in schema.tables:
            continue
        columns = set(schema.tables[name].columns)
        facts = columns - STRUCTURAL[name] - set(DERIVED[name])
        out += [
            f"R5 {name}.{c}: fact column without an evidence property in {constraint}"
            for c in sorted(facts - props)
        ]
        out += [
            f"R5 {constraint}: property {p!r} is neither a column of {name} nor {sorted(EVIDENCE_PSEUDO)}"
            for p in sorted(props - columns - EVIDENCE_PSEUDO)
        ]
        out += [
            f"R5 {name}.{c}: DERIVED/STRUCTURAL lists a column that does not exist"
            for c in sorted((STRUCTURAL[name] | set(DERIVED[name])) - columns)
        ]
        out += [
            f"R5 {name}.{c}: derived from {src}, which is not a Verst table"
            for c, src in DERIVED[name].items()
            if LAYER.get(src) != VERST or src not in schema.tables
        ]
    return out


# ------------------------------------------------------------------------------------------- tests
class SchemaSeparationTest(unittest.TestCase):
    def test_migrations_follow_the_separation_rules(self) -> None:
        found = violations(build(up_migrations()))
        self.assertEqual(found, [], "\n" + "\n".join(found))

    def test_rules_catch_the_0001_schema(self) -> None:
        """The same rules flag what 0002 had to fix: the test can fail."""
        schema = build(up_migrations()[:1])
        found = "\n".join(violations(schema))
        for expected in (
            "R2 core.place.osm_id: OSM identifier outside an OSM reference table",
            "R2 core.town.osm_id: OSM identifier outside an OSM reference table",
            "R4 core.place place_source_check: admits OSM-derived value(s) ['osm']",
            "R6 core.place.verified_by: must reference core.curator",
            "R5 core.evidence: missing constraint evidence_place_property",
        ):
            self.assertIn(expected, found)

    def test_rules_catch_injected_osm_columns(self) -> None:
        cases = {
            "ALTER TABLE core.place ADD COLUMN osm_version integer": "R2 core.place.osm_version",
            "ALTER TABLE core.place_tag ADD COLUMN lat double precision": "R3 core.place_tag.lat",
            "ALTER TABLE core.place ADD COLUMN website text": "R3 core.place.website",
            "ALTER TABLE core.place ADD COLUMN extra jsonb": "R3 core.place.extra",
            "ALTER TABLE core.place ADD COLUMN cuisine text": "R3 core.place.cuisine",
            "ALTER TABLE core.place_osm_ref ADD COLUMN name text": "R2 core.place_osm_ref.name",
            "ALTER TABLE core.place ADD COLUMN wifi boolean": "R5 core.place.wifi",
            "ALTER TABLE core.place_photo ADD COLUMN author_email text": "R6 core.place_photo.author_email",
            "ALTER TABLE core.place_photo ADD COLUMN approved_by text": "R6 core.place_photo.approved_by",
            "ALTER TABLE core.evidence ADD COLUMN mirror_url text": "R4 core.evidence.mirror_url",
            "CREATE TABLE core.osm_poi (id bigint PRIMARY KEY, tags jsonb)": "R1 core.osm_poi",
            "ALTER TABLE core.evidence DROP CONSTRAINT evidence_place_property": "R5 core.evidence: missing",
            "ALTER TABLE core.place_check DROP CONSTRAINT place_check_kind_check, ADD CONSTRAINT k "
            "CHECK (kind IN ('full','osm_import'))": "R4 core.place_check k",
        }
        base = "\n".join(p.read_text(encoding="utf-8") for p in up_migrations())
        for ddl, expected in cases.items():
            with self.subTest(ddl=ddl):
                schema = Schema()
                apply(schema, base + ";\n" + ddl + ";")
                self.assertIn(expected, "\n".join(violations(schema)))

    def test_parser_sees_the_0002_model(self) -> None:
        schema = build(up_migrations())
        place = schema.tables["core.place"]
        self.assertNotIn("osm_id", place.columns)
        self.assertNotIn("osm_id", schema.tables["core.town"].columns)
        self.assertEqual(
            set(schema.tables["core.place_osm_ref"].columns), OSM_REF_COLUMNS["core.place_osm_ref"]
        )
        self.assertEqual(literals(place.checks["place_source_check"]), ["curated", "partner"])
        self.assertEqual(schema.fk_target("core.place", "verified_by"), "core.curator")
        self.assertTrue(
            {"core.place_verified", "core.kpi_verified_by_route", "core.kpi_verified_by_corridor"}
            <= schema.views
        )

    def test_parser_fails_closed(self) -> None:
        for ddl in (
            "CREATE TABLE core.x AS SELECT 1",
            "CREATE UNLOGGED TABLE core.y (a int)",
            "CREATE MATERIALIZED VIEW core.z AS SELECT 1",
            "ALTER TABLE core.place ADD UNIQUE (name_ru)",
        ):
            with self.subTest(ddl=ddl), self.assertRaises(UnsupportedDDL):
                apply(build(up_migrations()), ddl)

    def test_0001_is_immutable(self) -> None:
        digest = hashlib.sha256((SQL_DIR / "0001_initial.sql").read_bytes()).hexdigest()
        self.assertEqual(digest, SQL_0001_SHA256, "0001 is history: add a new migration")


if __name__ == "__main__":
    unittest.main()
