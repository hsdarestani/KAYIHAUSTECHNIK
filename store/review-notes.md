# A+Bau — Review Notes / App Access

## Review account
A+Bau requires authentication and does not offer public self-registration in the store build. Reviewers must use the dedicated isolated Store review account.

The single source of truth for that account is the protected deployment secrets:
- `KAYI_REVIEW_USERNAME`
- `KAYI_REVIEW_PASSWORD`
- optional `KAYI_REVIEW_EMAIL`

The username/password entered in Google Play Console App Access and App Store Connect Review Information must be exactly the same values. Do not rotate this password while a review is pending. Never commit or paste the password into source control or public store metadata.

Workflow `Provision A+Bau Store Review Credentials` synchronizes the fixed credential to production and Publisher. It does not generate or rotate a password. The Google build in `Signed store release` is blocked unless the same protected username/password authenticates successfully against production.

## Apple App Review Notes
A+Bau is a business application for professional construction and building-services companies. The app requires a company-provided account; there is no public self-registration and no in-app purchase.

Review account: use the username/password supplied in the protected App Review Information fields. The account belongs only to an isolated demo organization and contains sample customers, projects, appointments and financial documents.

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
Choose **All or some functionality is restricted** and provide the dedicated A+Bau review username/password in Play Console App Access.

Instructions:
1. Launch A+Bau.
2. Enter the supplied review username and password.
3. No OTP, paid subscription, external hardware, VPN, IP allow-listing or additional approval is required for the review demo account.
4. The account belongs to a demo tenant and can be used to inspect customers, projects, appointments, documentation, 3D room planning, quotes and invoices.
5. Optional AI actions have a separate privacy-consent flow. AI consent is not required to access the rest of the app.

If ARCore room scanning is unsupported on the review device, use the photo/manual room workflow instead; this is expected device-capability behavior, not an account restriction.

## Mandatory pre-submission gate
Before any Google Play submission:
1. Run `Provision A+Bau Store Review Credentials` with `SYNC_STABLE_REVIEW_CREDENTIALS` when production/Publisher need synchronization.
2. Enter the exact same protected username/password in Google Play Console → App content → App access.
3. Run `Signed store release`. The Google AAB job must not proceed unless production authentication succeeds.
4. Test the exact candidate artifact through Internal testing / Pre-launch report before promotion.
5. Do not change the review password until Google has completed review.
