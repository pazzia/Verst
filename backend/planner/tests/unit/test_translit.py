"""CEO 30.10 (option «в»): names abroad in Cyrillic by their label language; other descriptions dropped."""

# Latin and Cyrillic letters side by side are the point here.
from __future__ import annotations

import unittest

from verst_planner.foreign.catalogues import russian_labels
from verst_planner.foreign.translit import cyrillic, russian_or_none


class TranslitTest(unittest.TestCase):
    def test_turkish(self) -> None:
        cases = {
            "İhsangazi": "Ихсангази",
            "Perşembe": "Першембе",
            "Eskişehir": "Эскишехир",
            "Antalya": "Анталья",
            "Üsküdar": "Ускюдар",
            "Ayasofya Camii": "Аясофья Джамии",
            "Eyyübiye": "Эйюбие",
            "Göreme": "Гёреме",
        }
        for src, want in cases.items():
            self.assertEqual(cyrillic(src, "tr"), want, src)

    def test_azerbaijani_and_uzbek(self) -> None:
        self.assertEqual(cyrillic("Nərimanov parkı", "az"), "Нариманов паркы")
        self.assertEqual(cyrillic("Qış bulvarı", "az"), "Гыш булвары")
        self.assertEqual(cyrillic("Navroʻz bogʻi", "uz"), "Навруз боги")
        self.assertEqual(cyrillic("Kox ota jome’ masjidi", "uz"), "Кох ота джоме масджиди")

    def test_left_as_is(self) -> None:
        self.assertEqual(cyrillic("Mtatsminda Park", "en"), "Mtatsminda Park")
        self.assertEqual(cyrillic("Tashkent City Park", "uz"), "Tashkent City Park")  # English under «uz»
        self.assertEqual(cyrillic("Стамбул", "tr"), "Стамбул")
        self.assertEqual(cyrillic("Galata", None), "Galata")

    def test_descriptions_only_in_russian(self) -> None:
        self.assertIsNone(russian_or_none("Museum in Yerevan, Armenia"))
        self.assertIsNone(russian_or_none("Beyoğlu'nda müze"))
        self.assertEqual(russian_or_none("Музей в Батуми"), "Музей в Батуми")

    def test_russian_labels_on_documents(self) -> None:
        towns = {"cols": {"name": ["Kocasinan"], "gen": [None], "prep": ["Kocasinan"], "nameLang": ["tr"]}}
        pois = {
            "cols": {
                "name": ["Galata Kulesi", "Mtatsminda Park"],
                "nameLang": ["tr", "en"],
                "desc": ["İstanbul'da kule", "Парк в Тбилиси"],
                "extract": ["Galata Kulesi ...", None],
                "extractSrc": ["wikipedia", None],
            }
        }
        russian_labels(towns, pois)
        self.assertEqual(towns["cols"], {"name": ["Коджасинан"], "gen": [None], "prep": ["Коджасинан"],
                                         "nameLang": ["tr"]})  # fmt: skip
        self.assertEqual(pois["cols"]["name"], ["Галата Кулеси", "Mtatsminda Park"])
        self.assertEqual(pois["cols"]["desc"], [None, "Парк в Тбилиси"])
        self.assertEqual((pois["cols"]["extract"], pois["cols"]["extractSrc"]), ([None, None], [None, None]))
