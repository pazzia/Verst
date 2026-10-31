# CI run 40792245522 · build · 2418d1e3cc · refs/heads/ccr-013d3489-181fz2

## gradle.unit
```json
{
  "buildFailed": true,
  "errors": 5,
  "whatWentWrong": [
    "Execution failed for task ':core-model:test'.\n> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/core-model/build/reports/tests/test/index.html",
    "Execution failed for task ':app:testDebugUnitTest'.\n> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html"
  ]
}
```
## junit
```json
{
  "tests": 301,
  "failures": 3,
  "skipped": 0
}
```
## gradle.lint
```json
{
  "buildFailed": false,
  "errors": 0,
  "whatWentWrong": []
}
```
## lint
```json
{
  "Warning": 23,
  "Hint": 13
}
```
## apk
```json
{
  "file": "app-demo.apk",
  "bytes": 48387425,
  "mb": 48.39,
  "sha256": "55f36d40508337ef90fcda89d646e94357510ab11e60c64599ce3e1c515f494a",
  "abis": [
    "arm64-v8a",
    "x86_64"
  ],
  "largestEntries": {
    "lib": 24805600,
    "assets": 13920151,
    "classes.dex": 4252451,
    "classes2.dex": 3619238,
    "resources.arsc": 758088,
    "res": 586353,
    "okhttp3": 41543,
    "kotlin": 12053,
    "META-INF": 11516,
    "AndroidManifest.xml": 2524,
    "DebugProbesKt.bin": 780,
    "kotlin-tooling-metadata.json": 284
  },
  "warnMb": 45.0,
  "failMb": 60.0
}
```
## steps.build
```json
{
  "assemble": "success",
  "unit": "failure",
  "lint": "success",
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
[unit] Test - V2ContractsTest > noDataPricesAndFoodStopsDecode
[unit] Test - ScreensScreenshotTest > cityNotEnoughNoData
[unit] Test - VerstFlowTest > notEnoughNoDataCarriesTheEnginesMessage
[unit] Gradle: Execution failed for task ':core-model:test'. - Execution failed for task ':core-model:test'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/core-model/build/reports/tests/test/index.html
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.ScreensScreenshotTest > cityNotEnoughNoData: java.lang.NullPointerException
[test] app.verst.nav.VerstFlowTest > notEnoughNoDataCarriesTheEnginesMessage: org.junit.ComparisonFailure: expected:<[no_data]> but was:<[few_places]>
[test] app.verst.core.model.V2ContractsTest > noDataPricesAndFoodStopsDecode: org.junit.ComparisonFailure: city_route-error-no-data.json expected:<[no_data]> but was:<[few_places]>
```
