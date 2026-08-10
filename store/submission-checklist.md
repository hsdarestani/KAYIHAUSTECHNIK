# KAYI Haustechnik — Final Submission Checklist

## Release identity
- App name: `KAYI Haustechnik`
- Bundle/Application ID: `de.kayihaustechnik.app`
- Release version: `2.2.0`
- Initial store build number: `22001` (increase for every new upload)
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
- Android `lintRelease`
- Android AAB + release APK
- Android merged manifest permission audit
- Android 16 KB ZIP and ELF LOAD alignment
- iOS Release `iphoneos` archive
- iOS app-level `PrivacyInfo.xcprivacy` present in archived `.app`
- Camera/Microphone purpose strings present
- Production browser smoke after merge: Datenschutz, Support and account deletion public without login

## Google Play Console
### App setup
- Create/select app: KAYI Haustechnik
- Package name: `de.kayihaustechnik.app`
- App type: App
- Free/Paid: choose according to commercial distribution model; KAYI contains no Play Billing or in-app purchases.
- Category: Business (recommended)
- Primary language: German (Germany)

### Developer/account requirements
- Complete Play developer identity verification.
- Ensure `de.kayihaustechnik.app` is registered/associated with the verified developer account.
- Organization account is recommended for a commercial B2B product; keep legal developer name/contact data current.

### App content
- Privacy policy URL: `https://kayi.smarbiz.sbs/datenschutz/`
- Account deletion URL: `https://kayi.smarbiz.sbs/konto-loeschen/`
- App access: restricted; paste `store/review-notes.md` instructions and enter the dedicated review credentials in the protected Play Console fields.
- Ads: No.
- Data Safety: use `store/privacy-declarations.md`.
- Content rating: complete IARC questionnaire accurately. KAYI has no violence, sexual content, drugs, gambling or ads; do not invent a rating manually—submit the questionnaire and use the calculated regional ratings.
- Target audience: professional/business users; do not mark the app as designed for children.
- News app: No.
- Government app: No, unless legal ownership changes.
- Financial features declaration: KAYI creates business documents/payment records but is not a banking, lending, investment or cryptocurrency service.

### Store listing
- Copy German text from `store/metadata-de.md`.
- Upload `google-play-icon-512.png`.
- Upload `google-play-feature-graphic-1024x500.png`.
- Upload at least the four generated `google-phone` screenshots.
- Do not add ranking, price, discount or misleading comparison claims to graphics/text.

### Release
- Enable Play App Signing.
- Use an upload key whose protected secrets are configured for `Signed store release`.
- Run workflow `Signed store release` with a new build number.
- Upload the generated signed `.aab` to Internal testing first.
- Run Pre-launch report/device checks; fix crashes/ANRs/policy warnings before Production.
- Promote the exact tested artifact through Closed/Open/Production as appropriate rather than rebuilding it manually.

## App Store Connect
### App record
- Name: KAYI Haustechnik
- Bundle ID: `de.kayihaustechnik.app`
- SKU: a stable internal value such as `KAYI-HAUSTECHNIK-IOS`
- Primary language: German
- Category: Business (recommended); Productivity can be secondary.
- Privacy Policy URL: `https://kayi.smarbiz.sbs/datenschutz/`
- Privacy Choices URL: `https://kayi.smarbiz.sbs/konto-loeschen/`
- Support URL: `https://kayi.smarbiz.sbs/support/`

### Compliance
- App Privacy: fill from `store/privacy-declarations.md`.
- Age rating: answer questionnaire accurately. KAYI has no objectionable entertainment content; do not choose Kids category. Let App Store Connect calculate the rating.
- Content Rights: confirm that the company/user has rights to business documents/photos uploaded into KAYI and any third-party content distributed through the app.
- Export compliance: binary declares `ITSAppUsesNonExemptEncryption = false`; confirm the declaration in App Store Connect consistently.
- Digital Services Act: declare the account/app's actual trader status. For commercial distribution in the EU, verify and publish the required trader business address, phone and email in App Store Connect.
- In-App Purchases: none.

### Review information
- Supply the dedicated review username/password only in App Store Connect's protected review fields.
- Paste Apple review notes from `store/review-notes.md`.
- Review account must work without OTP, VPN, IP allow-listing or a temporary-password reset.

### Screenshots and metadata
- Copy German metadata from `store/metadata-de.md`.
- Upload generated 1290×2796 `apple-6.9` screenshots; one to ten are accepted and four are prepared.
- Upload/use the generated 1024×1024 App Store icon through the signed app's AppIcon catalog; no alpha.

### Build/TestFlight/Review
- Configure protected Apple signing secrets.
- Run `Signed store release` with a new build number.
- Upload the generated IPA via Transporter/Xcode/App Store Connect tooling under the same Apple Developer team.
- Process build, complete App Privacy/export/age-rating questions, add review account, then send first to TestFlight internal testing.
- Test camera, gallery, microphone, login, project/appointment, RoomPlan fallback, AI consent/revoke, Privacy/Support/Löschung on a real iPhone.
- Submit the exact tested build to App Review.

## Protected repository/deployment secrets
### Google Play signing
- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

### Apple signing
- `APPLE_CERTIFICATE_P12_BASE64`
- `APPLE_CERTIFICATE_PASSWORD`
- `APPLE_PROVISIONING_PROFILE_BASE64`
- `APPLE_TEAM_ID`

### Store reviewer account
- `KAYI_REVIEW_USERNAME`
- `KAYI_REVIEW_PASSWORD`
- optional `KAYI_REVIEW_EMAIL`

No certificate, profile, keystore or reviewer password belongs in Git, app assets, store descriptions or chat transcripts.
