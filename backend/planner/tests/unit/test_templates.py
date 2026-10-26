import json
import unittest

from verst_planner.explain.templates import RESOURCES, TEMPLATE_KEYS, ReasonTemplates, placeholders

# Documented params per key (A§8.1)
DOC_PARAMS: dict[str, dict[str, str | int | float]] = {
    "overnight.shift.hotels": {
        "shift": "Не в Ростове, а на 55 км дальше",
        "crew_suffix": ", куда пускают с собакой",
    },
    "overnight.shift.quality": {"shift": "На 30 км раньше вашего предела"},
    "overnight.shift.evening": {"shift": "На 30 км раньше вашего предела"},
    "overnight.cap_ok": {"daily_km": 300},
    "overnight.shift.later": {"other_prep": "Ростове", "dkm": 55},
    "overnight.shift.earlier": {"other_prep": "Ростове", "dkm": 20},
    "overnight.shift.limit": {"dkm": 30},
    "overnight.widened": {"dkm": 80, "dir": "раньше"},
    "overnight.template": {"route": "Золотое кольцо"},
    "fuel.range": {"km": 40},
    "rest.generic": {"min": 20, "min_word": "минут", "drive": "двух часов"},
    "rest.who": {"min": 20, "min_word": "минут", "who": "ребёнку побегать, собаке погулять"},
    "rest.fun.child": {"min": 45, "min_word": "минут"},
    "sight.detour": {"minutes": 35},
    "rest.fun.dog": {"min": 30, "min_word": "минут"},
    "rest.fun.adults": {"min": 40, "min_word": "минут"},
    "lunch.default": {"town_prep": "Переславле-Залесском"},
    "sight.default": {"dwell": "Полтора часа"},
    "sight.dog_waits": {"dwell": "Полтора часа"},
    "sight.dog_ok": {"dwell": "Полтора часа"},
    "start.default": {"time": "08:00"},
    "finish.home": {"part_of_day": "вечеру"},
    "stage.split": {"n": 3, "days_word": "дня", "km": 250},
    "stage.split_ring": {"n": 3, "days_word": "дня", "km": 250},
    "stage.fuel": {"consumption": "8"},
    "warning.FUEL_GAP": {"km": 300},
    "warning.DAY_OVER_BUDGET": {"day": 2},
    "warning.STOP_CLOSED": {"name": "Ясная Поляна"},
}

EMPTY_ALLOWED = {"crew_suffix.none"}


class TemplatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.t = ReasonTemplates.default()

    def test_json_has_exactly_the_keys(self) -> None:
        with (RESOURCES / "reasons.ru.json").open(encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual(sorted(raw), sorted(TEMPLATE_KEYS))
        self.assertEqual(len(TEMPLATE_KEYS), len(set(TEMPLATE_KEYS)))

    def test_every_template_renders(self) -> None:
        for key in TEMPLATE_KEYS:
            with self.subTest(key=key):
                params = DOC_PARAMS.get(key, {})
                self.assertEqual(placeholders(self.t.raw(key)), frozenset(params))
                out = self.t.render(key, **params)
                if key not in EMPTY_ALLOWED:
                    self.assertTrue(out.strip())
                self.assertNotIn("{", out)
                self.assertNotIn("}", out)

    def test_missing_param_and_key_raise(self) -> None:
        with self.assertRaises(KeyError):
            self.t.render("fuel.range")
        with self.assertRaises(KeyError):
            self.t.render("no.such.key")

    def test_shift_hotels_example(self) -> None:
        shift = self.t.render("overnight.shift.later", other_prep="Ростове", dkm=55)
        text = self.t.render(
            "overnight.shift.hotels", shift=shift, crew_suffix=self.t.render("crew_suffix.dog")
        ) + self.t.render("overnight.cap_ok", daily_km=300)
        self.assertEqual(
            text,
            "Не в Ростове, а на 55 км дальше: здесь больше отелей, куда пускают с собакой. "
            "Ваши 300 км в день не превышены.",
        )

    def test_rendered_reasons_are_capitalised(self) -> None:
        self.assertEqual(self.t.render("sight.default", dwell="полтора часа"), "Полтора часа на осмотр.")
        self.assertEqual(
            self.t.render("sight.dog_waits", dwell="час"), "Час на осмотр. Собака ждёт с одним из взрослых."
        )
        for key in TEMPLATE_KEYS:
            with self.subTest(key=key):
                out = self.t.render(key, **DOC_PARAMS.get(key, {}))
                if out and out[0].isalpha():
                    self.assertTrue(out[0].isupper())
        # fragments that start with a space or comma are left as they are
        self.assertEqual(self.t.render("overnight.cap_ok", daily_km=300), " Ваши 300 км в день не превышены.")
        self.assertEqual(self.t.render("crew_suffix.family"), " с семейными номерами")

    def test_rest_minutes_plural(self) -> None:
        from verst_planner.explain.ru import minutes_word

        cases = {1: "минута", 2: "минуты", 5: "минут", 15: "минут", 20: "минут", 21: "минута", 22: "минуты"}
        for n, word in cases.items():
            with self.subTest(n=n):
                out = self.t.render("rest.who", min=n, min_word=minutes_word(n), who="собаке погулять")
                self.assertEqual(out, f"Разминка {n} {word}: собаке погулять.")
        self.assertNotIn("21 минут:", self.t.render("rest.who", min=21, min_word=minutes_word(21), who="x"))

    def test_from_dict_validates(self) -> None:
        good = {k: self.t.raw(k) for k in TEMPLATE_KEYS}
        self.assertEqual(ReasonTemplates.from_dict(good).keys(), TEMPLATE_KEYS)
        with self.assertRaises(ValueError):
            ReasonTemplates.from_dict({k: v for k, v in good.items() if k != "fuel.last"})
        with self.assertRaises(ValueError):
            ReasonTemplates.from_dict({**good, "extra": "x"})


if __name__ == "__main__":
    unittest.main()
