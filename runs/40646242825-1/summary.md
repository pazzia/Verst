# Run 157 (40646242825-1) — failure

sha `08de87c5694a` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |

APK: 47.69 MB · ABIs ['arm64-v8a', 'x86_64'] · sha256 77195521a204fb23…

Screenshots: 117

## Errors (first 60)
```
[unit] Test - LocalCostBundleTest > replaceItems
[unit] Gradle: Execution failed for task ':core-model:test'. - Execution failed for task ':core-model:test'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/core-model/build/reports/tests/test/index.html
[test] app.verst.core.model.cost.LocalCostBundleTest > replaceItems: java.lang.AssertionError: expected:<143> but was:<139>
```
