# Verst — Investor-readiness backlog: from a demo to a product with proof

Horizon: 90 days (13 weeks) · Owner: CEO · Engineering acceptance: Manager · Team: role skills in `.claude/skills/` (see `.claude/skills/TEAM.md`) · Base: `main` @ `11f3a2b` (Sprint 4 CEO build)

**Goal.** In 90 days, go back to an investor with proof, not promises. That means real roads, real hotels and real prices; 10 Moscow ready routes with verified places; at least 100 families who actually drove a Verst trip; and a first money signal: confirmed affiliate bookings or one signed pilot.

**Why.** This backlog comes from an investor-style review of the Sprint 4 build (Oct 25, 2026). That review found:

- the engineering is strong;
- everything an investor pays for is still unproven: demand, real data, revenue, defensibility, team.

Specifically:

- hotels, cafes and fuel stations are fictional (`adapters/catalogue/synthetic.py`);
- distances are straight-line km × a calibrated ratio (`geo/roadmodel.py`), not a road router;
- booking is a mock partner;
- `backend/api`, `infra` and `admin` are empty;
- the curated Place DB has 0 verified places;
- there are no users and no metrics.

References: `docs/SPEC.md` (§9 Place DB, §10 integrations, §14 monetization, §17 acceptance), `docs/architecture.md`.

## Rules for the whole backlog

- **Feature freeze.** No new user-facing features (walks, bars, new presets, new card levels) until milestone M2 is met. Allowed: real data, real routing, real booking, measurement, and fixes.
- **Proof over output.** Every task names the metric or artefact that proves it is done. "Code merged" alone is never the acceptance criterion for a P0 business task.
- **`main` is always green.** A release commit with failing tests is a P0 bug.
- **Narrow before wide.** Moscow hub and its 10 ready routes first. No new regions until M3.
- **Every number is written down.** Interview notes, ad spend, funnel numbers and partner replies go in `docs/traction/`: one file per week, plain Markdown.

## Milestones (what the investor will check)

| ID | Week | Done when |
| --- | --- | --- |
| M1 Clean base | W1 | `main` green; landing page and waitlist live; 10 customer interviews written up; ODbL legal answer received |
| M2 Real trip | W6 | Every trip uses road routing; overnights show real hotels with real prices and a working affiliate link; 10 Moscow ready routes plan without warnings |
| M3 Verified data | W8 | ≥ 300 verified places on the 10 routes, each with `verified_at`; user "right/wrong" feedback flowing into the admin |
| M4 Closed beta | W10 | ≥ 100 beta families; funnel dashboard live; 3 field trips with receipts, cost error ≤ 15 % |
| M5 Money signal | W12 | First affiliate bookings visible in partner statistics with correct sub-ids **or** one signed pilot (region, hotel chain or roadside operator) |
| M6 Investor pack | W13 | Data room and deck built from the numbers below; 90-day results versus the targets table |

### Target numbers for the investor meeting

| Metric | Target at W13 |
| --- | --- |
| Trips planned (real routing) | ≥ 1 000 |
| Trips actually driven (confirmed by user) | ≥ 100 |
| Saved-trip rate | ≥ 25 % of planned trips |
| NPS of users who drove | ≥ 40 |
| Verified places | ≥ 300 on 10 routes |
| Cost estimate error (3 field trips) | ≤ 15 % |
| Pro waitlist | ≥ 5 % of active users |
| Revenue signal | ≥ 1 confirmed affiliate booking **or** 1 signed pilot |
| Cost per lead from the landing test | measured (no target: we need the real number) |

## Order and dependencies

```
W1      HYG-01 green main · VAL-01 interviews · VAL-02 landing + ads · LEG-01 ODbL · BIZ-01 unit economics
W1–W2   VAL-03 competitor teardown · TEAM-01 curator · LEG-02 legal entity + partner accounts
W2–W6   ENG-01 road routing ──▶ ENG-02 tolls ──▶ ENG-04 backend
        ENG-03 real hotels + affiliate links (needs LEG-02)
        DATA-01 Place DB separation (needs LEG-01) ──▶ DATA-02 curation of 10 routes ──▶ DATA-03 user verification
W5–W8   ENG-05 analytics · ENG-06 web planner (MVP) · DES-01 usability test
W8–W12  VAL-04 closed beta · VAL-05 field trips · BIZ-02…05 revenue pilots · BIZ-06 Pro waitlist pricing test
W12–W13 INV-01 data room · INV-02 deck
```

## Task list

Priority: **P0**: without it the investor says no. **P1**: makes the case strong. **P2**: important, but can slip past day 90.

| ID | Title | Priority | Owner | Depends on | Estimate |
| --- | --- | --- | --- | --- | --- |
| HYG-01 | Fix the 2 failing planner tests on `main`; make CI block red releases | P0 | Architect | — | 0.5 d |
| HYG-02 | Split god files (`VerstFlow.kt` 2 739 lines, `gen_worlds.py` 3 437 lines) | P2 | Developer / Architect | — | 2 d |
| VAL-01 | 30–50 customer interviews with car-travelling families | P0 | UX Specialist (CEO talks) | — | W1–W4 |
| VAL-02 | Landing page + waitlist + paid ad test (30–50 k ₽) | P0 | Growth Marketer + Web Designer (CEO approves spend) | — | 3 d + 2 wk run |
| VAL-03 | Competitor teardown (Яндекс Путешествия + Алиса AI, Яндекс Карты, 2ГИС, Roadtrippers, TripforTeam, Trippi) | P1 | Business Analyst | — | 2 d |
| VAL-04 | Closed beta with ≥ 100 families | P0 | Growth Marketer + UX Specialist + Developer | ENG-01, ENG-03, ENG-05 | W8–W12 |
| VAL-05 | 3 field trips with receipts (day trip, 2-day trip, Golden Ring) | P0 | UX Specialist (CEO drives) | ENG-01, ENG-02, ENG-03 | 3 trips |
| ENG-01 | Real road routing (self-hosted GraphHopper or OSRM, Russia extract) behind the existing routing port | P0 | Architect | — | 5 d |
| ENG-02 | Real toll segments and tariffs for the Moscow corridors | P1 | Architect | ENG-01 | 2 d |
| ENG-03 | Real hotels with prices and working affiliate links; remove synthetic hotels from production builds | P0 | Architect + Developer | LEG-02 | 5 d |
| ENG-04 | Minimal backend: plan API, ready routes, feedback, links; Docker Compose on one VM in Russia | P0 | Architect | ENG-01 | 5 d |
| ENG-05 | Analytics funnel and crash reporting (SPEC §15) + weekly dashboard | P0 | Developer (tracking plan: Growth Marketer) | ENG-04 | 2 d |
| ENG-06 | Web planner MVP (plan + cost page, shareable link, iOS users, SEO) | P1 | Developer + Web Designer | ENG-04 | 5 d |
| ENG-07 | Startup time and APK size: measure and cut the on-device Python cold start | P2 | Developer | — | 2 d |
| DATA-01 | Keep Verst's own data (tags, checks, prices) in tables separate from OSM-derived records | P0 | Architect | LEG-01 | 2 d |
| DATA-02 | Curate the 10 Moscow ready routes: ≥ 300 verified places with family/dog/parking tags | P0 | Data Curator + paid curator (TEAM-01) | DATA-01, ENG-04 | W3–W8 |
| DATA-03 | User verification loop: "here they let us in with the dog: yes/no", "closed", "price wrong" | P1 | Developer + Designer + Data Curator | ENG-04, DATA-01 | 3 d |
| DATA-04 | "Verified places per route" as a tracked KPI in the admin | P1 | Architect + Data Curator | DATA-02 | 1 d |
| LEG-01 | Lawyer's opinion on ODbL share-alike for the Place DB (OSM import in SPEC §9 step 1) | P0 | Legal & Compliance (CEO hires lawyer) | — | W1 |
| LEG-02 | Legal entity (self-employed / ИП / ООО), Travelpayouts and partner accounts, privacy policy | P0 | Legal & Compliance + CEO | — | W1–W2 |
| BIZ-01 | Unit-economics model in a spreadsheet: revenue per planned trip by stream versus CAC | P0 | Business Analyst | — | 1 d, then weekly |
| BIZ-02 | Hotel chains that left Яндекс Путешествия in Feb 2026: offer a direct channel | P1 | Partnerships (CEO sends) | ENG-03 | W4–W12 |
| BIZ-03 | Regional tourism body pilot (B2G): paid placement of a ready route | P1 | Partnerships (CEO sends) | DATA-02 | W6–W12 |
| BIZ-04 | Roadside service (cafes, fuel, motels) on Moscow corridors: sponsored stops | P2 | Partnerships (CEO sends) | DATA-02 | W8–W12 |
| BIZ-05 | B2B engine licensing exploration (car rental, carsharing, in-car platforms) | P2 | Partnerships + Business Analyst | ENG-04 | 3 calls |
| BIZ-06 | Trip Pro waitlist with a price test (3 price points) | P1 | Growth Marketer + Developer | ENG-05 | 2 d |
| DES-01 | Usability test of the «За рулём» UI on 10 people | P1 | UX Specialist + Designer | — | 3 d |
| DES-02 | Seasonality plan: winter ready routes (New Year, Карелия, Казань) | P2 | Designer + Growth Marketer | DATA-02 | 2 d |
| TEAM-01 | Hire a part-time paid curator | P0 | CEO (Data Curator writes the brief) | LEG-02 | W2 |
| TEAM-02 | Find a co-founder or advisor for partnerships and sales (tour operator, OTA or regional tourism background) | P1 | CEO | — | W1–W12 |
| INV-01 | Data room: metrics, unit economics, legal, cap table, 12-month plan | P0 | Business Analyst + CEO | M1–M5 | 2 d |
| INV-02 | Pitch deck built on real numbers (the targets table above) | P0 | Business Analyst + CEO | INV-01 | 2 d |

---

## Hygiene

### HYG-01 — Green `main`

**Description.** Two planner tests fail on the Sprint 4 release commit:

- `test_brands.BrandDenyListTest.test_android_strings_the_app_uses`: the deny-list entry «Суточно» matches inside the ordinary word «круглосуточно». Match the deny-list on word boundaries.
- `test_mobile_v2.ContractsV2Test.test_generator_matches_committed_files`: `docs/contracts/v2/selfcheck.json` is stale (13.16 vs 13.17). Regenerate it.

**Acceptance.**

- `python3 -m unittest discover` in `backend/planner` is green.
- The release workflow refuses to publish an APK when planner or Android tests are red.

### HYG-02 — Split god files

**Acceptance.** No Kotlin file over 800 lines in `android/app/src/main`; `gen_worlds.py` split by world section; behaviour unchanged (golden trips byte-identical, e2e green).

---

## Validation (demand)

### VAL-01 — Customer interviews

**Description.** Talk to 30–50 people who took a multi-day car trip in Russia in the last 12 months: families with children first, then dog owners and couples. Find them in VK groups, Drive2, Telegram travel channels and among friends of friends. Use a script about the past, not the future: "Tell me about your last trip. How did you plan it? What went wrong? What did it cost? What did you use?" Do not pitch Verst until the last 5 minutes.

**Acceptance.**

- `docs/traction/interviews.md`: one entry per interview (anonymous), top 5 pains ranked by frequency, the tools people actually use, what they paid for.
- A written go / adjust decision on the three core bets: overnight placement, transparent cost, dog and kids filters.

### VAL-02 — Landing page and waitlist

**Description.** A one-page site with one promise, one screenshot and a waitlist form. Run a 30–50 k ₽ ad test (VK Ads / Яндекс Директ) on two or three promise variants, for example "маршрут с ночёвками под ваш темп" versus "честная стоимость поездки до рубля".

**Acceptance.** Cost per waitlist sign-up per variant, conversion rate and the winning promise recorded in `docs/traction/`.

### VAL-03 — Competitor teardown

**Description.** Plan the same three trips in every competitor: Москва → Ярославль (weekend), Золотое кольцо with a dog, Москва → Казань (2 days). Record time to first route, quality of overnights, cost transparency and booking path. Track the Яндекс Авто concept, where Алиса plans a Суздаль weekend with stops and a hotel, as the main platform threat.

**Acceptance.** `docs/traction/competitors.md` with a comparison table and the 3 things Verst must stay best at.

### VAL-04 — Closed beta

**Description.** At least 100 families from the waitlist and the interviews get the real build (RuStore closed test plus the web planner). Ask every beta user one question after the trip date: "Did you go? What went wrong?"

**Acceptance.** Funnel numbers for the targets table, NPS of users who drove, the top 10 issues filed and triaged.

### VAL-05 — Field trips

**Acceptance.** Three real trips planned in Verst and driven, with receipts:

- for each line, the plan versus reality: fuel, tolls, lodging, food and tickets; drive times within ±20 %;
- every stop open;
- the result is recorded, and the waybill footnote changes from «Пример расчёта» to «Расчёт» only if the cost error is ≤ 15 %.

---

## Engineering (a real product)

### ENG-01 — Real road routing

**Description.** Replace `HybridRouting` with a real car router (GraphHopper or OSRM on the Russia OSM extract), as SPEC §10 planned. Keep the routing port, so the engine and golden trips change only through the adapter. Use the road model only as a labelled offline fallback.

**Acceptance.**

- Moscow → Yaroslavl, Moscow → Kazan and the Golden Ring are within 3 % of Яндекс Карты road km.
- Golden trips are re-baselined with a written justification.
- Plan p95 ≤ 10 s for ≤ 1 500 km (SPEC §16).
- No trip shown to a beta user is `route.synthetic`.

### ENG-02 — Tolls

**Acceptance.** М-11, М-12, М-4 and М-1 toll segments with day/night tariffs, `asOf` dates, and the waybill line «Платные дороги» matching the operator's calculator within 5 %.

### ENG-03 — Real hotels and working booking links

**Description.** Hotels come from a partner feed or search API through Travelpayouts. Ostrovok is the fallback if Yandex Travel terms or attribution are poor. Prices are labelled with their date. Synthetic hotels stay only in the demo flavour.

**Acceptance.**

- In the production flavour, no hotel is fictional.
- "Забронировать ночь" opens the partner with city, dates and guests prefilled.
- A test booking click appears in partner statistics with the right sub-id.

### ENG-04 — Minimal backend

**Description.** Only what the beta needs, on one VM in Russia: plan, ready routes, links, feedback and analytics ingestion. The FastAPI design in `docs/architecture.md` stays the target; ship the smallest subset.

**Acceptance.** The beta runs on it for 4 weeks with ≥ 99 % uptime; daily backups are restorable (tested once).

### ENG-05 — Analytics funnel

**Acceptance.**

- Events from SPEC §15 fire, plus one new event: `trip_driven_confirmed`.
- A weekly dashboard shows install → plan → save → booking click → driven.

### ENG-06 — Web planner MVP

**Description.** The same engine behind a web page: plan a trip, see the waybill, share a link. This covers iPhone users, who are a large share of families with a car, and lets public "how much does a trip from Moscow to X cost" pages bring search traffic.

**Acceptance.** Any of the 10 ready routes and any free A → B plan on the web; the share link opens without the app; pages are indexable.

### ENG-07 — Cold start and APK size

**Acceptance.** Measured on a mid-range phone (Galaxy A34 class); cold start to an interactive Windshield ≤ 2 s (SPEC §16), or a written plan to move planning to the backend for online users.

---

## Data (the moat)

### DATA-01 — Keep our data apart from OSM

**Description.** Under ODbL, a public derivative database of OSM data must be shared under the same licence. Store Verst's own facts in separate tables keyed by our own ids: tags, verification results, prices, photos we own, curator notes. Link OSM objects by reference only. Follow LEG-01's opinion where it differs.

**Acceptance.**

- A schema note in `docs/architecture.md`.
- A test proves that the curated tables contain no OSM-copied attributes beyond the reference id and the coordinates the lawyer allows.

### DATA-02 — Curate the 10 Moscow routes

**Description.** SPEC §9 curation workflow, limited to the 10 Moscow ready routes and their corridors (М-4, М-7, М-8, М-10/М-11, М-12, Р-22, М-2).

**Acceptance.**

- ≥ 300 places are `live` with `verified_at`.
- Every overnight town on every ready route has ≥ 2 verified lodgings, ≥ 1 of them dog-friendly.
- All 10 routes plan without warnings.

### DATA-03 — Users verify places

**Description.** After a trip date, the app asks 1–3 one-tap questions about the stops the user passed. Two "closed" reports hide a place (SPEC §9); positive answers refresh `verified_at`.

**Acceptance.** ≥ 30 % of driven trips return at least one answer; the admin shows the feedback queue.

### DATA-04 — Verified-places KPI

**Acceptance.** The admin shows verified places per route and per corridor, with age buckets (< 90 d, 90–180 d, stale).

---

## Legal

### LEG-01 — ODbL opinion

**Acceptance.** A written answer from a lawyer: can the Place DB stay proprietary given the OSM import step, and which data model makes it safe. Store it in `docs/legal/` (no personal data).

### LEG-02 — Entity and accounts

**Acceptance.** A legal entity for payouts; Travelpayouts (or a direct partner) account with the `verst_app` marker; RuStore developer account; privacy policy and terms published (SPEC §16, 152-FZ).

---

## Business (money)

### BIZ-01 — Unit economics

**Description.** Per 1 000 planned trips, model:

- affiliate revenue: click rate × booking rate × average booking × commission;
- Pro revenue;
- B2B/B2G revenue.

Compare it with cost per install and cost per planned trip from VAL-02. The review estimated affiliate-only revenue at ≈ 10 ₽ per planned trip (8 % click-through × ~10 % booking × ~12 000 ₽ × 8 %). That does not pay for paid installs on its own. Update the model weekly with real numbers.

**Acceptance.** `docs/traction/unit-economics.md` (or a linked spreadsheet), with assumptions labelled "assumed" or "measured".

### BIZ-02 — Hotel chains

**Description.** In February 2026, Azimut, Cosmos Hotel Group, Accor and Alean Collection left Яндекс Путешествия over the commission rise from 15 % to 17 %. Offer them Verst as an extra direct channel for car travellers on Moscow corridors.

**Acceptance.** ≥ 5 conversations held; ≥ 1 letter of intent or pilot.

### BIZ-03 — Regional pilot (B2G)

**Description.** Regional tourism ministries and tourism centres pay to promote routes (national project «Туризм и гостеприимство»). Offer a curated ready route with analytics on plans and trips.

**Acceptance.** ≥ 3 regions contacted from the Moscow ring (Ярославская, Владимирская, Тульская, Калужская, Тверская); ≥ 1 pilot agreed (paid or free with a paid follow-up).

### BIZ-04 — Sponsored roadside stops

**Description.** `place.sponsored` already exists in the data model. Sponsored stops are clearly labelled and never override crew filters or opening hours.

**Acceptance.** ≥ 3 roadside businesses agree to a test.

### BIZ-05 — Engine licensing

**Acceptance.** 3 calls with car rental, carsharing or in-car platform teams; a short note on interest and price expectations.

### BIZ-06 — Pro pricing test

**Acceptance.** The Pro plate on the waybill shows one of 3 prices at random; waitlist sign-up rate per price recorded; no payment taken.

---

## Design

### DES-01 — Usability test

**Acceptance.** 10 people, 3 tasks each (plan a ready route, plan A → B with a dog, find the total cost); time to first route, failures and quotes recorded; ≤ 5 fixes chosen for the beta.

### DES-02 — Seasonality

**Acceptance.** 3 winter ready routes specified; a note on what changes in the engine in winter (daylight, slower speeds, closed sights).

---

## Team

### TEAM-01 — Paid curator

**Acceptance.** A part-time curator hired, trained on the SPEC §9 workflow, with a measured throughput (verified places per hour).

### TEAM-02 — Partnerships co-founder or advisor

**Acceptance.** At least one person with a travel-industry sales background is committed (co-founder, advisor with equity or a paid contractor) and named in the deck.

---

## Investor pack

### INV-01 — Data room

**Acceptance.** One folder with:

- the targets table filled with real numbers;
- unit economics, interview summary, competitor teardown;
- legal (entity, ODbL opinion, partner agreements);
- the 12-month plan and use of funds.

### INV-02 — Deck

**Acceptance.** ≤ 12 slides: problem (from interviews), product (real screenshots), traction (beta numbers), money (unit economics, first revenue or pilot), moat (verified places KPI), competition (incl. Yandex), team, ask with milestones per tranche.
