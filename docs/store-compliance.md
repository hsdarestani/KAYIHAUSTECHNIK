# App Store / Google Play compliance baseline

- Bundle identifier (iOS and Android): `de.kayihaustechnik.app`
- Privacy URL: `https://kayi.smarbiz.sbs/privacy/`
- Terms URL: `https://kayi.smarbiz.sbs/terms/`
- In-app account deletion request: Settings and `POST /api/mobile/account-deletion/`
- Authentication: server-issued token over HTTPS; secrets never ship in the app.
- Camera/files: only after user action for project documentation.
- Location: only after user consent while starting time tracking; no background tracking by default.
- AI: server-side OpenAI key; AI outputs are drafts requiring human approval.
- The native shell includes RoomPlan/ARCore scanning, camera/files, connectivity-aware cached read access, scan upload queue, role-aware operational workflows and in-app appointment reminders. Financial writes are deliberately blocked offline to prevent duplicate documents.
- Legal retention: deletion requests may preserve invoices and audit data required by German law.
