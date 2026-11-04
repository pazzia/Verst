# Run 198 (41546333192-1) — failure

sha `c6a8936ee0f0` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |

APK: 49.85 MB · ABIs ['arm64-v8a', 'x86_64'] · sha256 c34366e5d99c1fd6…

Screenshots: 140

## Errors (first 60)
```
[unit] Test - ScreensScreenshotTest > cardHotelArea
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.ScreensScreenshotTest > cardHotelArea: java.lang.AssertionError: Failed: assertExists.
Reason: Expected exactly '1' node but could not find any node that satisfies: (Text + InputText + EditableText contains 'Гостиница в демо-сборке вымышленная' (ignoreCase: false))
```
