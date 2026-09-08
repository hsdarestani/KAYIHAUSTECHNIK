# KAYI Mobile Wrapper

Capacitor shell for Android and iOS. The production app uses the authenticated API and hosted UI while native plugins provide camera, file, geolocation, network and push capabilities.

Before store submission:
1. Generate native projects with `npm install && npx cap add android && npx cap add ios`.
2. Add Android signing and Apple provisioning in private CI secrets.
3. Supply 1024px App Store and 512px Play Store icons, screenshots, support URL and privacy URL.
4. Configure Firebase/APNs for push notifications.
5. Keep location permission usage limited to an explicit active time-entry action.
6. Complete Apple privacy nutrition labels and Google Play Data Safety from `docs/store-compliance.md`.
