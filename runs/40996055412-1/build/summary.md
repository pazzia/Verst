# CI run 40996055412 · build · 754539fac2 · refs/heads/ccr-013d3489-181fz2

## gradle.unit
```json
{
  "buildFailed": false,
  "errors": 0,
  "whatWentWrong": []
}
```
## junit
```json
{
  "tests": 347,
  "failures": 0,
  "skipped": 0
}
```
## gradle.lint
```json
{
  "buildFailed": true,
  "errors": 1,
  "whatWentWrong": [
    "Execution failed for task ':core-ui:lintDebug'.\n> Lint found errors in the project; aborting build.\n  Fix the issues identified by lint, or create a baseline to see only new errors.\n  To create a baseline, run `gradlew updateLintBaseline` after adding the following to the module's build.gradle file:\n  ```\n  android {\n      lint {\n          baseline = file(\"lint-baseline.xml\")\n      }\n  }\n  ```\n  For more details, see https://developer.android.com/studio/write/lint#snapshot\n  Lint found 1 error, 4 warnings. First failure:\n  /home/runner/work/Verst/Verst/android/core-ui/src/main/res/values/strings.xml:856: Error: \"abroad_consent_body\" is not translated in \"en\" (English) [MissingTranslation]\n      <string name=\"abroad_consent_body\">Поездку за границу строит только сервер Версты. На тестовый сервер в Нидерландах уйдут точки маршрута, состав экипажа, бюджет и машина. Маршрут там не хранится. Без связи такую поездку не построить.</string>\n              ~~~~~~~~~~~~~~~~~~~~~~~~~~\n     Explanation for issues of type \"MissingTranslation\":\n     If an application has more than one locale, then all the strings declared\n     in one language should also be translated in all other languages.\n     If the string should not be translated, you can add the attribute\n     translatable=\"false\" on the <string> element, or you can define all your\n     non-translatable strings in a resource file called donottranslate.xml. Or,\n     you can ignore the issue with a tools:ignore=\"MissingTranslation\"\n     attribute.\n     You can tell lint (and other tools) which language is the default language\n     in your res/values/ folder by specifying tools:locale=\"languageCode\" for\n     the root <resources> element in your resource file. (The tools prefix\n     refers to the namespace declaration http://schemas.android.com/tools.)\n  The full lint text report is located at:\n    /home/runner/work/Verst/Verst/android/core-ui/build/intermediates/lint_intermediate_text_report/debug/lintReportDebug/lint-results-debug.txt"
  ]
}
```
## lint
```json
{
  "Warning": 23,
  "Hint": 14,
  "Error": 1
}
```
## apk
```json
{
  "file": "app-demo.apk",
  "bytes": 48567469,
  "mb": 48.57,
  "sha256": "3b99b8159ab721616ebb822fd08d431055b2be2e94203dcc1374e089ddc3f669",
  "abis": [
    "arm64-v8a",
    "x86_64"
  ],
  "largestEntries": {
    "lib": 24805600,
    "assets": 13994595,
    "classes.dex": 4252443,
    "classes2.dex": 3686300,
    "resources.arsc": 790636,
    "res": 586353,
    "okhttp3": 41543,
    "kotlin": 12053,
    "META-INF": 11516,
    "AndroidManifest.xml": 2538,
    "DebugProbesKt.bin": 780,
    "kotlin-tooling-metadata.json": 284
  },
  "warnMb": 45.0,
  "failMb": 60.0,
  "abroadEntries": []
}
```
## steps.build
```json
{
  "assemble": "success",
  "unit": "success",
  "lint": "failure",
  "licences": "success",
  "apk": "success"
}
```
## gradle.assemble
```json
{
  "buildFailed": false,
  "errors": 0,
  "whatWentWrong": []
}
```
## gradle.toolchain
```json
{
  "buildFailed": false,
  "errors": 0,
  "whatWentWrong": []
}
```

## First errors
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
