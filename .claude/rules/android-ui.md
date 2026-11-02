---
paths:
  - "android/app/src/main/kotlin/app/verst/feature/**"
  - "android/app/src/main/kotlin/app/verst/MainActivity.kt"
  - "android/core-ui/src/main/kotlin/**"
---

# Android UI rules

- **Two designs (D-IR-24).** A restyled screen has a camper twin `XxxCamper.kt` in the same package. The
  classic entry point starts with `if (Palette.camper) return XxxCamper(…)`. State and action types (`XxxUi`,
  `XxxActions`) live only in the classic file. Change both files unless the change is design-specific, and say
  which design you changed.
- **Text:** every user-facing string comes from `R.string.*`.
  - New keys go into `design/copy-ru.md` and are generated: `python3 design/tools/gen_strings.py`.
  - English goes by hand into `android/core-ui/src/main/res/values-en/strings.xml`; lint fails on a missing
    translation.
- **Colours:** only `DesignTokens.color.*` (`C.camper.*` in camper twins), never `Color(0x…)` in a screen.
  - New tokens go into `design/tokens*.json` and are regenerated (CLAUDE.md, «Colours»).
  - Text contrast is ≥ 4.5:1 (`apply_camper_palette.py --check`).
- **Brands:** real brand names only in `handoff_*` strings (`BrandDenyListTest` fails otherwise).
- **No state in UI:** a screen gets a `…Ui` data class and an `…Actions` interface; logic lives in `nav/*Flow.kt`.
- **Test tags** are the e2e contract (`app/src/androidTest`): keep them identical in both twins.
- **Touch targets** ≥ 44 dp (`DesignTokens.size.touchMin`). Animations respect `LocalReducedMotion`.
- **Done = seen:** a visible change is done only after a CI screenshot (unit shots run the classic design, the
  emulator journey runs the camper one) shows it.
