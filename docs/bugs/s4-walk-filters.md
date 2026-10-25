# S4 investigation — «По городу» → «Свой маршрут»: re-plan and filters (CEO, build 83)

Investigation only: nothing is fixed on this branch. The setup is the CEO's:
- start Фрязино, «проезд Павла Блинова, 8» (55.9606, 38.0456);
- adults only;
- «Свой маршрут»: 4 ч, история + архитектура, обычный темп, бюджет «не важно», вернуться к старту.

Code is main `cf8f335` (build 83).

How it was reproduced:
- **Engine.** `docs/bugs/s4-walk-filters-repro.py` runs the real engine and the real catalogue (r7.2) on the
  sandbox: `python3 -I docs/bugs/s4-walk-filters-repro.py`.
- **App flow.** `VerstFlowTest.customWalkRecoversAfterOtherVariantRunsOutOfPlaces` uses a fake engine that
  answers like the real one in Фрязино. It fails on main (CI run listed at the end), and the fix should make it
  pass. It is committed with `@Ignore` so the branch stays green.

## What the engine does in Фрязино (repro script)

12 sights are within the 4 km radius:
- three monuments 0.5–1.3 km from the start;
- the Гребнево estate cluster (church, tower, park, palace…) 2.5–2.9 km away.

| Request (4 ч, история + архитектура, обычный, с возвратом unless noted) | Result |
| --- | --- |
| as set by the CEO | 3 monuments, **75 min**, `shorter`: «Получилось 1 ч 15 мин вместо 4 ч — больше открытых мест рядом нет» |
| «Другой вариант» = the same with `exclude` = those 3 | **`NOT_ENOUGH_POIS`** |
| interests «парки», «виды», «история» or «архитектура» alone | the same 3 monuments, 75 min |
| 2 ч or 8 ч | the same 3 monuments, 75 min |
| темп «медленный» | 6 stops incl. Гребнево, 240 min |
| без возврата | 10 stops incl. Гребнево, 228 min |

So in a small town one «Другой вариант» already exhausts the places, and most filters cannot change the result.

## (a) After «Другой вариант» the screen leaves the walk and then ignores every change

**Cause (app).** «Другой вариант» adds the current stops to `walkExclude`. Nothing removes them except opening
«По городу» again from the Windshield.
- `android/app/src/main/kotlin/app/verst/nav/VerstFlow.kt:1760-1764` `otherWalk()`:
  `walkExclude += w.stops.mapNotNull { it.poiId }`. It accumulates on every tap and the list is never reset.
- `VerstFlow.kt:1583`: `walkExclude.clear()` happens only in `openCity()`.
- `VerstFlow.kt:1721`: `walkRequest()` sends `exclude = walkExclude` on every build: ПОШЛИ, «Собрать прогулку»,
  «Гулять N ч» and «Другой маршрут» → «Собрать».
- `VerstFlow.kt:1748-1751`: on `NOT_ENOUGH_POIS` with `keepScreen` the flow calls `back()` from Walk to City
  and shows the «Мало мест» plate. This is the «drops out of the walk» moment.

From then on every request still excludes the stops the engine needs. Any filter, duration or pace gives
`NOT_ENOUGH_POIS` again, the City screen shows the same plate, and nothing seems to react. In a big town the same
happens after more taps.

**Proposed fix (app):**
1. `walkExclude` belongs to one «Другой вариант» chain. Clear it whenever the walk's parameters change:
   `setCityDuration`, `toggleCityInterest`, `pickCityPace`, `pickCityBudget`, `toggleCityReturn`,
   `selectCityPreset`, `walkLonger`, the start point (`cityStart`), and «Собрать прогулку». A practical rule is
   to remember the request without `exclude` and drop the list when the new request differs.
2. When «Другой вариант» is `NOT_ENOUGH_POIS`, stay on the current walk (no `back()`). Show a toast such as
   «Других вариантов рядом нет» (copy for the Designer), and keep or reset the list so the next tap cycles
   instead of failing forever.
3. Optional: cap the list (the last two walks' stops) so a long chain cannot starve the solver.

**Test (added, ignored until the fix).** `VerstFlowTest.customWalkRecoversAfterOtherVariantRunsOutOfPlaces`:
1. Build a custom walk, then press «Другой вариант» (the fake engine answers `NOT_ENOUGH_POIS`).
2. Choose «Другой маршрут», change the duration and an interest, then «Собрать».
3. Expect: the request carries the new filters with `exclude` empty, the screen is the walk, and there is no error.

After the fix, also expect that «Другой вариант» with no alternative keeps `top == Walk`.

## (b) Changing filters does not rebuild the walk or change its points

There are three causes. They stack, so in Фрязино nothing visible changes.

1. **App, exclusions:** as (a). Once one «Другой вариант» has run, every rebuild fails and the old screen
   stays.
2. **App, by design but confusing:** the City screen and the custom sheet only change state. The walk is
   rebuilt only on ПОШЛИ or «Собрать прогулку» (`VerstFlow.kt:1667-1697` setters, `:1704` `buildCustomWalk`).
   Also, opening «Свой маршрут» again resets the duration and pace to the preset defaults (`VerstFlow.kt:1636-1639`
   → `selectDefaults`, `:1619-1623`), so earlier choices are silently replaced.
   Proposal: keep the user's custom values when the sheet reopens. After a change while a walk exists, show the
   caption as changed («Собрать заново»), or rebuild on «Готово». This needs the Designer's call (mockups first,
   per the CEO).
3. **Engine** (Architect), confirmed with the script:
   - **Interests are weights, not filters.** `backend/planner/verst_planner/city/presets.py:147-155`
     `custom_weights` gives every other sight kind 0.15, so a town without parks or viewpoints in the catalogue
     answers «парки» or «виды» with the same monuments.
   - **The solver stops in a local optimum.** At normal pace with the return it keeps 3 stops (75 min of 240),
     though the slow pace and the one-way walk both reach the Гребнево cluster with the same 12 candidates.
     The likely trigger is the leg cap: `presets.py:27-28` (`WALK_FACTOR = 1.30`, `MAX_LEG_KM = 2.5`) and
     `city/walk.py:319` (`if km > MAX_LEG_KM: infeasible`). A Гребнево stop is 3.3 km of walking from the start
     and can only be reached through another stop. The one-at-a-time insertion in `_insert_pass`
     (`walk.py:358`) and `solve()` (`walk.py:478`) does not find that chain at normal pace.
   - **The «shorter» reason is wrong.** «больше открытых мест рядом нет» is shown although 9 more places are
     within reach (`resources/strings.ru.json:132` `walk.shorter.places`).
   - **Proposal (Architect):** insert pairs or clusters (or lift the leg cap for an insertion that is followed
     by a short leg); treat interests as a filter with a fallback; set the `shorter` reason from what actually
     limited the walk. Engine test: Фрязино custom 4 ч обычный с возвратом gives ≥ 4 stops and ≥ 180 min, and
     «парки» returns no monument-only walk without saying so.

## (c) «Мало мест для такой прогулки» offers «Гулять 4 ч» while 4 ч is selected

**Cause (app).** The plate's action is computed from the current duration only. It is offered whatever caused the
failure:
- `android/app/src/main/kotlin/app/verst/feature/city/CityScreen.kt:152`:
  `city_not_enough_longer` with `(WalkDurations.firstOrNull { it > ui.durationMin } ?: WalkDurations.last()) / 60`.
  At 8 ч it falls back to `last()` and offers «Гулять 8 ч» while 8 ч is selected.
- `VerstFlow.kt:1766-1771` `walkLonger()` keeps `walkExclude`, so «Гулять N ч» after «Другой вариант» always
  fails again: the plate comes back with the next duration and finally repeats «Гулять 8 ч».
- In Фрязино a longer walk cannot help at all: 2 ч, 4 ч and 8 ч give the same 75 min walk (table above).

The exact text «Гулять 4 ч» means the flow's duration was 2 ч at that moment, since the label is always the next
value above `cityDurationMin`. With 4 ч the label is «Гулять 6 ч». I could not find a code path that shows
«4 ч» on the chip and keeps 120 in the flow. The sheet and the plate read the same `cityDurationMin`, which only
`setCityDuration`, `selectDefaults` and `walkLonger` change. The most likely sequence is (a): «Другой вариант» →
plate → «Гулять …» → the plate again with a different number. Either way the action is wrong.

**Proposed fix:**
- Offer «Гулять N ч» only when a longer walk can help: the error came from a build with an empty `exclude`, and
  a longer duration exists (not at 8 ч).
- Otherwise offer «Другой маршрут» / «Изменить старт» only.
- `walkLonger()` clears `walkExclude` (see (a)).
- Better, if the Architect agrees: the engine returns `NOT_ENOUGH_POIS` with `reason` (`excluded` | `area`) and
  the largest duration that would work, and the plate uses that.

**Test.**
- Robolectric `CityScreen` with `error = NOT_ENOUGH_POIS` and `durationMin = 480`: no «Гулять 8 ч».
- A flow test: «Другой вариант» → `NOT_ENOUGH_POIS` → the plate's longer action is absent (e.g.
  `flow.cityLongerOffer == null`).

## Summary for the backlog

| # | Owner | Fix | Test |
| --- | --- | --- | --- |
| a | Developer | reset `walkExclude` on any parameter change; on `NOT_ENOUGH_POIS` from «Другой вариант» stay on the walk with a toast | `customWalkRecoversAfterOtherVariantRunsOutOfPlaces` (added, `@Ignore` until fixed) |
| b | Developer + Designer | keep custom values when the sheet reopens; make «changed, rebuild» visible (mockup) | flow test: reopen the sheet keeps 2 ч / slow |
| b | Architect | solver reaches clusters behind the leg cap; interests filter with fallback; honest `shorter` reason | engine test: Фрязино 4 ч normal + return ≥ 4 stops |
| c | Developer | «Гулять N ч» only when a longer walk can help (no exclusions, below 8 ч) | Robolectric plate test at 480; flow test after «Другой вариант» |
