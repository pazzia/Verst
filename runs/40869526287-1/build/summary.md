# CI run 40869526287 · build · 261dfd1bab · refs/heads/ccr-013d3489-181fz2

## gradle.unit
```json
{
  "buildFailed": true,
  "errors": 4,
  "whatWentWrong": [
    "Execution failed for task ':app:testDebugUnitTest'.\n> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html"
  ]
}
```
## junit
```json
{
  "tests": 320,
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
  "bytes": 48419021,
  "mb": 48.42,
  "sha256": "cb75113b58b6eb742f96c5edbcfee4f760194c3d6510a81b84068443e3567beb",
  "abis": [
    "arm64-v8a",
    "x86_64"
  ],
  "largestEntries": {
    "lib": 24805600,
    "assets": 13920858,
    "classes.dex": 4252449,
    "classes2.dex": 3628587,
    "resources.arsc": 773288,
    "res": 586353,
    "okhttp3": 41543,
    "kotlin": 12053,
    "META-INF": 11516,
    "AndroidManifest.xml": 2538,
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
[unit] Test - ScreensScreenshotTest > settingsDefault
[unit] Test - HandoffLauncherTest > googleMapsAppElseTheBrowser
[unit] Test - HandoffLauncherTest > yandexMapsAppElseTheWebRoute
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.ScreensScreenshotTest > settingsDefault: java.lang.AssertionError: expected:<[currency:EUR, theme:DAY]> but was:<[]>
[test] app.verst.platform.HandoffLauncherTest > googleMapsAppElseTheBrowser: java.lang.AssertionError: expected:<false> but was:<true>
[test] app.verst.platform.HandoffLauncherTest > yandexMapsAppElseTheWebRoute: java.lang.AssertionError: expected:<Browser> but was:<Maps>
```
