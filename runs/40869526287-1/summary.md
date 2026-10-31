# Run 171 (40869526287-1) — failure

sha `261dfd1bab1f` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |

APK: 48.42 MB · ABIs ['arm64-v8a', 'x86_64'] · sha256 cb75113b58b6eb74…

Screenshots: 128

## Errors (first 60)
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
