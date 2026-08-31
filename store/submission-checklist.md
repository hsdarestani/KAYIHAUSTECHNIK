# A+Bau — Final Submission Checklist

## Release identity
- App name: `A+Bau`
- Bundle/Application ID: `de.kayihaustechnik.app`
- Increase the store build number for every new upload.
- Android target/compile SDK: 36
- Android min SDK: 24
- iOS minimum deployment target: 16.0
- Apple build toolchain: Xcode 26+ / iOS 26 SDK

## Repository gates — must all be green
- CI
- Room editor CI
- Native scanner CI
- Store release readiness
- Store assets
- Production reviewer authentication gate
- Android `lintRelease`
- Android AAB + release APK
- Android merged manifest permission audit
- Android 16 KB ZIP and ELF LOAD alignment
- iOS Release `iphoneos` archive
- iOS app-level `PrivacyInfo.xcprivacy` present in archived `.app`
- Camera/Microphone purpose strings present
- Production browser smoke after merge: Datenschutz, Support and account deletion public without login

## Store reviewer credential — critical
There is exactly one stable Store reviewer credential, supplied through protected secrets:
- `KAYI_REVIEW_USERNAME`
- `KAYI_REVIEW_PASSWORD`
- optional `KAYI_REVIEW_EMAIL`

Rules:
- Never generate a new random review password during a release.
- Never rotate the password while Google Play or Apple review is pending.
- Production, Publisher, Google Play Console App Access and App Store Connect Review Information must use the same username/password.
- Run `Provision A+Bau Store Review Credentials` with confirmation `SYNC_STABLE_REVIEW_CREDENTIALS` when synchronization is needed.
- `Signed store release` must stop before Google AAB generation if the protected reviewer credential cannot authenticate against production.
- Do not place the password in Git, store descriptions, release notes, screenshots, issues or chat transcripts.

## Google Play Console
### App setup
- Select app: A+Bau
- Package name: `de.kayihaustechnik.app`
- App type: App
- Category: Business
- Primary language: German (Germany)

### App content
- Privacy policy URL: `https://kayi.smarbiz.sbs/datenschutz/`
- Account deletion URL: `https://kayi.smarbiz.sbs/konto-loeschen/`
- App access: choose **All or some functionality is restricted**.
- Enter the exact values of `KAYI_REVIEW_USERNAME` and `KAYI_REVIEW_PASSWORD` in the protected App Access fields.
- Paste the non-secret instructions from `store/review-notes.md`.
- Ads: No.
- Data Safety: use `store/privacy-declarations.md`.
- Target audience: professional/business users; not designed for children.
- News app: No.
- Government app: No, unless legal ownership changes.
- Financial features: A+Bau creates business documents/payment records but is not a banking, lending, investment or cryptocurrency service.

### Store listing
- All visible branding must say `A+Bau`; do not reuse legacy `KAYI Haustechnik` store text or screenshots.
- Copy current German text from `store/metadata-de.md` only after confirming it is A+Bau-branded.
- Upload the current Google Play icon and feature graphic.
- Use screenshots from the actual current A+Bau build.
- Do not add ranking, price, discount or misleading comparison claims.

### Release
1. Synchronize the stable reviewer account if necessary.
2. Manually verify Google Play Console App Access contains the exact same protected credential.
3. Run `Signed store release` with a new build number.
4. The `review-credentials-gate` must pass before the Google AAB can be built.
5. Upload the generated signed `.aab` to Internal testing first.
6. Run Pre-launch report/device checks and fix crashes, ANRs, freezes, loading errors or policy warnings.
7. Test login with the same reviewer account on the exact candidate build.
8. Promote the exact tested artifact rather than rebuilding it manually.
9. Do not rotate reviewer credentials until review is complete.

## App Store Connect
### App record
- Name: A+Bau
- Bundle ID: `de.kayihaustechnik.app`
- Primary language: German
- Category: Business; Productivity may be secondary.
- Privacy Policy URL: `https://kayi.smarbiz.sbs/datenschutz/`
- Privacy Choices URL: `https://kayi.smarbiz.sbs/konto-loeschen/`
- Support URL: `https://kayi.smarbiz.sbs/support/`

### Review information
- Supply the same stable dedicated reviewer username/password in App Store Connect protected review fields.
- Paste Apple review notes from `store/review-notes.md`.
- Review account must work without OTP, VPN, IP allow-listing or a temporary-password reset.
- Do not rotate it during review.

### Compliance and testing
- Fill App Privacy from `store/privacy-declarations.md`.
- Confirm export compliance consistently with the signed binary.
- Complete age rating accurately; do not choose Kids category.
- Submit the exact internally tested build.
- Test camera, gallery, microphone, login, project/appointment, RoomPlan fallback, AI consent/revoke, Privacy/Support/Löschung on a real device before review.

## Protected signing secrets
### Google Play
- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

### Apple
- `APPLE_CERTIFICATE_P12_BASE64`
- `APPLE_CERTIFICATE_PASSWORD`
- `APPLE_PROVISIONING_PROFILE_BASE64`
- `APPLE_TEAM_ID`
