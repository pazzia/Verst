import threading
import unittest

from verst_planner.domain.enums import SignType, StageKey, StopKind
from verst_planner.domain.errors import PlanCancelled
from verst_planner.events import NEVER, NULL_SINK, CancelToken, ListSink, StageEvent, StopEvent, event_to_json


class EventsTest(unittest.TestCase):
    def test_list_sink_collects_in_order(self) -> None:
        sink = ListSink()
        a = StageEvent(StageKey.SPLIT, "Прокладываем дорогу", 0.05)
        b = StopEvent(1, "night1", StopKind.OVERNIGHT, SignType.HOTEL, "Ярославль", 265, True)
        c = StageEvent(StageKey.COST, "Считаем, сколько стоит поездка", 0.9)
        for e in (a, b, c):
            sink.emit(e)
        self.assertEqual(sink.events, [a, b, c])
        NULL_SINK.emit(a)  # no-op

    def test_cancel_token(self) -> None:
        t = CancelToken()
        t.check()
        self.assertFalse(t.is_cancelled())
        t.cancel()
        self.assertTrue(t.is_cancelled())
        with self.assertRaises(PlanCancelled):
            t.check()

    def test_cancel_from_thread(self) -> None:
        t = CancelToken()
        th = threading.Thread(target=t.cancel)
        th.start()
        th.join(timeout=5)
        self.assertTrue(t.is_cancelled())
        with self.assertRaises(PlanCancelled):
            t.check()

    def test_never_token(self) -> None:
        NEVER.check()
        self.assertFalse(NEVER.is_cancelled())
        with self.assertRaises(RuntimeError):
            NEVER.cancel()
        NEVER.check()

    def test_event_json(self) -> None:
        self.assertEqual(
            event_to_json(StageEvent(StageKey.SPLIT, "Прокладываем дорогу", 0.05)),
            {"event": "stage", "key": "split", "text": "Прокладываем дорогу", "progress": 0.05},
        )
        stop = event_to_json(
            StopEvent(1, "night1", StopKind.OVERNIGHT, SignType.HOTEL, "Ярославль", 265, True)
        )
        self.assertEqual(stop["day"], 1)
        self.assertEqual(
            stop["stop"],
            {
                "id": "night1",
                "kind": "overnight",
                "sign": "hotel",
                "name": "Ярославль",
                "kmAt": 265,
                "provisional": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
