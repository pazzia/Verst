"""ProviderSelector (ADR-0021 §2.3): pick providers per capability and country from the manifest.

Filter: coverage, configured key, entity, health, remaining budget. Rank: country priority (higher first), then
cost. The chain always ends in a provider with no key and no entity (open data), so a plan never depends on a
vendor. Every decision carries a reason, for the report and the plan log.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class Choice:
    provider: str
    usable: bool
    reason: str
    priority: int


@dataclass
class ProviderSelector:
    manifest: dict[str, Any]
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    unhealthy: set[str] = field(default_factory=set)
    spent_rub: dict[str, float] = field(default_factory=dict)
    budgets_rub: dict[str, float] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path, **kw: Any) -> "ProviderSelector":
        return cls(json.loads(path.read_text(encoding="utf-8")), **kw)

    @property
    def providers(self) -> list[dict[str, Any]]:
        return list(self.manifest["providers"])

    def provider(self, pid: str) -> dict[str, Any]:
        return next(p for p in self.providers if p["id"] == pid)

    def key_name(self, p: dict[str, Any], country: str) -> str | None:
        k = p.get("envKey")
        return k.replace("{COUNTRY}", country) if k else None

    def _check(self, p: dict[str, Any], capability: str, country: str) -> Choice | None:
        if capability not in p["capabilities"]:
            return None
        prio = int(p.get("priority", {}).get(country, p.get("priority", {}).get("*", 0)))
        cov = p["coverage"]
        if not ("world" in cov or country in cov) or country in p.get("excluded", []):
            return None
        entities = set(self.manifest.get("deployment", {}).get("entities", []))
        need = p["licence"].get("needsEntity", "none")
        if need != "none" and need not in entities:
            return Choice(p["id"], False, f"needs a {need} legal entity", prio)
        key = self.key_name(p, country)
        if key and not self.env.get(key):
            return Choice(p["id"], False, f"not configured ({key} unset)", prio)
        if p["id"] in self.unhealthy:
            return Choice(p["id"], False, "unhealthy", prio)
        budget = self.budgets_rub.get(p["id"])
        if budget is not None and self.spent_rub.get(p["id"], 0.0) >= budget:
            return Choice(p["id"], False, "monthly budget spent", prio)
        return Choice(p["id"], True, "ok", prio)

    def chain(self, capability: str, country: str) -> list[Choice]:
        """All candidate providers for (capability, country), best first; usable ones before unusable ones."""
        found = [c for p in self.providers if (c := self._check(p, capability, country)) is not None]
        return sorted(found, key=lambda c: (not c.usable, -c.priority, c.provider))

    def pick(self, capability: str, country: str) -> Choice:
        usable = [c for c in self.chain(capability, country) if c.usable]
        if not usable:
            raise LookupError(f"no usable provider for {capability} in {country}")
        return usable[0]

    def would_pick_if_licensed(self, capability: str, country: str) -> dict[str, Any] | None:
        """The best commercial provider ignoring keys and entities: what the cost simulation prices."""
        best = None
        for p in self.providers:
            if capability not in p["capabilities"] or not p.get("cost"):
                continue
            cov = p["coverage"]
            if not ("world" in cov or country in cov) or country in p.get("excluded", []):
                continue
            prio = int(p.get("priority", {}).get(country, p.get("priority", {}).get("*", 0)))
            if p["cost"].get("search") is None:
                continue
            if best is None or prio > best[0]:
                best = (prio, p)
        return best[1] if best else None

    def call_cost_rub(self, p: dict[str, Any], method: str, calls: int) -> float:
        c = p["cost"]
        per = c.get(method)
        if per is None:
            return float("nan")
        rate = self.manifest.get("deployment", {}).get("usdRub", 1.0) if c.get("currency") == "USD" else 1.0
        return calls * per * rate
