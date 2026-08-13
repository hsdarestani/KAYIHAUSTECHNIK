#!/usr/bin/env bash
set -euo pipefail

VERSION="${APP_VERSION_NAME:-2.2.0}"
BUILD="${APP_BUILD_NUMBER:-22001}"

bash scripts/unpack-source.sh
python3 -m pip install --disable-pip-version-check Pillow

pushd native >/dev/null
npm install --no-audit --no-fund
rm -rf ios
npx cap add ios
npx cap sync ios
popd >/dev/null

export KAYI_APP_VERSION="$VERSION"
export KAYI_BUILD_NUMBER="$BUILD"
python3 scripts/configure_native_release.py ios
python3 scripts/generate_store_brand_assets.py --native

ARCHIVE="${RUNNER_TEMP:-/tmp}/A-Bau.xcarchive"
EXPORT_DIR="${RUNNER_TEMP:-/tmp}/a-bau-export"
EXPORT_OPTIONS="${RUNNER_TEMP:-/tmp}/A-Bau-ExportOptions.plist"
mkdir -p artifacts "$EXPORT_DIR"

cat > "$EXPORT_OPTIONS" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>method</key><string>app-store-connect</string>
  <key>destination</key><string>export</string>
  <key>signingStyle</key><string>manual</string>
  <key>teamID</key><string>${IOS_TEAM_ID:?Publisher iOS team ID missing}</string>
  <key>manageAppVersionAndBuildNumber</key><false/>
  <key>provisioningProfiles</key><dict>
    <key>de.kayihaustechnik.app</key><string>${IOS_PROVISIONING_PROFILE_SPECIFIER:?Publisher provisioning profile missing}</string>
  </dict>
</dict></plist>
EOF

pushd native >/dev/null
xcodebuild \
  -project ios/App/App.xcodeproj \
  -scheme App \
  -configuration Release \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE" \
  DEVELOPMENT_TEAM="$IOS_TEAM_ID" \
  CODE_SIGN_STYLE=Manual \
  CODE_SIGN_IDENTITY="${IOS_CODE_SIGN_IDENTITY:-Apple Distribution}" \
  PROVISIONING_PROFILE_SPECIFIER="$IOS_PROVISIONING_PROFILE_SPECIFIER" \
  archive

xcodebuild -exportArchive \
  -archivePath "$ARCHIVE" \
  -exportPath "$EXPORT_DIR" \
  -exportOptionsPlist "$EXPORT_OPTIONS"
popd >/dev/null

IPA="$(find "$EXPORT_DIR" -maxdepth 1 -name '*.ipa' | head -n 1)"
test -n "$IPA" && test -f "$IPA"
cp "$IPA" artifacts/a-bau.ipa

echo "A+Bau iOS Publisher build ready: ${VERSION} (${BUILD})"
