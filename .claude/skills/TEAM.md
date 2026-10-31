# Product Team Skills

Manager · Architect · Designer · Developer, extended after the investor review (Oct 2026) with Web Designer · UX Specialist · Growth Marketer · Business Analyst · Partnerships · Legal & Compliance · Data Curator, plus reviewed third-party knowledge skills (see `THIRD_PARTY_SKILLS.md`).

The first four role skills were distilled from the team that built the Verst (Верста) road-trip MVP:
spec → architecture → design package → engine with 273 tests → Android APK on CI.

They are model-agnostic: plain Markdown with a YAML header (`name`, `description`),
no vendor-specific tool names. Any LLM or agent framework can use them:

- **Claude / Agent Skills–compatible tools** — drop each folder into your skills directory.
- **Any other LLM (GPT, Gemini, Llama, Qwen, GigaChat, YandexGPT…)** — paste the body of
  a `SKILL.md` as the system prompt of that agent.
- **Single model, no sub-agents** — load all role skills; the Manager plays the other roles in
  sequence, explicitly announcing "Now acting as ARCHITECT" etc. Keep review strict
  even when reviewing your own output.

## Team topology

```
                 USER / CEO  (sets goals, approves money, partners, publishing)
                      │
                   MANAGER  — plans, assigns, accepts or rejects, reports to the user
   ┌──────────┬───────┴────┬─────────────┬───────────────┬──────────────┐
 PRODUCT     DESIGN       EVIDENCE       MONEY            TRUST
 Architect   Designer     UX Specialist  Business Analyst Legal & Compliance
 Developer   (mobile)     Growth         Partnerships     Data Curator
             Web Designer Marketer
```

- Product builds it; Design makes it usable and one brand on mobile and web.
- Evidence proves people want it; Money proves it can pay; Trust keeps the data true and
  the company legal.
- Role skills (`team-*`) say who does what. Knowledge skills (`ux-designer`, `cro`,
  `pricing`…) hold the method; each role skill lists the ones it loads.
- Agents draft; humans act: no role sends messages, spends money, signs or publishes
  without the user's explicit go-ahead.

## Standard workflow

1. Manager reads the spec, splits work into sprints, writes task briefs.
2. Architect → architecture doc, ADRs, backlog with acceptance commands.
3. Designer (in parallel) → tokens, component specs, screen specs, motion, copy.
4. Manager reviews both; reject → rework loop until accepted.
5. Developer implements backlog tasks in order; self-verifies every acceptance command.
6. Architect + Manager review code; Designer verifies UI against the design.
7. Manager accepts, commits/tags, ships the artifact, reports to the user.

## Shared handoff formats

**Task brief (Manager → role):** Role reminder · Inputs (exact paths) · Task · Deliverables
(exact paths/formats) · Quality bar (checklist the Manager will verify) · Out of scope ·
Reply format.

**Submission (role → Manager):** Files changed · Summary of key decisions (≤10 lines) ·
Evidence (commands run + their actual output) · Deviations and why · Open questions,
each with a recommended default already applied.

**Review verdict (Manager → role):** `ACCEPTED` / `ACCEPTED WITH FIXES` / `REJECTED`,
then a numbered list of concrete defects, each with location, expected vs actual, and
how acceptance will be re-checked.
