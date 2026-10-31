import unittest

from tests.helpers import sample_plan
from verst_planner.explain.ru import NBSP, THIN
from verst_planner.explain.share import share_text


class ShareTest(unittest.TestCase):
    def test_share_text_format(self) -> None:
        expected = "\n".join(
            [
                "Москва → Ярославль · 255 км · 2 дня",
                "День 1 · 200 км",
                "08:00 Москва",
                "12:45 Кафе «Ель»",
                "15:30 Ростов",
                "День 2 · 55 км",
                "09:00 Ростов",
                "09:50 Ярославль",
                f"Итого ≈ 12{THIN}900{NBSP}₽ на 3 чел.",
            ]
        )
        self.assertEqual(share_text(sample_plan()), expected)

    def test_one_day_word(self) -> None:
        import dataclasses

        plan = sample_plan()
        one = dataclasses.replace(plan, days=1, km=1255, days_list=plan.days_list[:1])
        self.assertTrue(share_text(one).startswith(f"Москва → Ярославль · 1{THIN}255 км · 1 день\n"))


if __name__ == "__main__":
    unittest.main()
