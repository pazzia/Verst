# CI run 41675968539 · build · 4b87e4fb2f · refs/heads/ccr-013d3489-181fz2

## gradle.unit
```json
{
  "buildFailed": true,
  "errors": 2,
  "whatWentWrong": [
    "Execution failed for task ':app:testDebugUnitTest'.\n> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html"
  ]
}
```
## junit
```json
{
  "tests": 353,
  "failures": 1,
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
  "bytes": 50196978,
  "mb": 50.2,
  "sha256": "130b71a58fea8273adabed3603ba1505c274014441b35cfa30fc5dc78bc7d9f5",
  "abis": [
    "arm64-v8a",
    "x86_64"
  ],
  "largestEntries": {
    "lib": 24805600,
    "assets": 15185400,
    "classes.dex": 4252451,
    "classes2.dex": 4103855,
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
[unit] Test - VerstFlowTest > oneTripOneDistanceThenWaybillReplaceSaveReopen
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.nav.VerstFlowTest > oneTripOneDistanceThenWaybillReplaceSaveReopen: java.lang.AssertionError: expected:<TripFigures(km=542, days=2)> but was:<TripFigures(km=540, days=2)>
```
