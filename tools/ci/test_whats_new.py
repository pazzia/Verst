"""Unit tests of tools/ci/whats_new.py (run: python3 -m unittest tools/ci/test_whats_new.py)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import whats_new  # noqa: E402


class WhatsNewTest(unittest.TestCase):
    def test_trailers_newest_first_deduplicated(self) -> None:
        bodies = [
            "Fix x\n\nbody\n\nТестерам: кнопка «Готово» стала заметнее.\nCo-Authored-By: a",
            "Feature y\n\nТестерам: в настройках можно выбрать дизайн\nТестерам: Кнопка «Готово» стала заметнее",
            "Refactor z\n\nno trailer",
        ]
        self.assertEqual(
            ["кнопка «Готово» стала заметнее", "в настройках можно выбрать дизайн"],
            whats_new.items(bodies, 25),
        )

    def test_previous_commit_from_both_note_kinds(self) -> None:
        sha = "a" * 40
        self.assertEqual(sha, whats_new.previous_commit(f"- Коммит: {sha}\n"))
        self.assertEqual(sha, whats_new.previous_commit(f"- Собрано из коммита {sha} (метка …)"))
        self.assertIsNone(whats_new.previous_commit("Изменения: ручной запуск"))

    def test_render(self) -> None:
        self.assertEqual("**Что нового:**\n- a.\n- b.", whats_new.render(["a", "b"], True))
        self.assertIn("видимых изменений нет", whats_new.render([], True))


if __name__ == "__main__":
    unittest.main()
