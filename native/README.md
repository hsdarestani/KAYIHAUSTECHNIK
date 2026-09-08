# KAYI Native Room Scanner

Capacitor 8 shell for the KAYI field app.

- iOS: Apple RoomPlan with LiDAR, semantic walls/doors/windows/openings and USDZ export.
- Android: guided ARCore Depth/plane capture with four floor corners plus ceiling point and OBJ export.
- Every native result is uploaded to `/api/native-scans/` and remains `review` until a user confirms it in KAYI.
- Photo-based AI measurement remains the fallback on unsupported devices.

## Local build

```bash
npm install
npm run build
npx cap add ios
npx cap add android
npx cap sync
```

Add `NSCameraUsageDescription` to the iOS app Info.plist. Android permissions and ARCore metadata are merged from the plugin manifest.

Physical LiDAR and ARCore device validation is required before store distribution. CI builds unsigned simulator/debug artifacts only.
