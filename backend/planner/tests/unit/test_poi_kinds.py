"""M9: the category label of a sight (`poiKind` / `poiKindRu`) — name rules first, a curated expectation
list of famous places on the real catalogue, and the text hygiene of the packaged catalogue."""

from __future__ import annotations

import dataclasses
import re
import unittest

from tests.unit import test_mobile_v2
from verst_planner import mobile
from verst_planner.explain import ru
from verst_planner.pipeline.sights import kind_of, not_a_sight

# (exact name, expected kind) — the CEO screenshots and the Designer's QA (des/S4-QA, s4-review.md) included
FAMOUS = (
    ("Церковь Покрова на Нерли", "temple"),
    ("Золотые ворота", "monument"),
    ("Ипатьевский монастырь", "monastery"),
    ("Плещеево озеро", "nature"),
    ("Коломенское", "museum"),
    ("Эрмитаж-Выборг", "museum"),
    ("Беседка", "attraction"),
    ("Московский Кремль", "kremlin"),
    ("Красная площадь", "square"),
    ("Троице-Сергиева лавра", "monastery"),
    ("Суздальский кремль", "kremlin"),
    ("Успенский собор", "temple"),
    ("Дмитриевский собор", "temple"),
    ("Государственная Третьяковская галерея", "museum"),
    ("Государственный исторический музей", "museum"),
    ("Казанский кремль", "kremlin"),
    ("Храм Василия Блаженного", "temple"),
    ("Исаакиевский собор", "temple"),
    ("Петропавловская крепость", "kremlin"),
    ("Нижегородский кремль", "kremlin"),
    ("Ростовский кремль", "kremlin"),
    ("Спасо-Евфимиев монастырь", "monastery"),
    ("Новодевичий монастырь", "monastery"),
    ("Мамаев курган", "monument"),
    ("Рабочий и колхозница", "monument"),
    ("Выставка достижений народного хозяйства", "park"),
    ("Стрелка и Волжская набережная", "embankment"),
    ("Храм Христа Спасителя", "temple"),
    ("Памятник Минину и Пожарскому", "monument"),
    ("Медный всадник", "monument"),
    ("Ярославский музей-заповедник", "museum"),
    ("Палаты Андрея Боголюбского", "attraction"),
    ("Благовещенский собор Казанского кремля", "temple"),
    ("Михайловский замок", "attraction"),
    ("Нарвские триумфальные ворота", "monument"),
    ("Смотровая у Успенского собора", "viewpoint"),
)


class KindRulesTest(unittest.TestCase):
    def test_name_rules(self) -> None:
        self.assertEqual(kind_of("Церковь Покрова на Нерли", "viewpoint"), "temple")
        self.assertEqual(kind_of("Золотые ворота", "museum"), "monument")
        self.assertEqual(kind_of("Музей-усадьба Дуровой", "attraction"), "museum")
        self.assertEqual(kind_of("Смотровая у Успенского собора", "viewpoint"), "viewpoint")
        self.assertEqual(kind_of("Беседка «Храм Венеры»", "attraction"), "attraction")
        self.assertEqual(kind_of("Детская площадка в Клину", "playground"), "playground")
        self.assertEqual(kind_of("Майендорф", "kremlin"), "attraction")  # a castle is not a kremlin
        self.assertEqual(kind_of("Коломенское", "nature", "музей-заповедник в Москве"), "museum")
        self.assertEqual(kind_of("Иске Таш", "attraction"), "attraction")
        self.assertEqual(kind_of("Сквер Победы", "attraction"), "park")
        self.assertEqual(ru.kind_label("temple"), "Храм")
        self.assertEqual(ru.kind_label("unknown"), "Достопримечательность")


class FamousPlacesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        test_mobile_v2.MobileV2Test.setUpClass()
        if mobile._CATALOGUE[0].version == "sample":
            raise unittest.SkipTest("sample catalogue")
        cls.w = mobile._WORLDS["russia_v1"]
        cls.by_name: dict[str, list[str]] = {}
        for p in cls.w.world.places.values():
            if p.type.value == "sight":
                cls.by_name.setdefault(p.name_ru, []).append(mobile.card_kind(cls.w, p))

    def test_famous_places(self) -> None:
        self.assertGreaterEqual(len(FAMOUS), 30)
        for name, want in FAMOUS:
            with self.subTest(name=name):
                kinds = self.by_name.get(name)
                self.assertTrue(kinds, f"{name} is not in the catalogue")
                self.assertEqual(kinds[0], want)

    def test_not_a_sight(self) -> None:
        """M9: a philharmonic is not a road-trip sight unless heritage and q ≥ 0.6."""
        hall = [
            p for p in self.w.world.places.values() if p.name_ru == "Ивановская государственная филармония"
        ]
        self.assertTrue(hall)
        self.assertTrue(not_a_sight(hall[0]))
        self.assertFalse(not_a_sight(dataclasses.replace(hall[0], heritage=True, quality=0.65)))
        self.assertFalse(not_a_sight(dataclasses.replace(hall[0], name_ru="Ивановский музей")))

    def test_catalogue_text(self) -> None:
        """Names start with a capital, no space before punctuation, no bare «Детская площадка»."""
        cat = mobile._CATALOGUE[0]
        space = re.compile(r"\s[,.;:!?»)]")
        for p in cat.pois:
            with self.subTest(poi=p.id):
                self.assertFalse(p.name[:1].islower(), p.name)
                self.assertNotEqual(p.name, "Детская площадка")
                for text in (p.name, p.desc, p.extract):
                    if text:
                        self.assertIsNone(space.search(text), text)
                if p.extract:
                    self.assertFalse(p.extract[:1].islower(), p.extract)


if __name__ == "__main__":
    unittest.main()
