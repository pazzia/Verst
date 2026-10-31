import unittest
from datetime import date, time
from decimal import Decimal

from tests.helpers import make_town
from verst_planner.explain import ru

T = ru.THIN
N = ru.NBSP


class RuTest(unittest.TestCase):
    def test_plural(self) -> None:
        cases = {
            1: "день",
            2: "дня",
            5: "дней",
            11: "дней",
            21: "день",
            22: "дня",
            12: "дней",
            104: "дня",
            0: "дней",
        }
        for n, expected in cases.items():
            with self.subTest(n=n):
                self.assertEqual(ru.plural(n, "день", "дня", "дней"), expected)
                self.assertEqual(ru.days_word(n), expected)

    def test_fmt_rub(self) -> None:
        self.assertEqual(ru.fmt_rub(34500), f"34{T}500{N}₽")
        self.assertEqual(ru.fmt_rub(0), f"0{N}₽")
        self.assertEqual(ru.fmt_rub(1_234_567), f"1{T}234{T}567{N}₽")
        self.assertEqual(ru.fmt_int(-5500), f"-5{T}500")
        self.assertEqual(ru.fmt_int(999), "999")

    def test_fmt_decimal_and_consumption(self) -> None:
        self.assertEqual(ru.fmt_decimal(61.4, 2), "61,40")
        self.assertEqual(ru.fmt_decimal(Decimal("61.405"), 2), "61,41")
        self.assertEqual(ru.fmt_decimal(2.5, 1), "2,5")
        self.assertEqual(ru.fmt_decimal(1234.5, 1), f"1{T}234,5")
        self.assertEqual(ru.fmt_decimal(7.5, 0), "8")
        self.assertEqual(ru.fmt_consumption(8), "8")
        self.assertEqual(ru.fmt_consumption(8.0), "8")
        self.assertEqual(ru.fmt_consumption(7.5), "7,5")
        self.assertEqual(ru.fmt_km(744.5), "745")

    def test_decimal_comma_in_user_numbers(self) -> None:
        self.assertEqual(ru.fmt_consumption_setting(8), "8,0")
        self.assertEqual(ru.fmt_consumption_setting(7.5), "7,5")
        self.assertEqual(ru.fmt_price(62.4), "62,40")
        self.assertEqual(ru.fmt_price(Decimal("61.9")), "61,90")
        for out in (ru.fmt_consumption_setting(8), ru.fmt_price(62.4), ru.fmt_decimal(61.4, 2)):
            self.assertNotIn(".", out)
        self.assertEqual(ru.fuel_type_label("ai95"), "АИ-95")
        self.assertEqual(ru.text("cost.title.fuel", fuel_type=ru.fuel_type_label("ai95")), "Бензин АИ-95")
        self.assertEqual(ru.text("cost.title.food"), "Питание")
        self.assertEqual(ru.text("cost.title.reserve", pct=10), "Резерв 10%")
        self.assertEqual(ru.text("cost.title.tolls"), "Платные дороги")

    def test_duration_phrase(self) -> None:
        self.assertEqual(ru.duration_phrase(30), "полчаса")
        self.assertEqual(ru.duration_phrase(60), "час")
        self.assertEqual(ru.duration_phrase(90), "полтора часа")
        self.assertEqual(ru.duration_phrase(120), "два часа")
        self.assertEqual(ru.duration_phrase(135), "2 ч 15 мин")
        self.assertEqual(ru.duration_phrase(45), "45 мин")
        self.assertEqual(ru.duration_phrase(180), "3 ч")
        self.assertEqual(ru.duration_genitive(120), "двух часов")
        self.assertEqual(ru.duration_genitive(90), "полутора часов")
        self.assertEqual(ru.duration_genitive(135), "2 ч 15 мин")

    def test_part_of_day(self) -> None:
        self.assertEqual(ru.part_of_day(time(11, 59)), "обеду")
        self.assertEqual(ru.part_of_day(time(14, 0)), "ужину")
        self.assertEqual(ru.part_of_day(time(17, 0)), "вечеру")

    def test_prepositional(self) -> None:
        self.assertEqual(ru.prepositional(make_town(name_ru="Ростов", name_prep_ru="Ростове")), "Ростове")
        self.assertEqual(ru.prepositional(make_town(name_ru="Плёс", name_prep_ru=None)), "Плёс")

    def test_month_year(self) -> None:
        self.assertEqual(ru.month_year_ru("2026-10"), "октябрь 2026")
        self.assertEqual(ru.month_year_ru(date(2027, 1, 5)), "январь 2027")

    def test_text_and_capitalize(self) -> None:
        self.assertEqual(ru.text("label.dir_later"), "дальше")
        self.assertEqual(ru.text("share.day", day=1, km=265), "День 1 · 265 км")
        with self.assertRaises(KeyError):
            ru.text("share.day", day=1)
        with self.assertRaises(KeyError):
            ru.text("months")
        with self.assertRaises(KeyError):
            ru.words("label.dir_later")
        self.assertEqual(ru.capitalize_first("полтора часа"), "Полтора часа")
        self.assertEqual(ru.capitalize_first(""), "")


if __name__ == "__main__":
    unittest.main()
