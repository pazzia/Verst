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
W1–W4   SOC-01 demand check for community routes (inside VAL-01 interviews)
Now     SPIKE-01 dynamic planning prototype (research, allowed under the freeze) ──▶ after M2: ARCH-01 · DATA-05 · ENG-10 · DES-03 ──▶ ENG-09 / LEG-03 · BIZ-07
After   SOC-02 saved routes (after M2) ──▶ SOC-03 public routes + ratings (after VAL-04) ──▶ SOC-04 paid routes · SOC-05 contests
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
| LEG-02 | Legal entity (self-employed / ИП / ООО), Travelpayouts and partner accounts, Яндекс hand-off signing key (D-IR-17), privacy policy | P0 | Legal & Compliance + CEO | — | W1–W2 |
| BIZ-01 | Unit-economics model in a spreadsheet: revenue per planned trip by stream versus CAC | P0 | Business Analyst | — | 1 d, then weekly |
| BIZ-02 | Hotel chains growing direct sales against the 17 % aggregator commission: offer a direct channel | P1 | Partnerships (CEO sends) | ENG-03 | W4–W12 |
| BIZ-03 | Regional tourism body pilot (B2G): paid placement of a ready route | P1 | Partnerships (CEO sends) | DATA-02 | W6–W12 |
| BIZ-04 | Roadside service (cafes, fuel, motels) on Moscow corridors: sponsored stops | P2 | Partnerships (CEO sends) | DATA-02 | W8–W12 |
| BIZ-05 | B2B engine licensing exploration (car rental, carsharing, in-car platforms) | P2 | Partnerships + Business Analyst | ENG-04 | 3 calls |
| BIZ-06 | Trip Pro waitlist with a price test (3 price points) | P1 | Growth Marketer + Developer | ENG-05 | 2 d |
| DES-01 | Usability test of the «За рулём» UI on 10 people | P1 | UX Specialist + Designer | — | 3 d |
| DES-02 | Seasonality plan: winter ready routes (New Year, Карелия, Казань) | P2 | Designer + Growth Marketer | DATA-02 | 2 d |
| SPIKE-01 | Prototype of dynamic planning on provider-agnostic sources (ADR-0021 §5): Москва → Казань and Денпасар → Убуд → Ловина; quality, time, cost per plan | P1 | Architect + Developer + Data Curator (rating) | ENG-01 | 1–2 wk |
| ARCH-01 | Capability ports, provider manifest and `ProviderSelector` with fallback to open data (ADR-0021 §2.1–2.3) | P1 | Architect | SPIKE-01 | 3 d |
| DATA-05 | Server-side open place index (OSM + Wikidata) with corridor search, beyond Russia; the packaged catalogue becomes the offline cache | P1 | Architect + Data Curator | SPIKE-01, LEG-01 | 5–7 d |
| ENG-08 | Routing graphs per country (Russia whole, then the countries chosen after SPIKE-01) | P2 | Architect | ENG-01 | 3 d |
| ENG-09 | Commercial place search / enrichment adapters with licence-driven storage, attribution and cost guard (ADR-0021 §2.4–2.6) | P2 | Developer + Legal & Compliance | ARCH-01, LEG-03 | 5 d |
| ENG-10 | `POST /v2/plan` on the server with the preference profile; the app plans online through it and falls back to the on-device engine offline | P1 | Architect + Developer | ARCH-01, ENG-04 | 3–5 d |
| DES-03 | Questionnaire 2.0 (level, density, interests, free text) and vendor-map display where a licence requires it | P1 | Designer + UX Specialist | SPIKE-01 | 3 d |
| LEG-03 | Terms review of each candidate provider (storage, display, attribution) and the foreign-entity question for providers abroad | P1 | Legal & Compliance (lawyer) | LEG-02 | 1 wk |
| BIZ-07 | Cost per plan of commercial providers in the BIZ-01 model; budget per plan and per month | P1 | Business Analyst | SPIKE-01 | 1 d |
| SOC-01 | Demand check for user and author routes: past-behaviour question in the VAL-01 interviews | P1 | UX Specialist (CEO asks) | — | 0.5 d |
| SOC-02 | Save a planned or driven trip as a personal route and replan it later as a ready route | P2 | Architect + Developer + Designer | M2 (feature freeze), SOC-01 | 3 d |
| SOC-03 | Public user and author routes, rated only by people who drove them | P2 | Architect + Developer + Designer + Data Curator (moderation) | SOC-02, VAL-04, DATA-03, LEG-02 | 5 d |
| SOC-04 | Paid author routes (marketplace with a revenue share) | P2 | Business Analyst + Legal & Compliance + Developer | SOC-03, LEG-02 | 5 d |
| SOC-05 | Contests with a cash prize for the best-rated routes | P2 | Growth Marketer + Legal & Compliance (CEO approves the prize fund) | SOC-03, LEG-02 | 2 d, then per contest |
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

**Acceptance.** A legal entity for payouts; Travelpayouts (or a direct partner) account with the `verst_app` marker; RuStore developer account; privacy policy and terms published (SPEC §16, 152-FZ). The Яндекс URL-signing key is requested once the entity, the domain and the RuStore page exist, and arrives before VAL-04 (D-IR-17); the app can already sign the links; the key is to live on our backend, not in the public APK (decision open).

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

**Description.** In February 2026, Azimut, Cosmos Hotel Group, Accor, Alean Collection and others left Яндекс Путешествия over the commission rise from 15 % to 17 %; by 22.04.2026 most returned after an РСТ-brokered deal, with the 17 % base commission unchanged (see `docs/partners/targets.md`). Offer chains that are growing direct sales an extra direct channel for car travellers on Moscow corridors. Targets and drafts: `docs/partners/`.

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

## Community routes (CEO idea, Oct 26, 2026)

**Idea.**
- A trip a user planned or drove can be saved and reused later as a ready route.
- Users and invited authors publish routes; people who drove a route rate it, so the best routes rise to the top. Authors can be local guides, travel bloggers or regional tourism bodies.
- Later stages:
  - paid author routes, as a marketplace with a revenue share;
  - contests with a cash prize for the routes that collect the most positive ratings.

**Why it matters to the investor.** It answers three gaps from the review:
- **Content.** Today every ready route is built by the team (DATA-02). Community routes add content without adding curators.
- **Distribution.** An author who publishes a route links to it for their own audience, so authors are a growth channel as well as content.
- **Moat and money.** A catalogue rated by real drivers is hard to copy and gives a network effect, and the marketplace commission is a second revenue stream.

**Risks to manage.**
- **Cold start.** Ratings mean nothing with few users.
  - Seed the catalogue with author routes first: invited authors, the 10 curated routes (DATA-02) and regional bodies (BIZ-03).
  - Open publishing to all users only after the closed beta (VAL-04).
- **Trust.** The product's promise is honest data. A community route keeps only the choice of stops and overnights; the engine re-checks every stop at plan time (opening hours, crew filters, «не проверено» per ADR-0019).
- **Rating fraud.** The risk is highest once money is involved.
  - Only users who confirmed they drove the route can rate it (`trip_driven_confirmed`, `docs/traction/tracking-plan.md`).
  - One rating per person per route.
  - Anomalies are reviewed before any payout.
- **Privacy (152-FZ).** A GPS track is personal data and can reveal a home address.
  - Publish the route's stops, never the raw track, and cut the first and last kilometres.
  - Ask for explicit consent before publishing.
  - The author name is a pseudonym by default.
- **Legal.** Everything below goes to Legal before launch; it needs LEG-02.
  - Terms of use: a licence for user content and the moderation duty.
  - Contest rules (ГК РФ гл. 57, public contest). Entry is free, so the contest is not a lottery (138-FZ).
  - Prize tax: НДФЛ, with the organiser as tax agent. If the contest counts as advertising, prizes above 4 000 ₽ a year are taxed at 35 %.
  - Paid routes need a legal entity, payouts to authors (самозанятые or ИП) and receipts (54-FZ).
- **Feature freeze.** The app code waits for M2. The demand check (SOC-01) runs now and decides whether SOC-03…05 go ahead.

### SOC-01 — Demand check (now, no code)

**Description.** Add one past-behaviour question to the VAL-01 interview kit, after Q6: «Вы когда-нибудь ехали по чужому маршруту — из блога, Telegram-канала, от друзей? А своим маршрутом после поездки с кем-нибудь делились? Как?». Q21 already asks whether people have paid for a ready route.

**Status (2026-10-27).** Question 6а is in `docs/traction/interview-kit.md` together with its note field; the shares are counted once the interviews are done.

**Acceptance.** `docs/traction/interviews.md` records three shares of interviewees: those who drove someone else's route in the last 2 years, those who shared their own, and those who paid for one. The go/no-go for SOC-03…05 is written next to these numbers.

### SOC-02 — Save and reuse a route

**Description.**
- «Сохранить как маршрут» on the waybill keeps the trip's stops and overnights as a personal ready route.
- The route can be replanned for new dates and a different crew; the engine re-checks every stop.
- After a confirmed drive, the user marks which stops they actually made (the same flow as DATA-03) and saves the route as driven.
- Recording the drive automatically needs background location (foreground service, a RuStore permission review). It is a later option, not the first version.
- Routes are stored on the device first; backend sync (ENG-04) is optional.

**Acceptance.**
- A saved route replans within the ready-route time budget.
- Replanning with a different crew applies the crew filters.
- No raw GPS track is stored.

### SOC-03 — Public routes and ratings

**Description.**
- An author publishes a saved route with a title, a short description and photos they own.
- The catalogue shows routes near the user's start, sorted by rating from people who drove them.
- A route goes public only after the Data Curator's moderation queue. Users can report wrong or unsafe content.

**Acceptance.**
- At least 20 author routes before publishing opens to all users.
- Ratings come only from confirmed drivers.
- Moderation takes 48 h or less.
- Four weeks after launch, the share of planned trips started from community routes is measured.

### SOC-04 — Paid author routes

**Description.**
- The author sets a price. The preview shows the outline; the buyer gets the full route with the author's notes and tips.
- Revenue is shared with the author.
- Run a price test first, as in BIZ-06, without taking payments.

**Acceptance.**
- BIZ-01 is updated with the marketplace commission.
- A lawyer approves the payout scheme.
- The first 10 paid sales are made.

### SOC-05 — Contests

**Description.** A contest per season or holiday, for example «лучший маршрут на майские». A cash prize goes to the route with the most positive ratings from confirmed drivers. The rules are published before the start, and entry is free.

**Acceptance.**
- Legal approves the rules.
- Anti-fraud review is done before the payout.
- The effect is measured against the month before: new routes published and trips planned during the contest.

---

## Dynamic planning without vendor lock-in (CEO concept, Oct 27, 2026; ADR-0021)

**Concept.**
- The user gives any two points in any country, plus wishes and constraints. The engine builds the road skeleton, searches places along it in live data, scores them against the questionnaire and re-routes through the best ones.
- Good trips are saved, and an owner can publish one for others to repeat exactly (SOC-02/03).
- **No binding to a vendor.** Each capability (routing, place search, enrichment, lodging, map display, hand-off) is served by a provider chosen per request: coverage, licence, budget and health decide. The chain always ends in open data and our own facts.

**Why not one vendor.**
- Google or Яндекс costs ≈ $1–2 per plan against ≈ 3 ₽ of revenue per trip.
- Their terms forbid storing place data, so saved and shared trips would break.
- Google billing is closed to Russian companies.
- It means lock-in to the main platform competitor.

**Order.**
1. SPIKE-01 measures quality, time and cost per plan on Москва → Казань and a Bali corridor.
2. Then ARCH-01, DATA-05 and ENG-10, after M2 under the feature freeze unless the CEO moves it.
3. ENG-09 and LEG-03 for the commercial providers.
4. DES-03 for the questionnaire and vendor maps.
5. BIZ-07 for the money.

**Acceptance (SPIKE-01).** The report gives:
- the share of stops worth stopping at, against the current catalogue;
- the share of stops with known hours;
- server plan time p95 ≤ 5 s;
- the commercial cost per plan in ₽;
- a go / no-go.

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
