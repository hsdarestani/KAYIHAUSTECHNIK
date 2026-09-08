from pathlib import Path
from django.test import SimpleTestCase


class NativeSourceContractTests(SimpleTestCase):
    def test_native_scanner_sources_and_human_review_contract_exist(self):
        root = Path(__file__).resolve().parents[1]
        required = [
            root / "native/package.json",
            root / "native/capacitor.config.ts",
            root / "native/www/app.js",
            root / "native/plugins/kayi-room-scanner/KayiRoomScanner.podspec",
            root / "native/plugins/kayi-room-scanner/ios/Sources/KayiRoomScannerPlugin/KayiRoomScannerPlugin.swift",
            root / "native/plugins/kayi-room-scanner/android/src/main/java/de/kayihaustechnik/scanner/KayiRoomScannerPlugin.java",
            root / "native/plugins/kayi-room-scanner/android/src/main/java/de/kayihaustechnik/scanner/ArCoreRoomScanActivity.java",
        ]
        for path in required:
            self.assertTrue(path.exists(), path)
        ios = required[4].read_text(encoding="utf-8")
        android = required[6].read_text(encoding="utf-8")
        web = required[2].read_text(encoding="utf-8")
        self.assertIn("RoomCaptureSession.isSupported", ios)
        self.assertIn("processedResult.export", ios)
        self.assertIn("Config.DepthMode.AUTOMATIC", android)
        self.assertIn("DepthPoint", android)
        self.assertIn("requires_confirmation", (root / "erp/services/native_scans.py").read_text(encoding="utf-8"))
        ios_source = (root / "native/plugins/kayi-room-scanner/ios/Sources/KayiRoomScannerPlugin/KayiRoomScannerPlugin.swift").read_text(encoding="utf-8")
        web_source = (root / "native/www/app.js").read_text(encoding="utf-8")
        self.assertIn('"fallback": !roomPlanSupported', ios_source)
        self.assertIn('"supported": true', ios_source)
        self.assertIn('"capture_mode": "manual_fallback"', ios_source)
        self.assertIn("Manuelles Aufmaß verfügbar", web_source)
        self.assertIn("function clearScannerFeedback()", web_source)
        self.assertIn("async function startScan(projectId){clearScannerFeedback();", web_source)
        self.assertIn("async function listPending(){clearScannerFeedback();", web_source)
        self.assertIn("Keine nicht hochgeladenen Scans vorhanden.", web_source)
        self.assertNotIn("JSON.stringify(data,null,2)", web_source)
        self.assertNotIn("JSON.stringify(uploaded,null,2)", web_source)
        self.assertIn("KayiManualMeasurementViewController", ios_source)
        self.assertIn('modalPresentationStyle = .fullScreen', ios_source)
        self.assertIn('accessibilityLabel = definition.0', ios_source)
        self.assertIn('keyboardWillChangeFrameNotification', ios_source)
        self.assertNotIn("UIAlertController", ios_source)
        self.assertNotIn('call.reject("Bitte gültige Maße eingeben:', ios_source)
        self.assertIn("Scanner.uploadScan", web)
