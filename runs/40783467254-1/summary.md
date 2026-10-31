# Run 166 (40783467254-1) — failure

sha `335a23b2dce6` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |

APK: 47.7 MB · ABIs ['arm64-v8a', 'x86_64'] · sha256 946afe1ff961292e…

Screenshots: 117

## Errors (first 60)
```
[unit] Test - NominatimClientTest > oneRequestWithTheUserAgentAndTheRussianParameters
[unit] Gradle: Execution failed for task ':app:testDebugUnitTest'. - Execution failed for task ':app:testDebugUnitTest'.
> There were failing tests. See the report at: file:///home/runner/work/Verst/Verst/android/app/build/reports/tests/testDebugUnitTest/index.html
[test] app.verst.data.net.NominatimClientTest > oneRequestWithTheUserAgentAndTheRussianParameters: org.junit.ComparisonFailure: expected:<[5]> but was:<[10]>
```
