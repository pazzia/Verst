"""A§3.1 dependency rules, enforced with `ast` (DEV-018).

1. `verst_planner` imports only the standard library and itself.
2. Inside the package: `domain` imports only `domain`; `geo` only `domain`/`geo`; `pipeline` may import
   `domain, geo, hours, config, ports, events, explain`; `cost` imports `domain, config, explain.ru`;
   `adapters.fake` imports `domain, geo, ports`; Sprint 3: `catalogue` imports `domain, resources`;
   `adapters.catalogue` imports `domain, geo, ports, adapters.fake, catalogue, explain.ru, resources`; `city`
   imports `domain, geo, hours, events, explain.ru`; `handoff` imports nothing internal. The composition roots
   `engine`, `cli` and `mobile` may import everything.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "verst_planner"
STDLIB = set(sys.stdlib_module_names) | {"__future__"}

# module prefix → allowed internal prefixes (besides itself)
RULES: dict[str, tuple[str, ...]] = {
    "verst_planner.domain": ("verst_planner.domain",),
    "verst_planner.geo": ("verst_planner.domain", "verst_planner.geo"),
    "verst_planner.hours": ("verst_planner.domain", "verst_planner.hours"),
    "verst_planner.config": ("verst_planner.domain", "verst_planner.config", "verst_planner.resources"),
    "verst_planner.resources": ("verst_planner.resources",),
    "verst_planner.ports": ("verst_planner.domain", "verst_planner.ports"),
    "verst_planner.events": ("verst_planner.domain", "verst_planner.events"),
    "verst_planner.explain": (
        "verst_planner.domain",
        "verst_planner.config",
        "verst_planner.explain",
        "verst_planner.resources",
    ),
    "verst_planner.pipeline": (
        "verst_planner.domain",
        "verst_planner.geo",
        "verst_planner.hours",
        "verst_planner.config",
        "verst_planner.ports",
        "verst_planner.events",
        "verst_planner.explain",
        "verst_planner.pipeline",
    ),
    "verst_planner.cost": (
        "verst_planner.domain",
        "verst_planner.config",
        "verst_planner.explain.ru",
        "verst_planner.cost",
    ),
    "verst_planner.adapters.fake": (
        "verst_planner.domain",
        "verst_planner.geo",
        "verst_planner.ports",
        "verst_planner.adapters.fake",
    ),
    # Sprint 3 (ADR-0012…0014)
    "verst_planner.catalogue": ("verst_planner.domain", "verst_planner.resources", "verst_planner.catalogue"),
    "verst_planner.adapters.catalogue": (
        "verst_planner.domain",
        "verst_planner.geo",
        "verst_planner.ports",
        "verst_planner.adapters.fake",
        "verst_planner.adapters.catalogue",
        "verst_planner.catalogue",
        "verst_planner.explain.ru",
        "verst_planner.resources",
        "verst_planner.parking",
    ),
    # Sprint 4 (ADR-0015 §4): the static parking model
    "verst_planner.parking": (
        "verst_planner.domain",
        "verst_planner.geo",
        "verst_planner.resources",
        "verst_planner.cost.money",
        "verst_planner.parking",
    ),
    "verst_planner.city": (
        "verst_planner.domain",
        "verst_planner.geo",
        "verst_planner.hours",
        "verst_planner.events",
        "verst_planner.explain.ru",
        "verst_planner.city",
    ),
    "verst_planner.handoff": (),
}


def module_name(path: Path) -> str:
    rel = path.relative_to(PKG.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend((node.lineno, a.name) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative imports are not used in the package
                out.append((node.lineno, "." * node.level + (node.module or "")))
            elif node.module:
                for alias in node.names:
                    sub = f"{node.module}.{alias.name}"
                    out.append((node.lineno, sub if _is_module(sub) else node.module))
    return out


def _is_module(name: str) -> bool:
    """`from pkg import sub` names the submodule `pkg.sub` when such a file or package exists."""
    if not name.startswith("verst_planner."):
        return False
    rel = Path(*name.split(".")[1:])
    return (PKG / rel).with_suffix(".py").exists() or (PKG / rel / "__init__.py").exists()


def rule_for(mod: str) -> tuple[str, ...] | None:
    for prefix in sorted(RULES, key=len, reverse=True):
        if mod == prefix or mod.startswith(prefix + "."):
            return RULES[prefix]
    return None


def allowed(target: str, prefixes: tuple[str, ...]) -> bool:
    return any(target == p or target.startswith(p + ".") for p in prefixes)


class LayeringTest(unittest.TestCase):
    def modules(self) -> list[Path]:
        files = sorted(PKG.rglob("*.py"))
        self.assertGreater(len(files), 40)
        return files

    def test_stdlib_only(self) -> None:
        for path in self.modules():
            for line, name in imports(path):
                top = name.split(".")[0]
                with self.subTest(module=module_name(path), line=line, imported=name):
                    self.assertFalse(name.startswith("."), "relative import")
                    self.assertTrue(top in STDLIB or top == "verst_planner", f"non-stdlib import {name}")

    def test_internal_rules(self) -> None:
        checked = 0
        for path in self.modules():
            mod = module_name(path)
            rule = rule_for(mod)
            if rule is None:  # engine, cli, package root: may import everything
                continue
            for line, name in imports(path):
                if not name.startswith("verst_planner"):
                    continue
                checked += 1
                with self.subTest(module=mod, line=line, imported=name):
                    self.assertTrue(allowed(name, rule), f"{mod} must not import {name}")
        self.assertGreater(checked, 50)

    def test_mobile_is_a_composition_root(self) -> None:
        """DEV-111: `mobile` (like `cli`, `engine`) may import every subpackage, only stdlib outside."""
        for mod in ("verst_planner.mobile", "verst_planner.cli", "verst_planner.engine"):
            self.assertIsNone(rule_for(mod), mod)
        names = {n for _line, n in imports(PKG / "mobile.py")}
        self.assertTrue(any(n == "verst_planner.engine" for n in names))

    def test_engine_uses_public_context(self) -> None:
        """A§16.1 #4 (R-10): `engine.py` reaches `PlanContext` only through its public API."""
        import re

        src = (PKG / "engine.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"ctx\._\w+", src), [])

    def test_detects_violations(self) -> None:
        self.assertFalse(allowed("verst_planner.cost.model", RULES["verst_planner.pipeline"]))
        self.assertFalse(allowed("verst_planner.geo.index", RULES["verst_planner.domain"]))
        self.assertTrue(allowed("verst_planner.explain.ru", RULES["verst_planner.cost"]))
        self.assertFalse(allowed("verst_planner.explain.templates", RULES["verst_planner.cost"]))
        self.assertNotIn("pydantic", STDLIB)


if __name__ == "__main__":
    unittest.main()
