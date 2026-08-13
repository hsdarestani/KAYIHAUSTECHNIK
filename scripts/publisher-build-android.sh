#!/usr/bin/env bash
set -euo pipefail

VERSION="${APP_VERSION_NAME:-2.2.0}"
BUILD="${APP_BUILD_NUMBER:-22001}"

bash scripts/unpack-source.sh
python3 -m pip install --disable-pip-version-check Pillow

pushd native >/dev/null
npm install --no-audit --no-fund
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

pushd native/android >/dev/null
./gradlew lintRelease bundleRelease --stacktrace
popd >/dev/null

test -f "$(find native/android/app/build/outputs/bundle/release -name '*.aab' | head -n 1)"
echo "A+Bau Android Publisher build ready: ${VERSION} (${BUILD})"
