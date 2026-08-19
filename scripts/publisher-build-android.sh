#!/usr/bin/env bash
set -euo pipefail

VERSION="${APP_VERSION_NAME:-2.2.1}"
BUILD="${APP_BUILD_NUMBER:-22002}"

bash scripts/unpack-source.sh
python3 -m pip install --disable-pip-version-check Pillow
python3 scripts/prepare_native_store_shell.py

pushd native >/dev/null
npm install --no-audit --no-fund
npm run build

# Store builds must never ship the raw ES-module source. A bare @capacitor/core
# import cannot be resolved by the Android WebView and leaves only the static splash.
if grep -RInE "from[[:space:]]+['\"]@capacitor/core['\"]" www; then
  echo "ERROR: native web bundle still contains an unresolved @capacitor/core import" >&2
  exit 1
fi
if grep -RInE "KAYI Haustechnik|Natives Baustellen-Aufmaß" www; then
  echo "ERROR: legacy KAYI splash/branding remains in the Android web bundle" >&2
  exit 1
fi
grep -RIn "A+Bau" www >/dev/null

rm -rf android
npx cap add android
npx cap sync android
popd >/dev/null

export KAYI_APP_VERSION="$VERSION"
export KAYI_BUILD_NUMBER="$BUILD"
export KAYI_ANDROID_KEYSTORE="${ANDROID_KEYSTORE_PATH:?Publisher Android keystore path missing}"
export KAYI_ANDROID_KEYSTORE_PASSWORD="${ANDROID_KEYSTORE_PASSWORD:?Publisher Android store password missing}"
export KAYI_ANDROID_KEY_ALIAS="${ANDROID_KEY_ALIAS:?Publisher Android key alias missing}"
export KAYI_ANDROID_KEY_PASSWORD="${ANDROID_KEY_PASSWORD:?Publisher Android key password missing}"

python3 scripts/configure_native_release.py android
python3 scripts/generate_store_brand_assets.py --native

# Verify what is actually embedded in the generated Android project, not only the source webDir.
grep -RIn '"appName": "A+Bau"' native/android/app/src/main/assets/capacitor.config.json >/dev/null
if grep -RInE "from[[:space:]]+['\"]@capacitor/core['\"]|KAYI Haustechnik|Natives Baustellen-Aufmaß" native/android/app/src/main/assets/public; then
  echo "ERROR: generated Android assets are not release-safe" >&2
  exit 1
fi

pushd native/android >/dev/null
./gradlew lintRelease bundleRelease --stacktrace
popd >/dev/null

test -f "$(find native/android/app/build/outputs/bundle/release -name '*.aab' | head -n 1)"
echo "A+Bau Android Publisher build ready: ${VERSION} (${BUILD}); bundled startup verified"
