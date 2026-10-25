#!/usr/bin/env bash
# Emulator journey for the mock APK (docs/architecture-android-mvp.md §11, §12).
# Called once by reactivecircus/android-emulator-runner (its `script:` runs each line in a separate
# shell, so everything lives here). Never exits early: it always pulls screenshots and logcat, then
# exits with the instrumentation result.
#
#   run_e2e.sh <app.apk> <androidTest.apk> <out-dir>
#
# Env: E2E_CLASSES (comma-separated test classes, default: all classes in package app.verst.e2e),
#      APP_ID (default app.verst.demo — the non-debuggable `demo` build type, so no run-as).
# Tests write their files to the app-specific external dir: /sdcard/Android/data/<APP_ID>/files/e2e.
set -uo pipefail

APP_APK=${1:?app apk}
TEST_APK=${2:?test apk}
OUT=${3:?out dir}
APP_ID=${APP_ID:-app.verst.demo}
TEST_ID="$APP_ID.test"
RUNNER="$TEST_ID/androidx.test.runner.AndroidJUnitRunner"
mkdir -p "$OUT/screens"

adb wait-for-device
adb shell 'while [ "$(getprop sys.boot_completed)" != "1" ]; do sleep 1; done'
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0
# Reference frame of the design (390 × 844 dp at density 3.0 = 1170 × 2532 px).
adb shell wm size 1170x2532
adb shell wm density 480
adb shell getprop ro.build.version.sdk > "$OUT/device-sdk.txt"
adb shell getprop ro.product.cpu.abi > "$OUT/device-abi.txt"

adb uninstall "$APP_ID" >/dev/null 2>&1 || true
adb uninstall "$TEST_ID" >/dev/null 2>&1 || true
adb install -r -t "$APP_APK" 2>&1 | tee "$OUT/install-app.txt"
adb install -r -t "$TEST_APK" 2>&1 | tee "$OUT/install-test.txt"
adb logcat -G 16M 2>/dev/null || true  # S3-R4: the 19-test main run outgrew the default ring buffer
adb logcat -c

# Cold start of the launcher activity, measured by the system (TotalTime = first frame).
adb shell am start -W -n "$APP_ID/app.verst.MainActivity" 2>&1 | tee "$OUT/am-start.txt"
sleep 8
adb exec-out screencap -p > "$OUT/screens/00-cold-start.png" || true
adb shell am force-stop "$APP_ID"

ARGS=(-w -r)
if [ -n "${E2E_CLASSES:-}" ]; then
  ARGS+=(-e class "$E2E_CLASSES")
else
  # The process-death journey (app.verst.e2e.restore) needs a kill between its phases: run below.
  ARGS+=(-e package app.verst.e2e -e notPackage app.verst.e2e.restore,app.verst.e2e.gps)
fi
timeout 1500 adb shell am instrument "${ARGS[@]}" "$RUNNER" 2>&1 | tee "$OUT/instrument.txt"
STATUS=${PIPESTATUS[0]}

# Release review P1-2 / M§11 step 8: plan a trip and stay on Road ahead, HOME, kill the process, relaunch:
# Road ahead must show the same trip. Each `am instrument` starts a fresh app process.
if [ -z "${E2E_CLASSES:-}" ] && [ "$STATUS" -eq 0 ]; then
  R="app.verst.e2e.restore.ProcessDeathTest"
  timeout 300 adb shell am instrument -w -r -e class "$R#phase1PlanAndLeave" "$RUNNER" 2>&1 | tee -a "$OUT/instrument.txt"
  S1=${PIPESTATUS[0]}
  adb shell input keyevent KEYCODE_HOME
  sleep 2
  adb shell am force-stop "$APP_ID"
  adb shell am kill "$APP_ID" || true
  sleep 2
  echo "process-death: $(adb shell pidof "$APP_ID" || echo 'no process') after force-stop" | tee -a "$OUT/instrument.txt"
  timeout 300 adb shell am instrument -w -r -e class "$R#phase2RelaunchRestoresRoadAhead" "$RUNNER" 2>&1 | tee -a "$OUT/instrument.txt"
  S2=${PIPESTATUS[0]}
  [ "$S1" -ne 0 ] && STATUS=$S1
  [ "$S2" -ne 0 ] && STATUS=$S2

  # S3-R1 GPS on the real location stack, last: grant the permission, location on, feed `geo fix` (Тула).
  adb shell cmd location set-location-enabled true || true
  adb shell pm grant "$APP_ID" android.permission.ACCESS_FINE_LOCATION || true
  adb shell pm grant "$APP_ID" android.permission.ACCESS_COARSE_LOCATION || true
  ( for i in $(seq 1 60); do adb emu geo fix 37.6177 54.1931 >/dev/null 2>&1; sleep 2; done ) &
  GEO=$!
  timeout 300 adb shell am instrument -w -r -e class app.verst.e2e.gps.RealGpsTest "$RUNNER" 2>&1 | tee -a "$OUT/instrument.txt"
  S3=${PIPESTATUS[0]}
  kill "$GEO" 2>/dev/null || true
  [ "$S3" -ne 0 ] && STATUS=$S3
fi

# Files written by the tests (screens/*.png, timings.json, parity.json) in the app-specific external dir.
adb pull "/sdcard/Android/data/$APP_ID/files/e2e/." "$OUT/" >/dev/null 2>&1 || echo "no e2e files pulled" | tee "$OUT/pull-error.txt"
adb logcat -d -v threadtime > "$OUT/logcat-full.txt" 2>/dev/null || true
gzip -f "$OUT/logcat-full.txt" || true
gunzip -c "$OUT/logcat-full.txt.gz" > "$OUT/logcat.txt" 2>/dev/null || true

if [ "$STATUS" -ne 0 ]; then
  echo "am instrument exited with $STATUS"
  exit "$STATUS"
fi
if grep -qE "FAILURES!!!|INSTRUMENTATION_FAILED|Process crashed|INSTRUMENTATION_CODE: 0" "$OUT/instrument.txt"; then
  echo "instrumentation reported failures"
  exit 1
fi
if ! grep -q "^OK (" "$OUT/instrument.txt"; then
  echo "instrumentation did not report OK"
  exit 1
fi
if [ -z "${E2E_CLASSES:-}" ] && [ "$(grep -c "^OK (" "$OUT/instrument.txt")" -ne 4 ]; then
  echo "expected 4 OK runs (main + process-death phases 1 and 2 + real GPS)"
  exit 1
fi
exit 0
