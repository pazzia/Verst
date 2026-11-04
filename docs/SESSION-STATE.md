# Session state (checkpoint)

The working memory between sessions and compactions (CLAUDE.md, «Read first»). Facts only, newest first.
Update at the end of every task. Older history: `docs/PROJECT-STATE.md` §3 and `docs/decisions.md`.

**Updated:** 2026-11-04

## Now

- **Release 0.3.216 (04.11, PR #10 `7cdfe4e`):** verst-latest; the test server runs `7cdfe4e` since 18:26 MSK (update asked and approved; ~14 s downtime, no errors).
- **Rollback (D-IR-33, PR #11 `81e43ee`):** merged; the server ran `update` at 19:06 MSK (no code change, the api was not recreated). The next `update` keeps a rollback image. `spike01` runs on any change of `spike.yml` (the Node 24 bump started it): ask the CEO whether to make it manual-only.
- **04.11, merged in PR #10:**
  - D-IR-31 (CEO option 1): an approximate long trip asks once «Дальняя поездка — точнее на сервере»; yes = server consent + later approximate trips on the server (fallback phone); no = phone, not asked again. Engine `estimate.approx`; `PlanRequest.longTrip`; `AppSettings.longTripAsked`. Seen on the camper emulator shot 05a (Москва → Санкт-Петербург). Green on run 41834108817 (attempt 2; attempt 1 failed the catalogue budget at 2 009 ms, attempt 2 measured 501–1 532 ms: the CI emulator varies ~3x).
  - Plan audit of 20 trips on the real catalogue: `docs/review/plan-audit-2026-11-04.md`. Fixed: no open-data playground for adults (`test_real_plans.py`). Main finding: long trips on the phone run on approximate straight legs outside central Russia (no real cafés, towns or hotels along them); the server's GraphHopper does not have this. **CEO decision asked:** plan long trips on the server when online and consented.
  - Catalogue load: town food stays columns (`_FoodRows`, `food_for_towns`); a reload frees the old world first. Emulator samples: 1 575 / 1 510 / 1 018 ms and 2 037 / 1 716 / 1 207 ms (budget 2 000 ms median); reloads no longer grow. The 2x target was not reached.
  - CI actions on Node 24 (checkout v5, setup-python v6, upload-artifact v6, download-artifact v7, setup-java v5, cache v5, setup-gradle v5); green on run 41824290305, test-server green.
  - Release notes: `Тестерам-заменяет:` drops an older wording (`tools/ci/whats_new.py`).
- **Test server ops (D-IR-29/30, PR #8 `a63d9e9`):** `test-server.yml` + `infra/api/server-ops.sh`; trigger = a new line in `infra/api/test-server.request` pushed on the ccr branch (or workflow_dispatch). Live since 03.11 21:39 (first `status`: api, postgres, graphhopper, backup healthy; /healthz ok). The server checkout is on `main` since 03.11 21:50 (`a63d9e9`); the running api was built at 21:26 from the same code (0.3.209 engine). The pinned host key is `infra/api/test-server.known_hosts` (ed25519 SHA256:Nx9n4W…); fixes merged in PR #9 (`c53cfa5`), `workflow_dispatch` from `main` works.
- **Release:** «Верста» 0.3.209 from PR #7 (`54ada56`); `main` is now PR #9 (docs and the test-server workflow only), «Верста» 0.3.209 at `releases/download/verst-latest/Verst-latest.apk` (03.11), all CI green. PR #6 = real stops, fuel names, roadside cafés; PR #7 = catalogue load headroom (walk grids lazy, ≤ 20 hotels per town as places).
- **Two designs (D-IR-24):** «Кемпер» is the default, «Классический» is chosen in Settings. The `camper-ui` branch and `verst-camper-latest` (0.3.187) are frozen.
- **Hotel booking (D-IR-25):** «Забронировать ночь» opens the real Yandex Travel search. The Travelpayouts wrapper on the server is off until `VERST_TP_*` are set.
- **Test server (NL, `docs/ops/test-server.md`):** GraphHopper with the Russia graph is on since 01.11 (`VERST_ROUTING=graphhopper`). Runs the 0.3.209 code since 03.11.
- **Working branch** `ccr-013d3489-181fz2` = `main` after PR #9.

- **Yandex MapKit:** the CEO got a free key (02.11). The terms of 01.09.2026 are analysed in `docs/research/yandex-mapkit-terms.md`.
  - Free only for a free open app; at most 1 000 unique users a day.
  - No storing Yandex data; no own turn-by-turn; no live tracking.
  - Required: logo and «Открыть в Картах», a terms link in «О программе», and consent for Yandex collecting IP, device id and location (п. 8.1).
  - Not integrated yet: waiting for the CEO to choose the screen.

- **Fuel names, unpriced hotels, roadside cafés (D-IR-28, 03.11):** green on run 41677282111 (APK 50.2 MB), seen on camper emulator shots (04b question, 150 Road, 151 waybill).
  - Data run 3 (`bot/data-stops-3`): fuel stations keep real names (20 234 of 28 906 roadside places named); 16 461 roadside cafés within ~1 km of motorway/trunk/primary, outside towns (116 say they have a toilet, 28 say they have none).
  - Engine: input `roadsideFood` (None = yes without children, town cafés only with a child); reasons «Обед в кафе у трассы…»; the total, the «Ночёвки» line and the shared text say «Стоимость ночёвок в отелях не учитывается».
  - App: with a child every ПОЕХАЛИ asks «Где обедать с ребёнком?» («И придорожные кафе» / «Только в городах»); the Road footer «Итог без стоимости отелей».
  - Brand deny-list: fuel chains are `copy:` entries (denied in app/engine copy, allowed in OSM place data).
  - Count hotel prices once a partner (Travelpayouts / Островок) or an open source gives them.
- **Real stops (D-IR-27, 02.11):** the plan uses only real OpenStreetMap hotels, fuel stations, rest areas and cafés.
  - Data: `catalogue_lodging` (12 530) and `catalogue_roadside` (28 902) from `data-stops.yml` run 2.
  - A night has no price («по ссылке «Забронировать»»), so the total leaves it out.
  - Engine, server and app changes: 3302307. The fix 7732c49 reads the roadside places on the first plan: the emulator catalogue load had gone to 2 041 ms against a 2 000 ms budget.
  - Side effect: with hotel nights left out of the total, the CEO budget case (30 000 ₽) fits on the first plan and «Подогнали под бюджет» is not shown. The budget check does not count hotels now.
  - App (c6a8936): a real hotel card has no «вымышленная» line; the hotel row shows «цена — по ссылке» under the name; the waybill «Ночёвки» shows «—» for unpriced nights; the Road footer says «Итог без ночёвок» instead of «в бюджете».
  - Green on 0.3.199 (run 41547293291), seen on the camper emulator shots (22-exit, 65-card, 151-waybill, 10-road). Emulator catalogue median: 1 668 ms against a 2 000 ms budget. APK 49.85 MB (over the 45 MB warning, under the 60 MB fail).

## Waiting on the CEO

1. Register at Travelpayouts and put `VERST_TP_TOKEN/MARKER/TRS` into the server `.env` (`docs/partners/hotel-affiliate.md` §4).
2. Decisions:
   - legal entity, D-IR-09;
   - a lawyer on the «Реклама» label at the booking button (R-05);
   - a server in Russia before the beta.
3. MapKit: which screen gets the map first (Road day map / city walk / pick a point); put the key into GitHub Secrets `YANDEX_MAPKIT_KEY` and restrict it to `app.verst.demo`.
4. The Yandex Navigator signing key: **not yet** (D-IR-17). The form asks for a company, a site and a store link. It comes after the legal entity, the domain and RuStore, before the closed beta.

## Next (when the CEO says)

- Ostrovok links for overnights abroad (6 % vs 3 %), after checking its URL template on a real link.
- 2GIS in the hand-off choice for Kazakhstan, Uzbekistan and Kyrgyzstan.
- Older open items:
  - abroad source verification (needs hosts allowed);
  - Южная Осетия, villages and resorts;
  - the «Обед» 600 ₽ estimate;
  - a sunset rule;
  - the mockup fonts.
