# Decision log

Open questions for the CEO always carry a default that is already in effect. The CEO can
overturn any default; the team then reworks the affected deliverables.

| # | Date | Question | Decision (default in effect) | Reason | Decided by |
| --- | --- | --- | --- | --- | --- |
| D-IR-01 | 2026-10-25 | Language of the investor-readiness deliverables | Engineering docs stay in English (repo rule). Everything whose reader is the CEO, a Russian lawyer, an interviewee, a partner or a site visitor is in Russian: `docs/traction/`, `docs/legal/`, `web/landing/`. | Those readers work in Russian; translating twice wastes time. | Manager |
| D-IR-02 | 2026-10-25 | Week 1 scope | HYG-01, VAL-01, VAL-02, LEG-01 (+ LEG-02 checklist), BIZ-01, TEAM-01 brief. VAL-03 desk part starts in week 2. | Backlog order: these are the M1 items; VAL-03 needs a person to run competitor apps. | Manager |
| D-IR-03 | 2026-10-25 | Ad test budget | 30 000 ₽ default for VAL-02, split evenly across the promise variants. **Nothing is spent until the CEO approves the test plan.** | Low end of the backlog's 30–50 k ₽ range; enough for a first cost-per-lead read. | Manager (needs CEO approval) |
| D-IR-04 | 2026-10-25 | Landing page hosting and domain | The page is built as static files in `web/landing/` with no hosting assumed. The CEO picks the domain and host; nothing is published in the company's name before that. | Publishing is the CEO's call. | Manager (needs CEO decision) |
| D-IR-05 | 2026-10-25 | Waitlist mechanism | Primary call to action: join a Telegram channel (no personal data collected by Verst). Secondary: an e-mail form whose endpoint is configurable and stays disabled until the privacy policy and consent text are approved by Legal. | Avoids collecting personal data (152-FZ) before the legal basis is in place, but keeps an owned channel. | Manager |
| D-IR-06 | 2026-10-25 | Web analytics on the landing page | Яндекс Метрика, with goals defined in the tracking plan; no personal data in events or UTM tags; counter ID left as a config value for the CEO. | Works in Russia and is free; the app already plans AppMetrica. | Manager |
