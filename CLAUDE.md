# CLAUDE.md — «Верста»

Android road-trip planner for Russia and 9 neighbour countries: a Kotlin/Compose app, one Python engine
(`backend/planner/verst_planner`, on the phone through Chaquopy and on the server), a FastAPI server
(`backend/api`), data built from open sources in GitHub Actions.

## Read first

1. **`docs/SESSION-STATE.md`**: the checkpoint of what is in flight, what waits on the CEO and what comes next.
   Read it after every compaction, `/clear` or new session; the file is the memory, not the conversation.
   **Update it at the end of every task** (short, facts only, newest first).
2. `docs/PROJECT-STATE.md`: the full handover (product, engine, server, app, data, infra, rules). Read the
   section you need, not the whole file.
3. `docs/decisions.md`: every CEO decision (D-IR-xx) with its reason. A new decision gets a row.
4. Path rules in `.claude/rules/` load by themselves when you edit those paths.

## Rules from the CEO (do not break)

**Talking to the CEO**
- The CEO writes in Russian. Answer in Russian, plain words, no jargon without a gloss.
- Times are Moscow time (UTC+3).
- Recommendations go **line by line**.
- **Server commands: one line per separate code block**, so each copies with one tap. The CEO runs them.
  The one exception (D-IR-29): Claude runs `status`, `update`, `recreate` and `errors` on the test server
  through `.github/workflows/test-server.yml` (a forced-command key, `infra/api/server-ops.sh`). Nothing else.
- **Before every deploy (`update`, `recreate`) ask the CEO and wait for his «да» (D-IR-30).** The question says,
  in Russian, line by line:
  1. what will be done (the action, the commits going in, what changes for the app and the testers);
  2. the risks (downtime, what can break, data or settings touched) and how it is rolled back.
  `status` and `errors` only read and need no question.

**Data and money**
- **Never invent data.** Unknown is shown as «нет данных» / «не проверено», never as a default
  (ADR-0019). Every external fact carries its source and date; mark what you could not verify.
- **No paid data services** («Пока в платные сервисы не идём»).

**Brands, keys, secrets**
- Real brand names («Яндекс», «Google Карты», «2ГИС») only in `handoff_*` / `handoff_settings_*` strings and
  in `exit_book_partner`. `BrandDenyListTest` checks this. Place names from OSM data are not app copy: a fuel
  station shows its real brand (D-IR-28).
- The Yandex private signing key is never put into the APK.
- Never commit `.env`, keystores, tokens or passwords. The commit guard (`tools/hooks/guard_commit.py`)
  blocks them. Secrets live in GitHub Secrets or in `.env` on the server.

**APK size (D-IR-26)**
- CI budget: warn above 45 MB, fail above 60 MB (`android.yml`, `diagnose.py apk`).
- Going over it is allowed only with the CEO's permission, asked **before** the change. The request shows:
  1. the size it adds (measured from a CI build, not estimated);
  2. evidence that it really improves the app;
  3. why the same result cannot be done on the server instead.
- Never raise the budget or silence the check on your own.

**Server and law**
- **152-FZ:** the Netherlands VM (`docs/ops/test-server.md`) is for tests only. A server in Russia comes before
  any beta with outside users.

**Git**
- Work only on the session's designated branch (`ccr-…`). Never push elsewhere without explicit permission.
- **Merge to `main` only after the CEO's word «Сливай».** Open a PR only when asked.
- Subagents never run git commands that change state; the main agent commits.
- Commit messages: English subject and body, then the session's attribution lines.
- **A user-visible change carries a Russian trailer line `Тестерам: <одна фраза>`** (one line per change; see
  "What's new" below). Pure refactors, docs and CI carry none.

## Engineering

**Where Android runs.** There is no Android SDK in the sandbox; the app is built and tested only in CI.
- Workflow `android.yml`, dispatched on the branch.
- Every green branch build lands at `releases/download/verst-test-latest/Verst-test-latest.apk`.
- `main` publishes `verst-latest`.

**Local checks before every push**
| What changed | Run |
| --- | --- |
| Engine | `make check` (ruff 110, `mypy --strict`, unittest) |
| Server | `cd backend/api && python3 -m pytest -q && ruff check verst_api tests && python3 -m mypy verst_api tests` |
| Engine output / contracts | `cd backend/planner && python3 tools/gen_api_contracts.py` |
| App strings | `python3 design/tools/gen_strings.py --check` (edit `design/copy-ru.md`, never `strings.xml`; `values-en` is by hand) |
| Colours | `python3 design/tools/apply_day_palette.py && python3 design/tools/apply_camper_palette.py && python3 tools/sync_design_tokens.py`, then `python3 -I design/tools/apply_camper_palette.py --check` |

**Two designs (D-IR-24).** «Кемпер» (default) and «Классический» are chosen in Settings.
- A restyled screen has a camper twin `XxxCamper.kt` next to the classic file.
- The classic entry point dispatches with `if (Palette.camper) return XxxCamper(…)`.
- Shared state and action types live only in the classic file.
- A UI change usually needs both files.

**Visible change = seen.** A change to what the user sees is done only when a CI screenshot or an emulator
shot shows it: unit shots run the classic design, the emulator journey runs the camper one. Say which one you
looked at.

**Docs, not more docs.** Write the document the next person needs, not one per step. Engineering docs are in
English. Anything the CEO reads (reports, `docs/ops`, research for him) is in Russian.

## What's new (release notes)

- `tools/ci/whats_new.py` collects the `Тестерам:` trailers between the previous release and the build commit.
- `android.yml` puts them into every release's notes under «Что нового».
- `docs/WHATS-NEW.md` is the running list for people; `/changelog` updates it from the same trailers.
