# Run 202 (41675968539-1) — failure

sha `4b87e4fb2fce` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |

APK: 50.2 MB · ABIs ['arm64-v8a', 'x86_64'] · sha256 130b71a58fea8273…

Screenshots: 140

## Errors (first 60)
```
[unit] Test - VerstFlowTest > oneTripOneDistanceThenWaybillReplaceSaveReopen
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.nav.VerstFlowTest > oneTripOneDistanceThenWaybillReplaceSaveReopen: java.lang.AssertionError: expected:<TripFigures(km=542, days=2)> but was:<TripFigures(km=540, days=2)>
```
