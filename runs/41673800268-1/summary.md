# Run 201 (41673800268-1) — failure

sha `1b76be0baad7` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |

APK: 49.85 MB · ABIs ['arm64-v8a', 'x86_64'] · sha256 deec2e050d39bd1e…

Screenshots: 140

## Errors (first 60)
```
[unit] Test - AnalyticsJourneyTest > searchInstrumentsWaybillHandoffReportShareAndDrivenEvents
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.analytics.AnalyticsJourneyTest > searchInstrumentsWaybillHandoffReportShareAndDrivenEvents: java.lang.AssertionError: expected:<{km_bucket=500-800, days=2, dog=true, children=1, mood=fun, ready_route_id=none}> but was:<{km_bucket=unknown, dog=true, children=1, mood=fun, ready_route_id=none}>
```
