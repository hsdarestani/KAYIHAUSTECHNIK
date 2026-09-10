# A+Bau Native Full App

Capacitor 8 application for office/admin and field employees. Customers, projects, appointments, work reports, tasks, time tracking, quotes, invoices and expenses use the same role-scoped backend; room scanning is one project tool.

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

Pull-request CI builds Android and iOS release-validation artifacts. The manual `Signed store release` workflow produces the signed Play AAB and App Store IPA after protected signing secrets are configured. Physical LiDAR and ARCore device validation is required before store distribution.
