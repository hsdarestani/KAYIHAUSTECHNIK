# App Store / Google Play compliance baseline

- Bundle identifier: `sbs.smarbiz.kayi`
- Privacy URL: `https://kayi.smarbiz.sbs/privacy/`
- Terms URL: `https://kayi.smarbiz.sbs/terms/`
- In-app account deletion request: Settings and `POST /api/mobile/account-deletion/`
- Authentication: server-issued token over HTTPS; secrets never ship in the app.
- Camera/files: only after user action for project documentation.
- Location: only after user consent while starting time tracking; no background tracking by default.
- AI: server-side OpenAI key; AI outputs are drafts requiring human approval.
- WebView is supplemented by camera, files, geolocation, offline queue and push integration to avoid a thin-wrapper product.
- Legal retention: deletion requests may preserve invoices and audit data required by German law.
