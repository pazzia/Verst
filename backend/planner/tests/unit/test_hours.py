import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from verst_planner.domain.errors import OpeningHoursParseError
from verst_planner.hours import parse

# 2026-10-26 is a Monday
MON, TUE, WED, THU, FRI, SAT, SUN = (datetime(2026, 10, 26) + timedelta(days=i) for i in range(7))


def at(day: datetime, hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return day.replace(hour=int(h), minute=int(m))


# (opening_hours, day, time, expected is_open)
IS_OPEN_CASES = [
    ("24/7", MON, "03:00", True),
    ("24/7", SUN, "23:59", True),
    ("Mo-Su 09:00-18:00", WED, "09:00", True),
    ("Mo-Su 09:00-18:00", WED, "08:59", False),
    ("Mo-Su 09:00-18:00", WED, "18:00", False),
    ("Mo-Su 09:00-18:00", WED, "17:59", True),
    ("Tu-Su 10:00-17:00", MON, "12:00", False),
    ("Tu-Su 10:00-17:00", TUE, "12:00", True),
    ("Tu-Su 10:00-17:00", SUN, "16:59", True),
    ("Mo-Fr 08:00-20:00; Sa,Su 10:00-18:00", FRI, "08:30", True),
    ("Mo-Fr 08:00-20:00; Sa,Su 10:00-18:00", SAT, "08:30", False),
    ("Mo-Fr 08:00-20:00; Sa,Su 10:00-18:00", SUN, "17:00", True),
    ("Mo-Su 10:00-14:00,15:00-19:00", THU, "14:30", False),
    ("Mo-Su 10:00-14:00,15:00-19:00", THU, "15:30", True),
    ("Fr-Sa 18:00-02:00", SAT, "01:00", True),
    ("Fr-Sa 18:00-02:00", SUN, "01:00", True),
    ("Fr-Sa 18:00-02:00", FRI, "01:00", False),
    ("Fr-Sa 18:00-02:00", MON, "01:00", False),
    ("Mo-Su 09:00-18:00; Mo off", MON, "12:00", False),
    ("Mo-Su 09:00-18:00; Mo off", TUE, "12:00", True),
    ("Mo-Su 00:00-24:00", TUE, "00:00", True),
    ("Mo-Su 00:00-24:00", TUE, "23:59", True),
    ("Mo-Su 09:00-18:00; PH off", MON, "12:00", True),
    ("10:00-16:00", SAT, "11:00", True),
    ("Fr-Mo 12:00-13:00", SUN, "12:30", True),
    ("Fr-Mo 12:00-13:00", TUE, "12:30", False),
    ("Mo-Fr 09:00-18:00; Sa closed", SAT, "12:00", False),
    ("Mo,We,Fr 09:00-12:00", WED, "10:00", True),
    ("Mo,We,Fr 09:00-12:00", THU, "10:00", False),
]

BAD = [
    "sunrise-sunset",
    "Mo-Fr 09:00+",
    "Jan-Mar 10:00-18:00",
    "Mo-Fr 9:00-18:00",
    "Mo-Fr 09:00-25:00",
    "Mo-Fr",
    "",
    "PH off",
    "Mo-Fr 10:00-10:00",
    "Mo-Fr 24:00-02:00",
]


class HoursTest(unittest.TestCase):
    def test_is_open_table(self) -> None:
        self.assertGreaterEqual(len(IS_OPEN_CASES), 20)
        for src, day, hhmm, expected in IS_OPEN_CASES:
            with self.subTest(src=src, day=day.strftime("%a"), t=hhmm):
                self.assertEqual(parse(src).is_open(at(day, hhmm)), expected)

    def test_unsupported_raises(self) -> None:
        for src in BAD:
            with self.subTest(src=src), self.assertRaises(OpeningHoursParseError):
                parse(src)

    def test_sunrise_sunset_raises(self) -> None:
        with self.assertRaises(OpeningHoursParseError):
            parse("sunrise-sunset")

    def test_covers(self) -> None:
        h = parse("Mo-Su 10:00-11:00")
        self.assertFalse(h.covers(at(MON, "10:00"), at(MON, "11:30")))
        self.assertTrue(h.covers(at(MON, "10:00"), at(MON, "11:00")))
        self.assertFalse(h.covers(at(MON, "09:59"), at(MON, "10:30")))
        self.assertFalse(h.covers(at(MON, "10:30"), at(MON, "10:20")))
        split = parse("Mo-Su 10:00-14:00,15:00-19:00")
        self.assertFalse(split.covers(at(TUE, "13:30"), at(TUE, "15:30")))
        night = parse("Fr-Sa 18:00-02:00")
        self.assertTrue(night.covers(at(FRI, "23:00"), at(SAT, "01:30")))
        self.assertTrue(night.covers(at(SAT, "23:00"), at(SUN, "02:00")))
        self.assertFalse(night.covers(at(SAT, "23:00"), at(SUN, "02:30")))
        allday = parse("Mo-Su 00:00-24:00")
        self.assertTrue(allday.covers(at(MON, "23:00"), at(TUE, "01:00")))
        self.assertTrue(parse("24/7").covers(at(MON, "00:00"), at(SUN, "23:00")))
        self.assertTrue(parse("24/7").always)
        self.assertFalse(h.always)

    def test_visit_must_fit_hours(self) -> None:
        h = parse("Tu-Su 09:00-17:00")
        self.assertFalse(h.covers(at(SAT, "16:30"), at(SAT, "17:30")))
        self.assertTrue(h.covers(at(SAT, "15:30"), at(SAT, "16:30")))

    def test_aware_datetime_uses_wall_clock(self) -> None:
        h = parse("Mo-Su 09:00-18:00")
        self.assertTrue(h.is_open(at(MON, "10:00").replace(tzinfo=ZoneInfo("Europe/Samara"))))
        self.assertFalse(h.is_open(at(MON, "08:00").replace(tzinfo=ZoneInfo("Europe/Moscow"))))


if __name__ == "__main__":
    unittest.main()
