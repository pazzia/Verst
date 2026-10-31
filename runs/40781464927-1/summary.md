# Run 165 (40781464927-1) — failure

sha `c5b1d1ea8363` · refs/heads/ccr-013d3489-181fz2 · workflow_dispatch

| job | result |
| --- | --- |
| planner | success |
| build | failure |
| e2e | skipped |
| release | skipped |


Screenshots: 0

## Errors (first 60)
```
[assemble] Kotlin android/app/src/main/kotlin/app/verst/platform/Platform.kt:65:19 Cannot infer type for this parameter. Specify it explicitly.
[assemble] Kotlin android/app/src/main/kotlin/app/verst/platform/Platform.kt:65:19 Not enough information to infer type argument for 'T'.
[assemble] Kotlin android/app/src/main/kotlin/app/verst/platform/Platform.kt:66:32 Unresolved reference 'channelFlow'.
[assemble] Kotlin android/app/src/main/kotlin/app/verst/platform/Platform.kt:67:67 Unresolved reference 'send'.
[assemble] Kotlin android/app/src/main/kotlin/app/verst/platform/Platform.kt:68:15 Cannot infer type for this parameter. Specify it explicitly.
[assemble] Kotlin android/app/src/main/kotlin/app/verst/platform/Platform.kt:68:15 Not enough information to infer type argument for 'T'.
[assemble] Gradle: Execution failed for task ':app:compileDemoKotlin'. - Execution failed for task ':app:compileDemoKotlin'.
> A failure occurred while executing org.jetbrains.kotlin.compilerRunner.GradleCompilerRunnerWithWorkers$GradleKotlinCompilerWorkAction
   > Compilation error. See log for more details
```
