"""Packaged JSON resources (config, reason templates, Russian strings), read zip-safely (DEV-110).

On Android, Chaquopy imports the app's Python code from an archive inside the APK, where
`Path(__file__).open()` fails with `NotADirectoryError`. Every resource read goes through `read_text`.
It uses `importlib.resources`, which works for directories and zip archives alike, and falls back to the
file next to this module when the loader offers no resource reader.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

DIR = Path(__file__).resolve().parent
"""Directory of the resources on a normal file system (used by `cli export-config` only)."""


def read_text(name: str) -> str:
    """The UTF-8 text of resource `name` (e.g. ``"planner_config.json"``)."""
    try:
        return resources.files(__name__).joinpath(name).read_text("utf-8")
    except (TypeError, AttributeError, NotImplementedError, ModuleNotFoundError):
        return (Path(__file__).parent / name).read_text("utf-8")


__all__ = ["DIR", "read_text"]
