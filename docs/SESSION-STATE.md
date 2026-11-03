# Session state (checkpoint)

The working memory between sessions and compactions (CLAUDE.md, «Read first»). Facts only, newest first.
Update at the end of every task. Older history: `docs/PROJECT-STATE.md` §3 and `docs/decisions.md`.

**Updated:** 2026-11-03

## Now

- **Test server ops (D-IR-29/30, PR #8 `a63d9e9`):** `test-server.yml` + `infra/api/server-ops.sh`; trigger = a new line in `infra/api/test-server.request` pushed on the ccr branch (or workflow_dispatch). Live since 03.11 21:39 (first `status`: api, postgres, graphhopper, backup healthy; /healthz ok). The server checkout is on `main` since 03.11 21:50 (`a63d9e9`); the running api was built at 21:26 from the same code (0.3.209 engine). The pinned host key is `infra/api/test-server.known_hosts` (ed25519 SHA256:Nx9n4W…); the workflow fixes are on the branch, not yet in `main`.
- **Release:** `main` = PR #7 (`54ada56`), «Верста» 0.3.209 at `releases/download/verst-latest/Verst-latest.apk` (03.11), all CI green. PR #6 = real stops, fuel names, roadside cafés; PR #7 = catalogue load headroom (walk grids lazy, ≤ 20 hotels per town as places).
- **Two designs (D-IR-24):** «Кемпер» is the default, «Классический» is chosen in Settings. The `camper-ui` branch and `verst-camper-latest` (0.3.187) are frozen.
- **Hotel booking (D-IR-25):** «Забронировать ночь» opens the real Yandex Travel search. The Travelpayouts wrapper on the server is off until `VERST_TP_*` are set.
- **Test server (NL, `docs/ops/test-server.md`):** GraphHopper with the Russia graph is on since 01.11 (`VERST_ROUTING=graphhopper`). The server has not yet been updated to PR #5: the CEO has the commands.
- **Working branch** `ccr-013d3489-181fz2` was restarted from `main` after the merge.
  - In it: the CCGS ideas 1–4 (this file, `CLAUDE.md`, `.claude/rules`, the commit guard, «Что нового» in releases).
  - Also in it: the maps-API research `docs/research/maps-apis-2026-11.md`.

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
  - Not merged: waiting for «Сливай».

## Waiting on the CEO

1. Update the test server to `main` (commands in `docs/ops/test-server.md`, «Обновить сервер»), then the one-time key setup of §5 (D-IR-29) and the two GitHub Secrets `VERST_TEST_SERVER_SSH_KEY` / `VERST_TEST_SERVER_KNOWN_HOSTS`. After that Claude runs `status` / `errors` freely and `update` / `recreate` only after asking (D-IR-30).
2. Register at Travelpayouts and put `VERST_TP_TOKEN/MARKER/TRS` into the server `.env` (`docs/partners/hotel-affiliate.md` §4).
3. Decisions:
   - legal entity, D-IR-09;
   - a lawyer on the «Реклама» label at the booking button (R-05);
   - a server in Russia before the beta.
5. MapKit: which screen gets the map first (Road day map / city walk / pick a point); put the key into GitHub Secrets `YANDEX_MAPKIT_KEY` and restrict it to `app.verst.demo`.
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
