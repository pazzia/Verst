# ADR-0019: Unknown is not a default — the engine follow-ups E-1…E-6

Status: **Accepted (Architect)** · Date: 2026-10-26 · Backlog: investor-readiness / trust fixes ·
Refs: ADR-0018 §10 (E-1…E-6), ADR-0011 (budget fitting), ADR-0015 §3–§6, A§6.9, A§7, `docs/curation/checklist.md`
§2.4, §3, §4; DB migration 0002 (`core.place_tag`, `core.place_fuel`, nullable `breakfast_included`)

## 1. Context

ADR-0018 §10 listed six places where the engine read a missing fact as a convenient one. Each one can make the
app say something false: «вход свободный» for a museum whose price nobody checked, a cheaper trip because a
breakfast was assumed, a fuel stop that may not sell the car's fuel. The DB side is done (0002 stores «unknown»).
This ADR makes the engine and the app carry «unknown» too.

Constraints: feature freeze (no new features, only truthful existing info); the engine is stdlib Python and
ships inside the APK (Chaquopy), so engine and app always have the same version; the Android `CostCalculator`
re-implements `recompute` numerically (ADR-0009), so the numbers of a cost unit must keep their meaning.

One module owns every rule: `verst_planner/domain/facts.py` (`hours_known`, `ticket_known`, `ticket_prices`,
`confirmed_free`, `breakfast_confirmed`, `tag_state`, `fuel_state`, `rank_rating`). The pipeline, the cost
model, the stop rendering and the mobile bridge all read it. `ticket_prices` moved there from two copies
(`cost/model.py`, `pipeline/alternatives.py`).

## 2. Decisions

| # | Was | Now | Where the user sees it |
| --- | --- | --- | --- |
| E-1 | `opening_hours` None = always open | None = **unknown**. The stop stays allowed and is scheduled as if open (no new feasibility rule), but nothing claims it is open. `24/7` or the `24h` tag = known. | Road row: «Часы не известны — уточните» (`unknownRu`). Card: chip «часы не известны — уточните» (`hours.known = false`). Walk: `todayRu`/`openNow` null → the app's «часы не указаны» pill (was «24 часа · открыто»). Open-data places: the existing open-data ring («из открытых данных, часы уточняйте») already says it, so no extra row line. |
| E-2 | no ticket price = free | None without `free_entry` = **price unknown**. 0 ₽ in every sum, never «вход свободный». | Road row cost: «цена билета неизвестна». Waybill ticket line: «1 место — цена билета неизвестна» or «… + ещё 1 — цена билета неизвестна»; under the total: «Без билетов в 1 место — цена неизвестна» (`totalNoteRu`). Card: chip «цена билета неизвестна» (`ticket.known = false`). |
| E-3 | `breakfast_included` default true | `bool \| None`, default None = **unknown → costed as not included**. | The food line counts a breakfast the morning after that night («завтрак 540»). |
| E-4 | every station sells every fuel | `fuel_kinds` / `fuel_kinds_no` (from `core.place_fuel`). A station known **not** to sell the car's fuel never enters the corridor; a confirmed one ranks above every unknown one in the refuel window. | Fuel row: «Есть ли АИ-95 — не проверено» (or with the hours: «Не проверено: часы работы, есть ли АИ-95 — уточните»). |
| E-5 | rating default 3.0 | `rating_internal: float \| None`; None ranks with `UNRATED_RANK = 0.0`, below every real rating (0..5). | Nothing new on screen: an unrated place is only a fallback when no rated place fits. |
| E-6 | «no» and «unknown» identical | `tags` = confirmed yes, `tags_no` = confirmed no, neither = unknown. A dog crew's sight reason says «Собака ждёт с одним из взрослых» only for a confirmed «no», «…, с собакой можно» for a confirmed «yes»; unknown makes no claim and the row says «Пускают ли с собакой — не проверено». | Road row; the walk's kind-based line is hedged to «С собакой внутрь обычно нельзя» (as the engine's own walk note). |

Notes per item:

- **E-1, which places.** The hours line is for sights, cafés and fuel stations (`facts.HOURS_TYPES`): their stop
  depends on an opening time the user can check. A rest area is open-air and a hotel's reception is confirmed by
  the booking; the engine claims nothing about their hours, so they get no line.
- **E-1, why no ranking change.** ADR-0018 suggested preferring known hours. In the fixture and open-data worlds
  whole classes have no hours (all rest areas, most fuel stations, outdoor sights), so a preference would only
  reshuffle plans without making them truer; the marker tells the user what to check. Revisit when ENG-04 serves
  curated places, which cannot go live without hours (0002 gate).
- **E-2, estimate vs. exclude.** ADR-0018 suggested a per-category estimate. Rejected for now: an estimate is a
  number we invent, and the card already shows the open-data estimates (`POI_TICKETS`, «цена примерная») where we
  have a basis. The unknown price stays out of the total, and the total says so. The «бесплатные места» budget
  lever (ADR-0011) keeps only confirmed-free sights, because it promises «free».
- **E-2, catalogue.** `adapters/catalogue/world.py` used to add `free_entry` to every open-data sight without a
  default ticket, including OSM `fee=yes`. Now: `fee=no` → free; a kind with a default ticket → the estimate;
  public spaces and churches (`FREE_KINDS`: church, monument, park, viewpoint, embankment, square, theatre seen from
  its square, nature, playground) without `fee=yes` → free by their kind; everything else (3 785 `attraction`
  items, `fee=yes` without a default) → unknown.
- **E-3, count vs. flag.** Counting the breakfast can over-estimate a trip by one breakfast per night; assuming it
  can under-estimate it, and an under-estimate is the failure users punish (checklist §3.1). The waybill row
  already shows «завтрак N», which is what we budget. The cost units keep `breakfastIncluded: bool` with the same
  numeric meaning (true = no breakfast costed), so the Android `CostCalculator` needs no change; unknown is false.
- **E-5.** 0.0 is a ranking value, not a rating: `rating_internal` stays None in the data and no screen shows it.
- **Where unknown facts live.** `ScheduledStop.unknown_facts` (keys `hours`, `ticket`, `fuel`, `dogs`) for the
  app's logic, `unknown_ru` for the row. The ticket is left out of `unknown_ru` (the cost texts name it), and
  open-data places get no `unknown_ru` (their ring says it).

## 3. Contract changes (all additive) and the API version

| Where | Field | When written |
| --- | --- | --- |
| trip stop (and an alternative's stop) | `unknownFacts: [str]`, `unknownRu: str \| null` | only on stops with an unknown fact, so other stops keep their bytes (the `funFor` rule) |
| `cost` | `totalNoteRu: str` | only when the total leaves something out |
| `cost.units.tickets[]` | `known: false` | only when false |
| alternative `units` | `ticketKnown: false` | only when false |
| `poi_details` sight | `hours.known`, `ticket.known`; `hours` is now present for unknown hours, `ticket` for an unknown price (`adultRub` null) | always |
| `city_route` stop | `hours.todayRu` / `hours.openNow` may be null (unknown) | when unknown |
| fixture world JSON | `tagsNo`, `fuelKinds`, `fuelKindsNo`; absent `rating` / `breakfastIncluded` = unknown | optional |
| `docs/contracts/{replace,patch}` | `afterFlags` = alternatives elsewhere in the trip whose `breaksBudget` the edit flips (ADR-0011 flags trip-wide) | only when non-empty (G13: 9 replace items, 1 patch item) |

`API_VERSION` stays **3**. Its rule is «a signature or envelope changes»; none does. Every new field is optional
with a default that reads as the old behaviour in the app's DTOs, and `breakfastIncluded` keeps its numeric
meaning. The two widened values (`hours.todayRu`/`openNow` null; `ticket.adultRub` null) were already nullable in
the app's DTOs, the app already renders null hours as «часы не указаны», and engine and app ship in one APK, so
no client sees a mixed pair. Older saved trips decode: every new key has a default in `codec`.

## 4. For the ENG-04 adapter (DB → `Place`)

NULL `rating_internal` → None; NULL `breakfast_included` → None (no longer `False`); NULL `opening_hours` → None;
`core.place_tag` state `no` → `tags_no`; `core.place_fuel` `yes` / `no` → `fuel_kinds` / `fuel_kinds_no`
(`unknown` rows → neither). All new `Place` fields have defaults, so existing constructors keep working.

## 5. Consequences

- Golden trips change: breakfasts at the fixture hotels without `breakfastIncluded` are now costed (G01, G02,
  G03, G06, G07, G13: totals + 6–10 %), dog crews' sight reasons, and the new stop fields. Every diff is justified
  in `docs/dev-notes.md` § Investor-readiness / trust fixes. The fixture data is unchanged: it never said those
  breakfasts were included, and the engine must not decide it for the hotels.
- The Data Curator may relax checklist §3.3 («нет АИ-95 → не выпускаем») once ENG-04 maps `core.place_fuel`, and
  the notes «движок решит, что открыто всегда» / «движок считает место без цены бесплатным» in checklist §2.4, §3,
  §4 are no longer true (the release gates stay).
- The share text («Итого ≈ …») is unchanged: its Kotlin twin (`ShareTextBuilder`) is pinned by the share-text
  contract; adding the total note there is a separate change.

## 6. Options considered

- **Keep the defaults, fix the data** (curators always fill the fields): rejected; it keeps the engine wrong for
  open data and for every place a curator could not reach, which is exactly the «unknown» case.
- **Drop places with unknown facts**: rejected; it empties the open-data world (no fuel station has fuel kinds yet)
  and hides useful stops. Unknown is shown, not hidden.
- **One generic «не проверено» flag per stop**: rejected; the user needs to know *what* to check, and the app
  needs the ticket fact to stop saying «вход свободный».
