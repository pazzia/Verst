# CI run 41546333192 · build · c6a8936ee0 · refs/heads/ccr-013d3489-181fz2

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
  "bytes": 49850714,
  "mb": 49.85,
  "sha256": "c34366e5d99c1fd6238ef1198407fdb31ce6933c6e684d5fc2cd3433b416e1ce",
  "abis": [
    "arm64-v8a",
    "x86_64"
  ],
  "largestEntries": {
    "lib": 24805600,
    "assets": 14849151,
    "classes.dex": 4252449,
    "classes2.dex": 4103262,
    "resources.arsc": 800888,
    "res": 596332,
    "okhttp3": 41543,
    "kotlin": 12053,
    "META-INF": 11516,
    "AndroidManifest.xml": 2537,
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
[unit] Test - ScreensScreenshotTest > cardHotelArea
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.ScreensScreenshotTest > cardHotelArea: java.lang.AssertionError: Failed: assertExists.
Reason: Expected exactly '1' node but could not find any node that satisfies: (Text + InputText + EditableText contains 'Гостиница в демо-сборке вымышленная' (ignoreCase: false))
```
