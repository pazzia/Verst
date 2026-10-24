# ADR-0011: The engine fits the plan to the budget, or says it does not fit

Status: Accepted (Architect) · Date: 2026-10-24 · Refs: CEO Sprint 3 requirement 1; Manager decision D1; A§6.5, A§7, A§16.9; ADR-0009; `docs/backlog-sprint3.md` ARCH-301

## Context

Today the budget is an input that the engine only reports against. `cost.overBudget` and three hints («дешевле ночёвка», «меньше платных мест», «просто доехать») are produced after the plan has been built. Nothing in stages 0–11 reads the budget.

The CEO tested this on mvp-mock-37: «Золотое кольцо», 4 adults + 1 child + dog, budget 30 000 ₽. The result was 61 100 ₽ with an overrun of 31 100 ₽, presented as a normal trip. On the golden clock the same input gives 58 400 ₽:

| Line | ₽ |
| --- | --- |
| fuel (761 km) | 3 760 |
| lodging (2 nights × 2 rooms × 6 000) | 24 000 |
| food (5 meals × 5 people × ≈ 750) | 18 750 |
| tickets (4 paid sights) | 6 600 |
| reserve | 5 310 |

A trip like this must either be brought within the budget, or be clearly marked as not fitting.

## Manager decision D1 (binding)

- **Target:** total ≤ budget. A *small overrun* is tolerated. Tolerance = **≤ 5 % and ≤ 3 000 ₽**, so `allowed = budget + min(round(0.05·budget), 3000)`. For a budget of 30 000 ₽, `allowed` = 31 500 ₽.
- **Levers, in this order:**
  1. cheaper hotel options and fewer rooms (family rooms);
  2. a cheaper food tier;
  3. prefer free sights and drop paid ones;
  4. fewer nights / shorter days;
  5. for ready routes, a shortened variant.
- **Doesn't fit:** if even the minimum exceeds the tolerance, the result is a distinct «doesn't fit» outcome. It contains the minimum achievable cost and 2–3 concrete options: raise the budget to X, shorten to N days, or a cheaper nearby route. It is never presented as a normal plan.
- **No budget:** budget «не важно» (null) means no fitting.
- **Alternatives:** replace alternatives that break the budget are flagged.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| (a) Cost-aware objective inside every stage (one pass, a price term in every score) | One plan run | Changes every stage, every golden and every tie. Hard to explain («why this hotel?») and hard to order the levers as D1 requires |
| (b) Post-plan cost patches only (cheapest hotel, drop tickets) via `recompute_cost` | Cheap, no re-plan | Cannot change food stops, sights, nights or the route. The CEO case still misses by far |
| **(c) Ladder of re-plans with knobs, cheapest-change-first, early exit** | Follows D1's lever order literally. Each step is the existing deterministic pipeline with one more knob, so it can be explained per lever. Goldens are untouched when the first plan fits | Up to 6 plan runs for an over-budget trip. On-device ≈ 0.2–0.6 s each, hidden by the Drive timeline (5.4 §6) |

## Decision

**(c).** A new stage 12b, `pipeline/budget_fit.py`, is called by `Planner.plan` after cost, only when `budget_rub is not None` and the first plan's total > budget.

### Knobs (`FitKnobs`, frozen dataclass; all default off = today's behaviour)

| Knob | Effect inside the existing stages |
| --- | --- |
| `lodging_cheap` | Stage 5 town score gains `−w_price · night_cost(town)/1000`, where `night_cost` = the cheapest passing option × rooms. Hotel choice inside the town = the minimum `rooms(h) × price(h)` among passing lodgings (ties → the current `hotel_score`). Crew filters (dog, family) still apply, so a dog trip never gets a hotel without `dogs_allowed` |
| `family_rooms` | `rooms(h, crew)` = `min(ceil(adults/2), ceil((adults+children)/4))` when `family_room ∈ h.tags`, priced at `h.family_price_rub` (default `price_night_rub × 1.4`, rounded to 100). Otherwise unchanged (`ceil(adults/2)`, children share) |
| `food_economy` | Stage 8 lunch picks: the lowest `avg_check_rub` among candidates within the lunch window (ties → current score). Default checks (dinner, breakfast, lunch without a check) are multiplied by `food_economy_factor` = 0.75. The reason text says «кафе попроще» |
| `sights_free` | Stage 9 accepts only sights with zero tickets for this crew (`free_entry`, or null/zero prices). Paid sights move to the alternatives pool. Fixed template stops (`role = stop`) stay |
| `fewer_nights` | Free A→B trips and free round trips with ≥ 2 days only. Raise `daily_km` in steps of 50 up to `min(1.3 × daily_km, daily_km_max)` until `n_days` drops by one. Rejected if the resulting plan has a `DAY_OVER_BUDGET` warning that the previous step did not have |
| `variant` | Ready routes only: the template's shortest `variants[]` entry, a hidden ready route with `parentId` (fixtures extended: «Золотое кольцо» gets a 2-day variant; Ярославль and Тула are already 2 days). Not used when `days_min` of the parent equals the variant's days |

### Ladder (cumulative; each step is a full `plan` with the knobs so far)

```
S0 = plan()                                        # today's plan
S1 = S0 + lodging_cheap + family_rooms             # D1 lever 1
S2 = S1 + food_economy                             # lever 2
S3 = S2 + sights_free                              # lever 3
S4 = S3 + fewer_nights        (skipped if not applicable)
S5 = S4 + variant             (ready routes with a variant)
```

- **Fits:** stop at the first step with `total ≤ budget`.
- **Small overrun:** if no step gets ≤ budget, take the **earliest** step with `total ≤ allowed`. Earliest means fewest levers, i.e. the least change to the trip.
- **Doesn't fit:** otherwise the outcome is `no_fit` with `minimum` = the cheapest step.
- **Monotonicity guard:** a step that is not cheaper than the previous one is still kept as the base for the next step, but is never the answer when an earlier step is cheaper.
- **Cancellation:** `cancel.check()` runs between steps. Progress: one extra stage event «Подбираем под бюджет: {lever}» at 0.92.

### Output (plan codec, additive; omitted when S0 fits or there is no budget, so the golden snapshots stay byte-identical)

```jsonc
"budgetFit": {
  "status": "fits" | "small_overrun",
  "budgetRub": 30000, "allowedRub": 31500,
  "initialTotalRub": 58400, "totalRub": 29800,
  "levers": [{"code": "lodging_cheap", "savedRub": 6000}, {"code": "food_economy", "savedRub": 4700}, …],
  "textRu": "Подогнали под бюджет: дешевле ночёвки, кафе попроще, бесплатные места.",
  "variantOf": null | "rr_golden_ring"
}
```

`savedRub` of a lever = the total of the previous step minus the total of this step. Each saving is shown on the Waybill as a line under the total.

### «Doesn't fit» outcome (mobile envelope, not a trip)

```jsonc
{"ok": true, "result": {
  "outcome": "no_fit",
  "budgetRub": 30000, "allowedRub": 31500,
  "minimum": {"totalRub": 41200, "levers": [...], "trip": <private trip of the cheapest step>, "shareText": "…", …name maps},
  "options": [
    {"kind": "raise_budget", "budgetRub": 42000},
    {"kind": "shorten", "days": 2, "totalRub": 29700, "readyRouteId": "rr_golden_ring_short", "titleRu": "Золотое кольцо · коротко"},
    {"kind": "cheaper_route", "totalRub": 24300, "readyRouteId": "rr_yaroslavl", "titleRu": "Ярославль"}
  ],
  "textRu": "В 30 000 ₽ эта поездка не помещается даже в самом экономном варианте — минимум ≈ 41 200 ₽."
}}
```

- Each option also carries `fits`. When no shorten or cheaper-route candidate fits the tolerance, the cheapest candidate that is still cheaper than the minimum is offered with `fits: false`: a concrete number, not a promise. A lever that saved nothing is not listed in `levers` or in the text.

A normal plan result carries `"outcome": "plan"` next to `trip`. That key is new, and `API_VERSION` becomes 2.
- **Options.** Each option is verified by an actual (fitted) plan, so its number is the engine's number. The search stops after 8 extra plan runs.
  - `raise_budget`: always present. `budgetRub` = minimum total rounded **up** to 1 000.
  - `shorten`:
    - ready route: its variant, if not already used;
    - free trip: the next shorter `n_days` (S4 with a larger `daily_km`), if that fits.
  - `cheaper_route`:
    - ready route: another ready route of the same hub, cheapest fitted plan first;
    - free trip: a catalogue town in the same direction (bearing ±30°) at 40–75 % of the distance, with population ≥ 20 000 and a passing lodging. At most 5 towns are tried, nearest-to-60 % first.
  - At most 3 options are returned, in this order: shorten, cheaper_route, raise_budget. Any option whose plan does not fit is dropped.
- **The app:** shows the distinct «Не помещается в бюджет» screen (DES-300). The `minimum` trip opens only through an explicit «Показать самый экономный вариант» and is then marked as over budget everywhere.
- **`estimate`** runs the same ladder (it is the plan), and returns `{km, days, outcome, totalRub}` so Instruments can show the fit before ПОЕХАЛИ.

### Alternatives flagged

When a budget is set, every `Alternative` gets `breaksBudget: true` if `recompute(units, overrides = {replaced: alt})` > `allowed`; the flag is omitted when false. `replace_stop` recomputes the flags of the new day. A replace the user confirms is allowed; the Waybill then shows the overrun as today.

### Cost model changes (shared contract, ADR-0009)

`NightUnit` gains `rooms: int | None` and `HotelPrice` gains `rooms: int | None`. Both are the room count the engine chose for that option (family rooms); `None` means the legacy `ceil(adults/2)`.

- `recompute` uses `rooms × price` with these values. A crew patch (`patch_cost {crew}`) recomputes the room counts in the engine; the device never changes the crew locally.
- `cost_recompute_cases.json` gains cases for explicit rooms. The Kotlin `CostCalculator` ports the rule (DEV-303); the old cases are unchanged.

A budget patch (`patch_cost {budget}`) stays cost-only: no re-fit. The Waybill's over-budget state offers «Подогнать под бюджет», which re-plans with the new budget and opens Drive.

## As built (ARCH-301, `arch/sprint-3`)

- **Code:** `verst_planner/fit.py` (ladder, tolerance, options, `flag_alternatives`) and `domain/rooms.py` (family room plan). The knobs live in `PlanContext.knobs` and are used by stages 5 (`rank_hotels`, the town price term `W_PRICE = 0.5` per 1 000 ₽), 8 (`lunch_score` economy term; `_EconomyPrices` x 0.75 on default checks; the cheapest town check instead of the median) and 9 (`is_paid` filter).
- **Entry point:** `Planner.plan` always fits; when the trip cannot fit, it raises `fit.NoFit` (code `NO_FIT`, never surfaced as an error by the bridge).
- **G13 «ceo_budget_fit»** (golden clock, start 2026-11-07): the plain plan is 58 400 ₽. The fitted plan is the 2-day «Золотое кольцо · коротко» at **27 400 ₽** (`fits`). Levers: economy food −2 700, free sights −5 600, variant −22 700. Cheaper hotels and family rooms saved 0: there is one dog-friendly family hotel per town, and 2 standard rooms tie with ceil(5/4) = 2 family rooms.
- **Fixture:** `central_russia_v1` gains the hidden ready route `rr_golden_ring_short` (`parentId`). G01–G12 are byte-identical; DEV-112 bundles gain `G13` only.

## Consequences

- The CEO case ends ≤ 31 500 ₽ or as `no_fit` with options. This is ARCH-301 acceptance, also a golden case G13 (new; the existing G01–G12 are unchanged because they fit or have no budget).
- Plan latency for over-budget trips: up to 6 runs plus ≤ 8 for options. The worst case on the CEO phone is estimated at ~4 s. The Drive timeline already shows ≥ 2.4 s of steps. The `estimate` that precedes the plan warms the N-10 km cache only for S0; the fitter's steps are not cached. Budget at 2× plan time; measured by e2e `budgets.json` (DEV-309).
- The Kotlin side changes:
  - the `CostCalculator` rooms rule;
  - `PlanResultDto.outcome`;
  - the `budgetFit` DTO;
  - `AlternativeDto.breaksBudget`;
  - the no-fit screen.

## Risks

| Risk | Mitigation |
| --- | --- |
| Cheapest hotel choice picks an obviously worse hotel | `lodging_cheap` only runs when the trip is over budget. Options keep the top-3 by price, so the user can still choose the nicer one on 5.7, and that choice is shown as an overrun |
| `fewer_nights` creates long, tiring days | Capped at 1.3 × `daily_km` and `daily_km_max`. Rejected when it adds `DAY_OVER_BUDGET` |
| Option search is slow on the phone | Bounded at 8 runs; each step is cancellable; the timing is in `budgets.json` |
