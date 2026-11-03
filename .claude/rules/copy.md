---
paths:
  - "design/copy-ru.md"
  - "android/core-ui/src/main/res/values*/strings.xml"
  - "android/core-ui/src/main/res/values*/plurals.xml"
---

# Copy rules

- `design/copy-ru.md` is the source. `values/strings.xml` and `plurals.xml` are generated: never edit them by
  hand. Run `python3 design/tools/gen_strings.py`, then `--check`.
- `values-en/strings.xml` is kept by hand: every new key gets an English line, or lint fails (MissingTranslation).
- Plain Russian; «ё» where it is pronounced; numbers with a non-breaking space before units (the generator does
  it). No promises the data cannot keep: unknown is «нет данных» / «не проверено» (ADR-0019).
- Brand names only in `handoff_*` / `handoff_settings_*` keys and `exit_book_partner`.
