# CI run 41539154478 · build · 3302307c47 · refs/heads/ccr-013d3489-181fz2

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
  "bytes": 49849702,
  "mb": 49.85,
  "sha256": "3bcdf3b5d5c0e2b16ae28a11cd249f4d37181f5865fd1bf4b1953c31e55eb0fa",
  "abis": [
    "arm64-v8a",
    "x86_64"
  ],
  "largestEntries": {
    "lib": 24805600,
    "assets": 14848727,
    "classes.dex": 4252451,
    "classes2.dex": 4101755,
    "resources.arsc": 799872,
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
[unit] Test - V2ContractsTest > cardsHandoffAndCity
[unit] Gradle: Execution failed for task ':core-model:test'. - Execution failed for task ':core-model:test'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/core-model/build/reports/tests/test/index.html
[test] app.verst.core.model.V2ContractsTest > cardsHandoffAndCity: java.lang.AssertionError
```
