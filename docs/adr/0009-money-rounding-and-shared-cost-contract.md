# ADR-0009: Decimal money, fixed rounding rules and a shared Python/Kotlin cost-recompute contract

Status: Accepted · Date: 2026-10-23 · Refs: SPEC §8, §13; architecture §7

## Context
SPEC requires lines rounded to 10 ₽, totals to 100 ₽, the formula string for each line, and on-device recomputation after replacing a stop, toggling the reserve or changing the crew — offline, ≤ 100 ms — with the server recomputing on save. Two implementations of the same arithmetic will drift unless pinned.

## Decision
- Python uses `decimal.Decimal` with `ROUND_HALF_UP`; Kotlin uses `java.math.BigDecimal` with `RoundingMode.HALF_UP`. Rounding order: round each line to 10, reserve = round10(10 % × Σ rounded lines), total = round100(Σ + reserve), per person = round100(total / people).
- The trip carries `cost.units` (all unit prices and quantities). `verst_planner.cost.recompute` is the reference algorithm; Android's `CostCalculator` is a port.
- A JSON contract file (`backend/planner/tests/contract/cost_recompute_cases.json`, ≥ 25 cases) is executed by both test suites; golden snapshots also assert `recompute(units) == cost`.

## Consequences
- Offline Waybill numbers equal the server's to the rouble.
- Changing a cost rule requires updating both implementations and the contract file in one change.

## Alternatives
- Floats — rounding drift at .5 boundaries.
- Server-only recompute — breaks offline replace and the 100 ms target.
