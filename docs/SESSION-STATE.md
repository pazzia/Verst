# Session state (checkpoint)

The working memory between sessions and compactions (CLAUDE.md, «Read first»). Facts only, newest first.
Update at the end of every task. Older history: `docs/PROJECT-STATE.md` §3 and `docs/decisions.md`.

**Updated:** 2026-11-02

## Now

- **Release:** `main` = PR #5 (`ed00467`), «Верста» 0.3.193 at `releases/download/verst-latest/Verst-latest.apk`, all CI green.
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

## Waiting on the CEO

1. Update the test server to `main` (commands in `docs/ops/test-server.md`, «Обновить сервер»).
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
