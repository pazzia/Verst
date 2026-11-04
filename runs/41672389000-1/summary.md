# Run 200 (41672389000-1) — failure

sha `481ded2c27f2` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |

APK: 49.85 MB · ABIs ['arm64-v8a', 'x86_64'] · sha256 88d5307a1cfcb477…

Screenshots: 140

## Errors (first 60)
```
[unit] Test - AnalyticsJourneyTest > searchInstrumentsWaybillHandoffReportShareAndDrivenEvents
[unit] Test - VerstFlowTest > oneTripOneDistanceThenWaybillReplaceSaveReopen
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.analytics.AnalyticsJourneyTest > searchInstrumentsWaybillHandoffReportShareAndDrivenEvents: java.util.NoSuchElementException: Collection contains no element matching the predicate.
[test] app.verst.nav.VerstFlowTest > oneTripOneDistanceThenWaybillReplaceSaveReopen: java.lang.AssertionError: expected:<Road> but was:<Instruments>
```
