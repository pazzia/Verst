# CI run 40646242825 · build · 08de87c569 · refs/heads/ccr-013d3489-181fz2

## gradle.unit
```json
{
  "buildFailed": true,
  "errors": 2,
  "whatWentWrong": [
    "Execution failed for task ':core-model:test'.\n> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/core-model/build/reports/tests/test/index.html"
  ]
}
```
## junit
```json
{
  "tests": 295,
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
  "Warning": 28,
  "Hint": 13
}
```
## apk
```json
{
  "file": "app-demo.apk",
  "bytes": 47687273,
  "mb": 47.69,
  "sha256": "77195521a204fb2321436c82c52a331883058edb6fa075a29c460ca5c7a05fc6",
  "abis": [
    "arm64-v8a",
    "x86_64"
  ],
  "largestEntries": {
    "lib": 24805600,
    "assets": 13271876,
    "classes.dex": 4252445,
    "classes2.dex": 3602013,
    "resources.arsc": 729788,
    "res": 586353,
    "okhttp3": 41543,
    "kotlin": 12053,
    "META-INF": 11516,
    "AndroidManifest.xml": 2494,
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
[unit] Test - LocalCostBundleTest > replaceItems
[unit] Gradle: Execution failed for task ':core-model:test'. - Execution failed for task ':core-model:test'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/core-model/build/reports/tests/test/index.html
[test] app.verst.core.model.cost.LocalCostBundleTest > replaceItems: java.lang.AssertionError: expected:<143> but was:<139>
```
