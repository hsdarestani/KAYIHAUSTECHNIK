# Signed Apple and Google build runbook

The repository contains `.github/workflows/store-signed-release.yml`. It produces a signed Google Play AAB and an App Store IPA from the same version/build inputs.

## Required protected GitHub secrets

### Shared review gate

- `KAYI_REVIEW_PASSWORD`
- `HOST`
- `DEPLOY_USER`
- `SSH_KEY` or `PASS`

The production review account username is fixed to `demo`; the workflow verifies the exact password before either store artifact is created.

### Google Play signing

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

Encode the upload keystore as one-line base64. Keep Play App Signing enabled and retain the upload key outside GitHub as a protected backup.

### Apple App Store signing

- `APPLE_CERTIFICATE_P12_BASE64`
- `APPLE_CERTIFICATE_PASSWORD`
- `APPLE_PROVISIONING_PROFILE_BASE64`
- `APPLE_TEAM_ID`

The provisioning profile must target `de.kayihaustechnik.app` and use an Apple Distribution certificate.

## Build

Run **Signed store release** manually on `main` and supply:

- `app_version`: semantic public version, for example `2.2.0`
- `build_number`: a new monotonically increasing integer, for example `22001`

Download the retained artifacts:

- `A-Bau-Google-Play-<version>-<build>` (`.aab`)
- `A-Bau-App-Store-<version>-<build>` (`.ipa`)

Upload the AAB to a Play Console internal-testing track and the IPA to App Store Connect/TestFlight before production review. Physical-device validation of LiDAR and ARCore remains mandatory.
