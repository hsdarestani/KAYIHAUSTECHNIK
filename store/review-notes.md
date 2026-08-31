# A+Bau — Review Notes / App Access

## Review account
A+Bau requires authentication and does not offer public self-registration in the store build. Reviewers must use the dedicated isolated Store review account.

The Store reviewer identity is fixed:
- Username: `demo`
- Password source: protected secret `KAYI_REVIEW_PASSWORD`
- optional review email: `KAYI_REVIEW_EMAIL`

The password entered in Google Play Console App Access and App Store Connect Review Information must be exactly the same protected value. Do not rotate this password while a review is pending. Never commit or paste the password into source control or public store metadata.

Workflow `Provision A+Bau Store Review Credentials` synchronizes the fixed `demo` account password to production and Publisher. It does not generate or rotate a password. The Google build in `Signed store release` is blocked unless `demo` with the protected password authenticates successfully against production.

## Apple App Review Notes
A+Bau is a business application for professional construction and building-services companies. The app requires a company-provided account; there is no public self-registration and no in-app purchase.

Review account: username `demo`; use the password supplied in the protected App Review Information password field. The review account belongs only to an isolated demo organization and contains sample customers, projects, appointments and financial documents.

Recommended review path:
1. Sign in.
2. Open a customer and project.
3. Open an appointment to see mobile time tracking and job documentation.
4. Open the project room-planning area to inspect the editable 3D workflow.
5. In Settings → Datenschutz & Konto, privacy information and account deletion are available.
6. Optional AI functions require a separate explicit consent in Settings before selected text or photos can be sent to OpenAI. The consent can be revoked at any time.

Camera access is requested only after the user starts a photo or room-scan action. Microphone access is requested only when the user actively starts a voice note/report. The app does not require broad photo-library access.

iOS RoomPlan/native room measurement is device-dependent. If the review device does not support the native scan capability, the photo/manual 3D workflow remains available. Scan results are reviewable before being adopted into project documentation.

Account deletion:
https://kayi.smarbiz.sbs/konto-loeschen/

Privacy policy:
https://kayi.smarbiz.sbs/datenschutz/

Support:
https://kayi.smarbiz.sbs/support/

A+Bau uses standard platform/TLS encryption and declares ITSAppUsesNonExemptEncryption = false; it does not implement non-exempt proprietary cryptography.

## Google Play — App Access instructions
Choose **All or some functionality is restricted** and provide username `demo` plus the exact `KAYI_REVIEW_PASSWORD` value in Play Console App Access.

Instructions:
1. Launch A+Bau.
2. Enter username `demo` and the supplied review password.
3. No OTP, paid subscription, external hardware, VPN, IP allow-listing or additional approval is required for the review demo account.
4. The account belongs to a demo tenant and can be used to inspect customers, projects, appointments, documentation, 3D room planning, quotes and invoices.
5. Optional AI actions have a separate privacy-consent flow. AI consent is not required to access the rest of the app.

If ARCore room scanning is unsupported on the review device, use the photo/manual room workflow instead; this is expected device-capability behavior, not an account restriction.

## Mandatory pre-submission gate
Before any Google Play submission:
1. Set/update the protected `KAYI_REVIEW_PASSWORD` in the GitHub `production` environment. Do not put it in Git or chat.
2. Run `Provision A+Bau Store Review Credentials` with `SYNC_STABLE_REVIEW_CREDENTIALS` to synchronize `demo` on production and Publisher.
3. Enter username `demo` and the exact same password in Google Play Console → App content → App access.
4. Run `A+Bau review credential readiness`; it must pass.
5. Run `Signed store release`. The Google AAB job must not proceed unless production authentication succeeds.
6. Test the exact candidate artifact through Internal testing / Pre-launch report before promotion.
7. Do not change the review password until Google has completed review.
