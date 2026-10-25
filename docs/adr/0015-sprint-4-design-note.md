# ADR-0015: Sprint 4 design note (CEO build 83 feedback)

Status: **Draft — headlines only, the full text follows in the next push** · Date: 2026-10-25 · Branch `arch/sprint-4` from main `cf8f335`

This round is design only: no engine code until the mockups are approved. Headline decisions, so the Designer can
draw now:

1. **Navigator hand-off.** Яндекс Навигатор and Яндекс Карты open an unsigned URL **only 5 times per device per
   24 h**; after that the link opens the Navigator web page in the browser, so the route never reaches the app.
   We apply for a free client id and key (forms.yandex.ru) and sign every link. Until the key arrives, the whole day
   goes to **Яндекс Карты** (`rtext` with every point, car mode, turn-by-turn «В путь»); Навигатор gets only the
   next point.
2. **POI quality.** A quality score, a hard exclude list (schools, stadiums, ordinary churches, administrative
   buildings) and diversity rules (≤ 1 religious place per 3 stops). The Moscow «Красная площадь» stop on the
   Фрязино ring is a routing gap, not a detour: the route goes through central Moscow. Fix: a Moscow bypass and no
   big-city centre sights on transit.
3. **Extra sources.** ru Wikipedia summaries, ru Wikivoyage listings, OSM tags and Commons geosearch, built into
   the offline catalogue in CI. Online lookups only for the card.
4. **Parking.** A new Waybill line «Парковки»: dwell × tariff by city zone (Москва, СПб, other big cities), with
   OSM `fee`/`charge`; free or unknown when nothing is known.
5. **«Весело и познавательно».** Interesting stops instead of bare rest areas, adapted to the group (child: play,
   interactive; dog: parks, nature). The moods are renamed.
6. **City walking.** A group input (adults, children, dog), 18+ by an age question, warnings, «без ограничения»,
   OSM opening hours, and fixes for the «Гулять 4 ч» suggestion and walks not rebuilding.
7. **Distance so far.** `kmAt` is the route position without detours; v3 adds `kmDriven` (cumulative, with
   detours) for «пройдено N км».
