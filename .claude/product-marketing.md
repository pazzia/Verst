# Verst («Верста»): product marketing context

Shared context for the team's marketing, research and partnership skills. Facts are marked
**[fact]**; everything else is a **[hypothesis]** to be confirmed by research
(`docs/backlog-investor-readiness.md`, VAL-01…VAL-04). Update this file when evidence
changes.

## Product

- **[fact]** Android app (RuStore first) that plans a multi-day car trip across Russia in
  seconds: any A → B or a ready-made trip near the start. It places overnight stops by the
  driver's comfortable daily mileage and shows the full cost with formulas (fuel, tolls,
  lodging, food, tickets, 10 % reserve). No registration. Works offline once saved. UI in
  Russian, visual concept «За рулём» (the view from the driver's seat).
- **[fact, Oct 2026]** Current build is a demo: hotels, cafes and fuel stations are
  fictional, distances are estimated, booking is a mock. Sights are real (open data). Do
  not market the demo as a working product.
- Hand-off of navigation to Яндекс Навигатор / Яндекс Карты / 2ГИС.

## Audience

- **[hypothesis]** Primary: a family driver (2 adults, 1–2 children, often a dog)
  planning a 1–4 day trip from a big city, starting with Moscow.
- **[hypothesis]** Secondary: couples on a weekend trip; long-haul drivers who need one good
  overnight.
- **[fact]** Car travel is growing in Russia. The Ministry of Economic Development
  expected 43 % of tourists to travel by car in summer 2025, against 38 % a year earlier.
  Industry forecasts for 2030 range from 70 % to 80 % (forecasts, not measurements).

## Problem and promise

- **[hypothesis]** Pains: map apps navigate but do not plan a multi-day trip around kids,
  a dog, a pace and a budget; AI planners invent routes and ignore opening hours; the
  real cost of a trip is unknown until it is over.
- **[hypothesis]** Candidate promises to test (VAL-02):
  - «Маршрут с ночёвками под ваш темп за 10 секунд»;
  - «Честная стоимость поездки: каждая строка с формулой»;
  - «С детьми и собакой: только места, где вам рады».

## Differentiators

- Overnight placement by daily mileage, shifted to the best nearby town, with the reason
  shown.
- Transparent cost with formulas and a budget check.
- **[hypothesis]** Verified family/dog/parking tags. Not built yet: 0 verified places
  as of Oct 2026.

## Alternatives and competitors

- Яндекс Карты, 2ГИС: navigation, not multi-day planning.
- Яндекс Путешествия with Алиса AI: trip help and hotel booking. The Яндекс Авто concept
  (April 2026) shows Алиса planning a Суздаль weekend with stops and a hotel. This is the main
  platform threat.
- Roadtrippers (foreign), TripforTeam (RuStore), generic AI trip planners, paper/Telegram
  route guides, doing it by hand.

## Business model

- **[fact]** Planned: affiliate hotel and excursion bookings (via Travelpayouts), a Trip
  Pro waitlist (no payments in the MVP).
- **[hypothesis]** Additional: regional tourism pilots (B2G), sponsored roadside stops
  (clearly labelled), engine licensing. Affiliate alone is ≈ 10 ₽ per planned trip by the
  investor review's estimate, so it does not pay for paid installs on its own.

## Voice

- Russian, plain and calm, the tone of an experienced travelling friend. Numbers with «≈»
  when estimated; never promise exact prices. No fake urgency, no fake reviews.

## Constraints

- Russian advertising law (38-FZ): online ads labelled with ERID markers; no unsolicited
  ad mailings.
- 152-FZ: no personal data in analytics or UTM tags; servers in Russia.
- Brand rule from the repo: real brand names appear only in navigator hand-off texts.
