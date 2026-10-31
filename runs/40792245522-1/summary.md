# Run 169 (40792245522-1) — failure

sha `2418d1e3cc47` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |

APK: 48.39 MB · ABIs ['arm64-v8a', 'x86_64'] · sha256 55f36d40508337ef…

Screenshots: 120

## Errors (first 60)
```
[unit] Test - V2ContractsTest > noDataPricesAndFoodStopsDecode
[unit] Test - ScreensScreenshotTest > cityNotEnoughNoData
[unit] Test - VerstFlowTest > notEnoughNoDataCarriesTheEnginesMessage
[unit] Gradle: Execution failed for task ':core-model:test'. - Execution failed for task ':core-model:test'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/core-model/build/reports/tests/test/index.html
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.ScreensScreenshotTest > cityNotEnoughNoData: java.lang.NullPointerException
[test] app.verst.nav.VerstFlowTest > notEnoughNoDataCarriesTheEnginesMessage: org.junit.ComparisonFailure: expected:<[no_data]> but was:<[few_places]>
[test] app.verst.core.model.V2ContractsTest > noDataPricesAndFoodStopsDecode: org.junit.ComparisonFailure: city_route-error-no-data.json expected:<[no_data]> but was:<[few_places]>
```
