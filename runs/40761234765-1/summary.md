# Run 159 (40761234765-1) — failure

sha `382dad6bc581` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |


Screenshots: 0

## Errors (first 60)
```
[assemble] Gradle: Execution failed for task ':app:packageDemoAndroidTest'. - Execution failed for task ':app:packageDemoAndroidTest'.
> A failure occurred while executing com.android.build.gradle.tasks.PackageAndroidArtifact$IncrementalSplitterRunnable
   > com.android.ide.common.signing.KeytoolException: Failed to read key verst-demo from store "/home/runner/work/_temp/verst-demo.jks": null
```
