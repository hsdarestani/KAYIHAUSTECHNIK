# KAYI Haustechnik — Review Notes / App Access

## Review account
KAYI requires authentication and does not offer public self-registration in the store build. Provide reviewers with a dedicated, isolated demo account created by:

`python manage.py ensure_store_reviewer`

Credentials are supplied only through deployment secrets:
- `KAYI_REVIEW_USERNAME`
- `KAYI_REVIEW_PASSWORD`
- optional `KAYI_REVIEW_EMAIL`

Never commit or paste production credentials into source control or store metadata files.

## Apple App Review Notes (paste into App Store Connect)
KAYI Haustechnik is a business application for professional Haustechnik/handcraft companies. The app requires a company-provided account; there is no public self-registration and no in-app purchase.

Review account: use the username/password supplied in the App Review Information fields. The review account belongs only to an isolated demo organization and contains sample customers, projects, appointments and financial documents.

Recommended review path:
1. Sign in.
2. Open a customer and project.
3. Open an appointment to see mobile time tracking and job documentation.
4. Open the project room-planning area to inspect the editable 3D workflow.
5. In Settings → Datenschutz & Konto, privacy information and account deletion are available.
6. Optional AI functions require a separate explicit consent in Settings before selected text or photos can be sent to OpenAI. The consent can be revoked at any time.

Camera access is requested only after the user starts a photo or room-scan action. Microphone access is requested only when the user actively starts a voice note/report. The app does not require broad photo-library access.

iOS RoomPlan/native room measurement is device-dependent. If the review device does not support the native scan capability, the photo/manual 3D workflow remains available. Scan results are reviewable before being adopted into project documentation.

Account deletion is available in-app and publicly at:
https://kayi.smarbiz.sbs/konto-loeschen/
Privacy policy:
https://kayi.smarbiz.sbs/datenschutz/
Support:
https://kayi.smarbiz.sbs/support/

KAYI uses standard platform/TLS encryption and declares ITSAppUsesNonExemptEncryption = false; it does not implement non-exempt proprietary cryptography.

## Google Play — App Access instructions
All or some functionality is restricted by authentication. Choose **All or some functionality is restricted** and provide the dedicated KAYI review username/password in Play Console App Access.

Instructions:
1. Launch KAYI Haustechnik.
2. Enter the supplied review username and password.
3. No OTP, paid subscription, external hardware or additional approval is required for the review demo account.
4. The account belongs to a demo tenant and can be used to inspect customers, projects, appointments, documentation, 3D room planning, quotes and invoices.
5. Optional AI actions first display/require the KAYI privacy consent state. Granting AI consent is not required to access the rest of the app.

If ARCore room scanning is unsupported on the review device, use the photo/manual room workflow instead; this is expected device-capability behavior, not an account restriction.

## Pre-submission operator checklist
Before submitting a build, verify the review account directly on the exact AAB/IPA candidate and confirm the credentials have not expired or been disabled. Do not enable 2FA, IP allow-listing or a temporary password-reset requirement for the store review account during review.
