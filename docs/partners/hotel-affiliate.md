# Hotel affiliate links (ENG-03, CEO 01.11 «прикрутить настоящее»)

Status on 01.11.2026:
- **Code: done.** «Забронировать ночь» opens the real hotel search instead of the mock sheet.
- **Revenue: off.** It switches on once the Travelpayouts account ids are entered on the server.

## 1. What works now

| Part | Behaviour |
| --- | --- |
| App, «Забронировать ночь» | Opens the Yandex Travel search for the night: town, check-in, check-out, adults and children. It opens in the browser or the partner app. On return the app asks «Забронировали?» as before. |
| App, without consent to the server | Builds the plain search link itself (`HotelLinkQuery.plainUrl`, core-model). No commission. |
| App, with consent | Asks the server first (`GET /v1/links/hotel`, 4 s timeout). On any failure it uses the plain link. |
| Server, `GET /v1/links/hotel` | With `VERST_TP_TOKEN` / `VERST_TP_MARKER` / `VERST_TP_TRS` set, it wraps the search through the Travelpayouts partner-links API and returns `affiliate: true`. `sub_id` is the trip and stop. Results are cached for 24 h. Any API error returns the plain link. |
| Children's ages | The app only knows how many children there are. Each child gets the engine's assumption, `cost.assumed_child_age` = 8. The traveller can change it on the partner's form. |

Changes on the server need no new app release. A new partner or link template is a server change only.

## 2. Programs (research 01.11; full report with sources in the session log)

The pages were read through search snippets: travelpayouts.com and yandex.ru are blocked for this environment. Each figure must be re-read in the partner account before relying on it.

| Program | Hotels: commission | Notes | Source |
| --- | --- | --- | --- |
| **Yandex Travel via Travelpayouts** (chosen first) | 8 % Russia, 3 % abroad | 30-day cookie, confirmed 2 days after checkout. Yandex is not among the brands that credit sales made inside their own app, so attribution may be lost if the Yandex Travel app opens: test with a real booking. | travelpayouts.com/ru/offers/yandex-travel-partnerskaya-programma/ ; travelpayouts.com/ru/brands/blog/mobile-apps/ |
| Ostrovok via Travelpayouts (second, for abroad) | 6 % | Worldwide. The click must happen before the booking form. One review reports a payout hold of 68–180 days. | travelpayouts.com/ru/offers/ostrovokru-partnerskaya-programma/ |
| Суточно.ру via Travelpayouts | 5 % | Russia, Belarus, Abkhazia | travelpayouts.com/ru/offers/sutochno-ru-partnerskaya-programma |
| Yandex Travel direct (Яндекс Дистрибуция) | "up to 12 %" (2023 announcement); current rate unverified | Has its own `affiliate_clid` link template and a Partner API with prices (access by request). | yandex.com/support/travel-distr/ru/instruments/partner-links-manually |
| Hotellook | **closed** | | support.travelpayouts.com/hc/en-us/articles/29534131568530 |
| Booking.com, Agoda | not in Russia | | travelpayouts.com/ru/blog/booking-holdings-changes/ |
| 101hotels | needs 10 000+ users a day | | 101hotels.com/partner_program |

## 3. Advertising law (38-FZ art. 18.1)

- Travelpayouts treats a partner link as advertising.
- Once the partner fills in «Закон о рекламе» in the Travelpayouts account, Travelpayouts reports to ЕРИР and adds the `erid` to its links (Travelpayouts blog, new-advertising-law).
- The 3 % levy is charged through ЕРИР. Travelpayouts compensates it (support article 28845366678418).
- **Open legal question (risk register R-05):** our button is native UI, not a Travelpayouts widget. It may need a visible «Реклама» label and the advertiser's name. This is for the lawyer. The button already says «через Яндекс Путешествия».

## 4. CEO steps (about 20 minutes)

1. Register at travelpayouts.com/ru.
2. Add a project of the mobile-app type. Its id is the **trs**.
3. Join the programs «Яндекс Путешествия», «Ostrovok.ru», «Суточно.ру» (and Tripster for excursions later).
4. Fill in the «Закон о рекламе» form.
5. Payouts: until the legal entity exists (D-IR-09), use ЮMoney (personal income tax withheld) or самозанятый. Switch to the ИП / ООО account later.
6. Copy three values from the account:
   - **marker** (partner id, in the profile);
   - **trs** (project id);
   - **API token** (profile → API).
7. On the server, in `/srv/verst/src/infra/api/.env`, set `VERST_TP_TOKEN=…`, `VERST_TP_MARKER=…` and `VERST_TP_TRS=…`, then restart api.
8. Check: in the app (server mode on), «Забронировать ночь» opens a `tp.media/...` link that redirects to Yandex Travel. The click appears in Travelpayouts statistics within a day.

The API answer shape (`partner_url`) was taken from the documentation snippet. If the first real call returns something else, the server logs «partner link API: no partner_url» and serves the plain link: nothing breaks, and the parser needs a fix.

## 5. Next

- Ostrovok for overnights abroad (6 % vs 3 %), once its search URL template is checked on a real link.
- Яндекс Дистрибуция: compare the direct rate and ask for Partner API prices.
- A real booking test for attribution through the Yandex Travel app.
