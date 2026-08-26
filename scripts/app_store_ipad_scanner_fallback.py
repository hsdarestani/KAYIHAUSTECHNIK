from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_required(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Could not apply {label}: expected marker missing in {path.relative_to(ROOT)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_ios_plugin() -> None:
    path = ROOT / "native" / "plugins" / "kayi-room-scanner" / "ios" / "Sources" / "KayiRoomScannerPlugin" / "KayiRoomScannerPlugin.swift"
    replace_required(
        path,
        '''    @objc public func getCapabilities(_ call: CAPPluginCall) {
        call.resolve([
            "supported": RoomCaptureSession.isSupported,
            "provider": "apple_roomplan",
            "lidar": RoomCaptureSession.isSupported,
            "requiresHumanConfirmation": true,
            "deviceModel": UIDevice.current.model,
            "operatingSystem": "iOS \\(UIDevice.current.systemVersion)"
        ])
    }

    @objc public func startScan(_ call: CAPPluginCall) {
        guard RoomCaptureSession.isSupported else {
            call.reject("RoomPlan benötigt ein iPhone oder iPad mit LiDAR-Scanner.", "ROOMPLAN_UNSUPPORTED")
            return
        }
        DispatchQueue.main.async { [weak self] in
            guard let self, let presenter = self.bridge?.viewController else {
                call.reject("Scanner-Oberfläche konnte nicht geöffnet werden.")
                return
            }
            let roomName = String(call.getString("roomName") ?? "Raum").prefix(160)
            let controller = KayiRoomCaptureViewController(roomName: String(roomName))
            controller.onCancel = { call.reject("Scan wurde abgebrochen.", "SCAN_CANCELLED") }
            controller.onComplete = { result in
                do {
                    let pending = try KayiScanStore.save(result: result)
                    call.resolve(pending.dictionary)
                } catch {
                    call.reject("Scan konnte nicht lokal gespeichert werden: \\(error.localizedDescription)")
                }
            }
            presenter.present(controller, animated: true)
        }
    }
''',
        '''    @objc public func getCapabilities(_ call: CAPPluginCall) {
        let roomPlanSupported = RoomCaptureSession.isSupported
        call.resolve([
            // App Store review devices such as iPad Air do not have LiDAR. Keep the
            // project action functional by offering a native manual room-measurement
            // fallback instead of disabling the primary "Scannen" button.
            "supported": true,
            "provider": roomPlanSupported ? "apple_roomplan" : "ios_manual",
            "lidar": roomPlanSupported,
            "fallback": !roomPlanSupported,
            "requiresHumanConfirmation": true,
            "deviceModel": UIDevice.current.model,
            "operatingSystem": "iOS \\(UIDevice.current.systemVersion)"
        ])
    }

    @objc public func startScan(_ call: CAPPluginCall) {
        DispatchQueue.main.async { [weak self] in
            guard let self, let presenter = self.bridge?.viewController else {
                call.reject("Aufmaß-Oberfläche konnte nicht geöffnet werden.")
                return
            }
            let roomName = String(call.getString("roomName") ?? "Raum").prefix(160)
            if !RoomCaptureSession.isSupported {
                self.presentManualMeasurement(call: call, presenter: presenter, roomName: String(roomName))
                return
            }
            let controller = KayiRoomCaptureViewController(roomName: String(roomName))
            controller.onCancel = { call.reject("Scan wurde abgebrochen.", "SCAN_CANCELLED") }
            controller.onComplete = { result in
                do {
                    let pending = try KayiScanStore.save(result: result)
                    call.resolve(pending.dictionary)
                } catch {
                    call.reject("Scan konnte nicht lokal gespeichert werden: \\(error.localizedDescription)")
                }
            }
            presenter.present(controller, animated: true)
        }
    }

    private func presentManualMeasurement(
        call: CAPPluginCall,
        presenter: UIViewController,
        roomName: String,
        previousValues: [String] = [],
        validationMessage: String? = nil
    ) {
        let alert = UIAlertController(
            title: "Manuelles Raumaufmaß",
            message: validationMessage ?? "Dieses Gerät hat keinen LiDAR-Scanner. Bitte Länge, Breite und Höhe eingeben. Das Aufmaß wird anschließend wie ein Scan zur Prüfung gespeichert.",
            preferredStyle: .alert
        )
        let fields: [(String, UIKeyboardType)] = [
            ("Länge in m (z. B. 4,20)", .decimalPad),
            ("Breite in m (z. B. 2,80)", .decimalPad),
            ("Höhe in m (z. B. 2,50)", .decimalPad),
        ]
        for (index, fieldConfiguration) in fields.enumerated() {
            let (placeholder, keyboardType) = fieldConfiguration
            alert.addTextField { field in
                field.placeholder = placeholder
                field.keyboardType = keyboardType
                field.clearButtonMode = .whileEditing
                if previousValues.indices.contains(index) {
                    field.text = previousValues[index]
                }
            }
        }
        alert.addAction(UIAlertAction(title: "Abbrechen", style: .cancel) { _ in
            call.reject("Aufmaß wurde abgebrochen.", "SCAN_CANCELLED")
        })
        alert.addAction(UIAlertAction(title: "Aufmaß speichern", style: .default) { _ in
            let enteredValues = (alert.textFields ?? []).map { $0.text ?? "" }
            let values = enteredValues.compactMap { value -> Double? in
                let normalized = value.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: ",", with: ".")
                return Double(normalized)
            }
            guard values.count == 3,
                  values[0] >= 0.20, values[0] <= 100.0,
                  values[1] >= 0.20, values[1] <= 100.0,
                  values[2] >= 1.20, values[2] <= 20.0 else {
                let message = "Bitte gültige Maße eingeben: Länge/Breite 0,20–100 m und Höhe 1,20–20 m."
                alert.dismiss(animated: true) { [weak self, weak presenter] in
                    guard let self, let presenter else {
                        call.reject(message, "INVALID_MANUAL_DIMENSIONS")
                        return
                    }
                    self.presentManualMeasurement(
                        call: call,
                        presenter: presenter,
                        roomName: roomName,
                        previousValues: enteredValues,
                        validationMessage: message
                    )
                }
                return
            }
            let id = UUID()
            let payload: [String: Any] = [
                "schema_version": "1.0",
                "provider": "apple_roomplan",
                "capture_mode": "manual_fallback",
                "coordinate_system": "right_handed_y_up",
                "room": [
                    "name": roomName,
                    "dimensions": ["length_m": values[0], "width_m": values[1], "height_m": values[2]],
                ],
                "walls": [],
                "doors": [],
                "windows": [],
                "openings": [],
                "objects": [],
                "corners": [],
                "confidence": 0.50,
                "warnings": [
                    "Manuelles Ersatz-Aufmaß auf einem iOS-Gerät ohne LiDAR. Maße vor Angebot oder Bestellung bestätigen."
                ],
            ]
            do {
                let pending = try KayiScanStore.save(result: KayiCapturedResult(id: id, roomName: roomName, payload: payload, modelURL: nil))
                call.resolve(pending.dictionary)
            } catch {
                call.reject("Aufmaß konnte nicht lokal gespeichert werden: \\(error.localizedDescription)")
            }
        })
        presenter.present(alert, animated: true)
    }
''',
        "non-LiDAR iOS fallback",
    )
    replace_required(
        path,
        '''private struct KayiCapturedResult {
    let id: UUID
    let roomName: String
    let payload: [String: Any]
    let modelURL: URL
}
''',
        '''private struct KayiCapturedResult {
    let id: UUID
    let roomName: String
    let payload: [String: Any]
    let modelURL: URL?
}
''',
        "optional model file",
    )
    replace_required(
        path,
        '''        let metadata=KayiPendingScan(scanId:result.id.uuidString,provider:"apple_roomplan",roomName:result.roomName,createdAt:ISO8601DateFormatter().string(from:Date()),payloadPath:payloadURL.path,modelPath:result.modelURL.path)
''',
        '''        let metadata=KayiPendingScan(scanId:result.id.uuidString,provider:"apple_roomplan",roomName:result.roomName,createdAt:ISO8601DateFormatter().string(from:Date()),payloadPath:payloadURL.path,modelPath:result.modelURL?.path ?? "")
''',
        "optional model metadata",
    )
    replace_required(
        path,
        '''        let fileURL=URL(fileURLWithPath:scan.modelPath);let fileData=try Data(contentsOf:fileURL);body.append("--\\(boundary)\\r\\nContent-Disposition: form-data; name=\\"model_file\\"; filename=\\"room.usdz\\"\\r\\nContent-Type: model/vnd.usdz+zip\\r\\n\\r\\n".data(using:.utf8)!);body.append(fileData);body.append("\\r\\n--\\(boundary)--\\r\\n".data(using:.utf8)!);request.httpBody=body
''',
        '''        if !scan.modelPath.isEmpty {
            let fileURL=URL(fileURLWithPath:scan.modelPath)
            if FileManager.default.fileExists(atPath:fileURL.path) {
                let fileData=try Data(contentsOf:fileURL)
                body.append("--\\(boundary)\\r\\nContent-Disposition: form-data; name=\\"model_file\\"; filename=\\"room.usdz\\"\\r\\nContent-Type: model/vnd.usdz+zip\\r\\n\\r\\n".data(using:.utf8)!)
                body.append(fileData)
                body.append("\\r\\n".data(using:.utf8)!)
            }
        }
        body.append("--\\(boundary)--\\r\\n".data(using:.utf8)!);request.httpBody=body
''',
        "optional model upload",
    )


def patch_native_web_shell() -> None:
    path = ROOT / "native" / "www" / "app.js"
    replace_required(
        path,
        "${caps.supported?'Scanner bereit':'Scanner auf diesem Gerät nicht verfügbar'}",
        "${caps.lidar?'LiDAR-Scanner bereit':(caps.fallback?'Manuelles Aufmaß verfügbar':(caps.supported?'Scanner bereit':'Scanner auf diesem Gerät nicht verfügbar'))}",
        "capability message",
    )
    replace_required(path, "status('Scanner wird geöffnet …')", "status('Aufmaß wird geöffnet …')", "scan opening status")
    replace_required(
        path,
        '''async function startScan(projectId){status('Aufmaß wird geöffnet …');try{const scan=await Scanner.startScan({roomName:'Raum'});status('Scan lokal gespeichert. Upload läuft …');const uploaded=await Scanner.uploadScan({scanId:scan.scanId,projectId,apiBaseUrl:state.baseUrl,token:state.token});status('Scan wurde als prüfpflichtiges Aufmaß gespeichert.');document.querySelector('#result').innerHTML=`<pre>${esc(JSON.stringify(uploaded,null,2))}</pre>`}catch(err){status(err.message||String(err),true)}}
async function listPending(){try{const data=await Scanner.listPendingScans();document.querySelector('#result').innerHTML=`<pre>${esc(JSON.stringify(data,null,2))}</pre>`}catch(err){status(err.message,true)}}
''',
        '''function clearScannerFeedback(){status('');const result=document.querySelector('#result');if(result)result.replaceChildren()}
function renderPendingScans(data){
  const result=document.querySelector('#result');if(!result)return;
  const scans=Array.isArray(data?.scans)?data.scans:[];
  if(!scans.length){result.innerHTML='<p class="empty-state">Keine nicht hochgeladenen Scans vorhanden.</p>';return}
  result.innerHTML=`<section class="pending-scans"><h2>Nicht hochgeladene Scans</h2><ul>${scans.map(scan=>`<li><b>${esc(scan.roomName||'Raumaufmaß')}</b><span>${esc(scan.createdAt||'Lokal gespeichert')}</span><small>${esc(scan.scanId||'')}</small></li>`).join('')}</ul></section>`
}
async function startScan(projectId){clearScannerFeedback();status('Aufmaß wird geöffnet …');try{const scan=await Scanner.startScan({roomName:'Raum'});status('Scan lokal gespeichert. Upload läuft …');await Scanner.uploadScan({scanId:scan.scanId,projectId,apiBaseUrl:state.baseUrl,token:state.token});status('Scan wurde als prüfpflichtiges Aufmaß gespeichert.')}catch(err){status(err.message||String(err),true)}}
async function listPending(){clearScannerFeedback();status('Nicht hochgeladene Scans werden geladen …');try{const data=await Scanner.listPendingScans();status('');renderPendingScans(data)}catch(err){status(err.message||String(err),true)}}
''',
        "scanner feedback lifecycle and pending-scan presentation",
    )


def patch_server_semantics() -> None:
    path = ROOT / "erp" / "services" / "native_scans.py"
    replace_required(
        path,
        '''        "schema_version": schema_version,
        "provider": provider,
''',
        '''        "schema_version": schema_version,
        "provider": provider,
        "capture_mode": str(payload.get("capture_mode") or "native_scan")[:40],
''',
        "capture mode normalization",
    )
    replace_required(
        path,
        '''        measurement = RoomMeasurement.objects.create(
            organization=organization,
            project=project,
            name=normalized["room"]["name"],
            method=RoomMeasurement.Method.AR_LIDAR,
''',
        '''        manual_fallback = normalized.get("capture_mode") == "manual_fallback"
        measurement = RoomMeasurement.objects.create(
            organization=organization,
            project=project,
            name=normalized["room"]["name"],
            method=RoomMeasurement.Method.MANUAL if manual_fallback else RoomMeasurement.Method.AR_LIDAR,
''',
        "manual measurement method",
    )
    replace_required(
        path,
        '''            ai_summary=f"Natives Raumaufmaß über {NativeRoomScan.Provider(provider).label}. Benutzerprüfung erforderlich.",
''',
        '''            ai_summary=(
                "Manuelles iOS-Ersatzaufmaß auf einem Gerät ohne LiDAR. Benutzerprüfung erforderlich."
                if manual_fallback
                else f"Natives Raumaufmaß über {NativeRoomScan.Provider(provider).label}. Benutzerprüfung erforderlich."
            ),
''',
        "manual measurement summary",
    )


def patch_tests() -> None:
    path = ROOT / "tests" / "test_native_room_scanner.py"
    text = path.read_text(encoding="utf-8")
    marker = "    def test_ios_manual_fallback_is_accepted_without_model_and_marked_manual(self):"
    if marker not in text:
        anchor = '''    def test_native_scan_upload_is_idempotent(self):
'''
        block = '''    def test_ios_manual_fallback_is_accepted_without_model_and_marked_manual(self):
        payload = self.payload()
        payload.update({
            "capture_mode": "manual_fallback",
            "confidence": 0.50,
            "walls": [],
            "doors": [],
            "windows": [],
            "warnings": ["Manuelles Ersatz-Aufmaß auf einem iOS-Gerät ohne LiDAR."],
        })
        response = self.tech_client.post(reverse("api-native-scans"), {
            "client_scan_id": str(uuid.uuid4()),
            "project_id": self.project.pk,
            "provider": "apple_roomplan",
            "payload": json.dumps(payload),
            "app_version": "2.2.3",
            "device_model": "iPad Air",
            "operating_system": "iPadOS 26.6",
        })
        self.assertEqual(response.status_code, 201, response.content)
        scan = NativeRoomScan.objects.get()
        self.assertFalse(bool(scan.model_file))
        self.assertEqual(scan.normalized_payload["capture_mode"], "manual_fallback")
        self.assertEqual(scan.measurement.method, RoomMeasurement.Method.MANUAL)
        self.assertIn("ohne LiDAR", scan.measurement.ai_summary)

'''
        if anchor not in text:
            raise RuntimeError("Could not add iOS manual fallback backend regression test")
        path.write_text(text.replace(anchor, block + anchor, 1), encoding="utf-8")

    contract = ROOT / "tests" / "test_native_source_contract.py"
    contract_text = contract.read_text(encoding="utf-8")
    if "Manuelles Aufmaß verfügbar" not in contract_text:
        anchor = '''        self.assertIn("requires_confirmation", (root / "erp/services/native_scans.py").read_text(encoding="utf-8"))
'''
        addition = anchor + '''        ios_source = (root / "native/plugins/kayi-room-scanner/ios/Sources/KayiRoomScannerPlugin/KayiRoomScannerPlugin.swift").read_text(encoding="utf-8")
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
        self.assertIn("previousValues: enteredValues", ios_source)
        self.assertIn("validationMessage: message", ios_source)
        self.assertNotIn('call.reject("Bitte gültige Maße eingeben:', ios_source)
'''
        if anchor not in contract_text:
            raise RuntimeError("Could not add native fallback source contract")
        contract.write_text(contract_text.replace(anchor, addition, 1), encoding="utf-8")


def guard() -> None:
    swift = (ROOT / "native/plugins/kayi-room-scanner/ios/Sources/KayiRoomScannerPlugin/KayiRoomScannerPlugin.swift").read_text(encoding="utf-8")
    web = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
    server = (ROOT / "erp/services/native_scans.py").read_text(encoding="utf-8")
    required = [
        ('"supported": true', swift),
        ('"fallback": !roomPlanSupported', swift),
        ('"capture_mode": "manual_fallback"', swift),
        ('modelURL: URL?', swift),
        ('if !scan.modelPath.isEmpty', swift),
        ('Manuelles Aufmaß verfügbar', web),
        ('function clearScannerFeedback()', web),
        ('Keine nicht hochgeladenen Scans vorhanden.', web),
        ('previousValues: enteredValues', swift),
        ('capture_mode', server),
        ('RoomMeasurement.Method.MANUAL if manual_fallback', server),
    ]
    missing = [marker for marker, text in required if marker not in text]
    if missing:
        raise RuntimeError(f"App Store iPad scanner fallback incomplete: {missing}")
    if "${caps.supported?'':'disabled'}" not in web:
        raise RuntimeError("Native Scannen button enable/disable contract changed unexpectedly")
    if "JSON.stringify(data,null,2)" in web or "JSON.stringify(uploaded,null,2)" in web:
        raise RuntimeError("Raw scanner payload remains visible in the App Store shell")
    if 'call.reject("Bitte gültige Maße eingeben:' in swift:
        raise RuntimeError("Invalid manual dimensions still poison the global scanner status")


patch_ios_plugin()
patch_native_web_shell()
patch_server_semantics()
patch_tests()
guard()
print("App Store iPad scanner fallback installed: RoomPlan on LiDAR + manual native measurement on non-LiDAR iOS.")
