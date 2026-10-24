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
  ARGS+=(-e package app.verst.e2e)
fi
timeout 1500 adb shell am instrument "${ARGS[@]}" "$RUNNER" 2>&1 | tee "$OUT/instrument.txt"
STATUS=${PIPESTATUS[0]}

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
exit 0
