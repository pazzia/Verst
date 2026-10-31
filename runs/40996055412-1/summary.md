# Run 177 (40996055412-1) — failure

sha `754539fac290` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |

APK: 48.57 MB · ABIs ['arm64-v8a', 'x86_64'] · sha256 3b99b8159ab72161…

Screenshots: 138

## Errors (first 60)
```
[lint] Gradle: Execution failed for task ':core-ui:lintDebug'. - Execution failed for task ':core-ui:lintDebug'.
> Lint found errors in the project; aborting build.
  Fix the issues identified by lint, or create a baseline to see only new errors.
  To create a baseline, run `gradlew updateLintBaseline` after adding the following to the module's build.gradle file:
  ```
  android {
      lint {
          baseline = file("lint-baseline.xml")
      }
  }
  ```
  For more details, see https://developer.android.com/studio/write/lint#snapshot
  Lint found 1 error, 4 warnings. First failure:
  /home/runner/work/Verst/Verst/android/core-ui/src/main/res/values/strings.xml:856: Error: "abroad_consent_body" is not translated in "en" (English) [MissingTranslation]
      <string name="abroad_consent_body">Поездку за границу строит только сервер Версты. На тестовый сервер в Нидерландах уйдут точки маршрута, состав экипажа, бюджет и машина. Маршрут там не хранится. Без связи такую поездку не построить.</string>
              ~~~~~~~~~~~~~~~~~~~~~~~~~~
     Explanation for issues of type "MissingTranslation":
     If an application has more than one locale, then all the strings declared
     in one language should also be translated in all other languages.
     If the string should not be translated, you can add the attribute
     translatable="false" on the <string> element, or you can define all your
     non-translatable strings in a resource file called donottranslate.xml. Or,
     you can ignore the issue with a tools:ignore="MissingTranslation"
    
[lint] Error android/core-ui/src/main/res/values/strings.xml:856 [MissingTranslation] "abroad_consent_body" is not translated in "en" (English)
```
