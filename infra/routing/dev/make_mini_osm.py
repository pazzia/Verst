"""Write a tiny synthetic OSM XML map for recording GraphHopper fixtures without the Russia extract.

The map is made up (no real roads), placed at lat 56.0, lon 37.0-37.3 so GraphHopper's country lookup sees
Russia. It has exactly what the adapter tests need:

- town W (56.000, 37.000) and town E (56.000, 37.300);
- a toll motorway «М-11» (toll=yes) on lat 56.010, the fast way W -> E;
- a free trunk «М-10» on lat 55.985; its west half is tagged "М-10;Е105" (two refs), its east half "M-10" with
  a Latin M (a real OSM tagging error the adapter normalises);
- a regional secondary «46К-1150» and a primary «Р-132» to village S (55.950, 37.150), used as a via point;
- an island: two residential streets at (56.05, 37.15) that touch no other road.

Usage: python3 make_mini_osm.py OUT.osm
"""

from __future__ import annotations

import sys
from xml.sax.saxutils import quoteattr

Node = tuple[int, float, float]


class Map:
    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.ways: list[tuple[int, list[int], dict[str, str]]] = []
        self._by_pos: dict[tuple[float, float], int] = {}

    def node(self, lat: float, lon: float) -> int:
        key = (round(lat, 6), round(lon, 6))
        if key not in self._by_pos:
            nid = len(self.nodes) + 1
            self.nodes.append((nid, key[0], key[1]))
            self._by_pos[key] = nid
        return self._by_pos[key]

    def way(self, points: list[tuple[float, float]], **tags: str) -> None:
        self.ways.append(
            (len(self.ways) + 1, [self.node(a, b) for a, b in points], tags)
        )

    def xml(self) -> str:
        out = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<osm version="0.6" generator="verst make_mini_osm">',
        ]
        for nid, lat, lon in self.nodes:
            out.append(
                f'  <node id="{nid}" version="1" lat="{lat:.6f}" lon="{lon:.6f}"/>'
            )
        for wid, nds, tags in self.ways:
            out.append(f'  <way id="{wid}" version="1">')
            out.extend(f'    <nd ref="{n}"/>' for n in nds)
            out.extend(
                f"    <tag k={quoteattr(k)} v={quoteattr(v)}/>" for k, v in tags.items()
            )
            out.append("  </way>")
        out.append("</osm>")
        return "\n".join(out) + "\n"


def line(
    lat0: float, lon0: float, lat1: float, lon1: float, n: int
) -> list[tuple[float, float]]:
    return [
        (lat0 + (lat1 - lat0) * k / n, lon0 + (lon1 - lon0) * k / n)
        for k in range(n + 1)
    ]


def build() -> Map:
    m = Map()
    # town W -> junction JW, junction JE -> town E
    m.way(
        [(56.000, 37.000), (56.000, 37.010)], highway="residential", name="улица Ленина"
    )
    m.way(
        [(56.000, 37.290), (56.000, 37.300)], highway="tertiary", name="Заводская улица"
    )
    # toll motorway М-11 (oneway=no: one carriageway is enough for the fixtures)
    m.way([(56.000, 37.010), (56.010, 37.020)], highway="motorway_link", oneway="no")
    m.way(
        line(56.010, 37.020, 56.010, 37.280, 13),
        highway="motorway",
        ref="М-11",
        toll="yes",
        maxspeed="110",
        oneway="no",
        name="Скоростная дорога М-11 «Нева»",
    )
    m.way([(56.010, 37.280), (56.000, 37.290)], highway="motorway_link", oneway="no")
    # free trunk М-10: regional access, two halves with different ref spellings
    m.way(
        [(56.000, 37.010), (55.990, 37.015), (55.985, 37.020)],
        highway="secondary",
        ref="46К-1150",
    )
    m.way(
        line(55.985, 37.020, 55.985, 37.150, 7),
        highway="trunk",
        ref="М-10;Е105",
        maxspeed="90",
    )
    m.way(
        line(55.985, 37.150, 55.985, 37.280, 7),
        highway="trunk",
        ref="M-10",
        maxspeed="90",
    )
    m.way([(55.985, 37.280), (55.995, 37.287), (56.000, 37.290)], highway="secondary")
    # village S on the primary Р-132
    m.way(
        line(55.985, 37.150, 55.950, 37.150, 4),
        highway="primary",
        ref="Р-132",
        name="Р-132",
    )
    # island: two streets in a T, touching no other road (a closed loop would collapse to one tower node)
    m.way(
        [(56.050, 37.140), (56.050, 37.150), (56.050, 37.160)],
        highway="residential",
        name="Островная улица",
    )
    m.way(
        [(56.050, 37.150), (56.056, 37.150)],
        highway="residential",
        name="Береговая улица",
    )
    return m


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        f.write(build().xml())


if __name__ == "__main__":
    main()
