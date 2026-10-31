# CI run 40761234765 · build · 382dad6bc5 · refs/heads/ccr-013d3489-181fz2

## gradle.assemble
```json
{
  "buildFailed": true,
  "errors": 1,
  "whatWentWrong": [
    "Execution failed for task ':app:packageDemoAndroidTest'.\n> A failure occurred while executing com.android.build.gradle.tasks.PackageAndroidArtifact$IncrementalSplitterRunnable\n   > com.android.ide.common.signing.KeytoolException: Failed to read key verst-demo from store \"/home/runner/work/_temp/verst-demo.jks\": null"
  ]
}
```
## steps.build
```json
{
  "assemble": "failure",
  "unit": "skipped",
  "lint": "skipped",
  "licences": "skipped",
  "apk": "skipped"
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
[assemble] Gradle: Execution failed for task ':app:packageDemoAndroidTest'. - Execution failed for task ':app:packageDemoAndroidTest'.
> A failure occurred while executing com.android.build.gradle.tasks.PackageAndroidArtifact$IncrementalSplitterRunnable
   > com.android.ide.common.signing.KeytoolException: Failed to read key verst-demo from store "/home/runner/work/_temp/verst-demo.jks": null
```
