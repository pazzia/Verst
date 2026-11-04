# CI run 41672389000 · build · 481ded2c27 · refs/heads/ccr-013d3489-181fz2

## gradle.unit
```json
{
  "buildFailed": true,
  "errors": 3,
  "whatWentWrong": [
    "Execution failed for task ':app:testDebugUnitTest'.\n> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html"
  ]
}
```
## junit
```json
{
  "tests": 353,
  "failures": 2,
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
  "Warning": 26,
  "Hint": 17
}
```
## apk
```json
{
  "file": "app-demo.apk",
  "bytes": 49852914,
  "mb": 49.85,
  "sha256": "88d5307a1cfcb47773b24db8b15b3f1de292a9abe9a427694c59bb209e93bce7",
  "abis": [
    "arm64-v8a",
    "x86_64"
  ],
  "largestEntries": {
    "lib": 24805600,
    "assets": 14850943,
    "classes.dex": 4252451,
    "classes2.dex": 4103458,
    "resources.arsc": 803084,
    "res": 596332,
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
[unit] Test - AnalyticsJourneyTest > searchInstrumentsWaybillHandoffReportShareAndDrivenEvents
[unit] Test - VerstFlowTest > oneTripOneDistanceThenWaybillReplaceSaveReopen
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.analytics.AnalyticsJourneyTest > searchInstrumentsWaybillHandoffReportShareAndDrivenEvents: java.util.NoSuchElementException: Collection contains no element matching the predicate.
[test] app.verst.nav.VerstFlowTest > oneTripOneDistanceThenWaybillReplaceSaveReopen: java.lang.AssertionError: expected:<Road> but was:<Instruments>
```
