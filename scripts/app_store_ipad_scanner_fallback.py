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


def replace_struct_with_prefix(path: Path, prefixed_old: str, new_struct: str, label: str) -> None:
    """Replace a source struct while inserting the controller declared before it."""
    marker = "private struct KayiCapturedResult {"
    marker_index = prefixed_old.find(marker)
    if marker_index < 0:
        raise RuntimeError(f"Could not apply {label}: embedded struct marker is missing")
    prefix = prefixed_old[:marker_index]
    old_struct = prefixed_old[marker_index:]
    desired = prefix + new_struct
    text = path.read_text(encoding="utf-8")
    if desired in text:
        return
    if old_struct not in text:
        raise RuntimeError(f"Could not apply {label}: expected struct missing in {path.relative_to(ROOT)}")
    path.write_text(text.replace(old_struct, desired, 1), encoding="utf-8")


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

    private func presentManualMeasurement(call: CAPPluginCall, presenter: UIViewController, roomName: String) {
        let controller = KayiManualMeasurementViewController()
        controller.onCancel = {
            call.reject("Aufmaß wurde abgebrochen.", "SCAN_CANCELLED")
        }
        controller.onSave = { values in
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
        }
        presenter.present(controller, animated: true)
    }
''',
        "non-LiDAR iOS fallback",
    )
    replace_struct_with_prefix(
        path,
        '''private final class KayiManualMeasurementViewController: UIViewController, UITextFieldDelegate {
    private let scrollView = UIScrollView()
    private let stack = UIStackView()
    private let validationLabel = UILabel()
    private var fields: [UITextField] = []
    var onCancel: (() -> Void)?
    var onSave: (([Double]) -> Void)?

    init() {
        super.init(nibName: nil, bundle: nil)
        modalPresentationStyle = .fullScreen
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        configureLayout()
        NotificationCenter.default.addObserver(self, selector: #selector(keyboardChanged), name: UIResponder.keyboardWillChangeFrameNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(keyboardHidden), name: UIResponder.keyboardWillHideNotification, object: nil)
    }

    deinit { NotificationCenter.default.removeObserver(self) }

    private func configureLayout() {
        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.keyboardDismissMode = .interactive
        scrollView.alwaysBounceVertical = true
        view.addSubview(scrollView)

        stack.axis = .vertical
        stack.spacing = 18
        stack.translatesAutoresizingMaskIntoConstraints = false
        scrollView.addSubview(stack)

        let title = UILabel()
        title.text = "Manuelles Raumaufmaß"
        title.font = .boldSystemFont(ofSize: 28)
        title.numberOfLines = 0
        stack.addArrangedSubview(title)

        let hint = UILabel()
        hint.text = "Dieses iPad hat keinen LiDAR-Scanner. Bitte Länge, Breite und Höhe eingeben."
        hint.font = .preferredFont(forTextStyle: .body)
        hint.textColor = .secondaryLabel
        hint.numberOfLines = 0
        stack.addArrangedSubview(hint)

        let definitions = [
            ("Länge / Tiefe", "z. B. 4,20"),
            ("Breite", "z. B. 2,80"),
            ("Höhe", "z. B. 2,50"),
        ]
        fields = definitions.enumerated().map { index, definition in
            let label = UILabel()
            label.text = definition.0
            label.font = .preferredFont(forTextStyle: .headline)
            let field = UITextField()
            field.placeholder = definition.1
            field.keyboardType = .decimalPad
            field.borderStyle = .roundedRect
            field.clearButtonMode = .whileEditing
            field.font = .preferredFont(forTextStyle: .title3)
            field.adjustsFontForContentSizeCategory = true
            field.delegate = self
            field.tag = index
            field.accessibilityLabel = definition.0
            field.translatesAutoresizingMaskIntoConstraints = false
            field.heightAnchor.constraint(greaterThanOrEqualToConstant: 50).isActive = true
            let group = UIStackView(arrangedSubviews: [label, field])
            group.axis = .vertical
            group.spacing = 7
            stack.addArrangedSubview(group)
            return field
        }

        validationLabel.textColor = .systemRed
        validationLabel.font = .preferredFont(forTextStyle: .footnote)
        validationLabel.numberOfLines = 0
        validationLabel.isHidden = true
        validationLabel.accessibilityIdentifier = "manualMeasurementValidation"
        stack.addArrangedSubview(validationLabel)

        let save = UIButton(type: .system)
        save.setTitle("Aufmaß speichern", for: .normal)
        save.titleLabel?.font = .boldSystemFont(ofSize: 17)
        save.backgroundColor = .systemBlue
        save.setTitleColor(.white, for: .normal)
        save.layer.cornerRadius = 12
        save.heightAnchor.constraint(equalToConstant: 54).isActive = true
        save.accessibilityIdentifier = "manualMeasurementSave"
        save.addTarget(self, action: #selector(saveTapped), for: .touchUpInside)
        stack.addArrangedSubview(save)

        let cancel = UIButton(type: .system)
        cancel.setTitle("Abbrechen", for: .normal)
        cancel.heightAnchor.constraint(equalToConstant: 48).isActive = true
        cancel.addTarget(self, action: #selector(cancelTapped), for: .touchUpInside)
        stack.addArrangedSubview(cancel)

        NSLayoutConstraint.activate([
            scrollView.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor),
            scrollView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            scrollView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            stack.leadingAnchor.constraint(equalTo: scrollView.contentLayoutGuide.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: scrollView.contentLayoutGuide.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: scrollView.contentLayoutGuide.topAnchor, constant: 28),
            stack.bottomAnchor.constraint(equalTo: scrollView.contentLayoutGuide.bottomAnchor, constant: -28),
            stack.widthAnchor.constraint(equalTo: scrollView.frameLayoutGuide.widthAnchor, constant: -48),
        ])
    }

    @objc private func saveTapped() {
        view.endEditing(true)
        let values = fields.compactMap { field -> Double? in
            let normalized = (field.text ?? "").trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: ",", with: ".")
            return Double(normalized)
        }
        guard values.count == 3,
              values[0] >= 0.20, values[0] <= 100.0,
              values[1] >= 0.20, values[1] <= 100.0,
              values[2] >= 1.20, values[2] <= 20.0 else {
            validationLabel.text = "Bitte gültige Maße eingeben: Länge/Breite 0,20–100 m und Höhe 1,20–20 m."
            validationLabel.isHidden = false
            UIAccessibility.post(notification: .announcement, argument: validationLabel.text)
            return
        }
        dismiss(animated: true) { [onSave] in onSave?(values) }
    }

    @objc private func cancelTapped() {
        dismiss(animated: true) { [onCancel] in onCancel?() }
    }

    func textFieldShouldReturn(_ textField: UITextField) -> Bool {
        let next = textField.tag + 1
        if fields.indices.contains(next) { fields[next].becomeFirstResponder() }
        else { textField.resignFirstResponder() }
        return true
    }

    @objc private func keyboardChanged(_ notification: Notification) {
        guard let frame = notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect else { return }
        let covered = max(0, view.bounds.maxY - view.convert(frame, from: nil).minY)
        scrollView.contentInset.bottom = covered
        scrollView.verticalScrollIndicatorInsets.bottom = covered
    }

    @objc private func keyboardHidden() {
        scrollView.contentInset.bottom = 0
        scrollView.verticalScrollIndicatorInsets.bottom = 0
    }
}

private struct KayiCapturedResult {
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
        "dedicated iPad manual measurement form and optional model file",
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
        self.assertIn("KayiManualMeasurementViewController", ios_source)
        self.assertIn('modalPresentationStyle = .fullScreen', ios_source)
        self.assertIn('accessibilityLabel = definition.0', ios_source)
        self.assertIn('keyboardWillChangeFrameNotification', ios_source)
        self.assertNotIn("UIAlertController", ios_source)
        self.assertNotIn('call.reject("Bitte gültige Maße eingeben:', ios_source)
'''
        if anchor not in contract_text:
            raise RuntimeError("Could not add native fallback source contract")
        contract.write_text(contract_text.replace(anchor, addition, 1), encoding="utf-8")
    else:
        stale = '''        self.assertIn("previousValues: enteredValues", ios_source)
        self.assertIn("validationMessage: message", ios_source)
        self.assertNotIn('call.reject("Bitte gültige Maße eingeben:', ios_source)
'''
        current = '''        self.assertIn("KayiManualMeasurementViewController", ios_source)
        self.assertIn('modalPresentationStyle = .fullScreen', ios_source)
        self.assertIn('accessibilityLabel = definition.0', ios_source)
        self.assertIn('keyboardWillChangeFrameNotification', ios_source)
        self.assertNotIn("UIAlertController", ios_source)
        self.assertNotIn('call.reject("Bitte gültige Maße eingeben:', ios_source)
'''
        if stale in contract_text:
            contract.write_text(contract_text.replace(stale, current, 1), encoding="utf-8")


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
        ('KayiManualMeasurementViewController', swift),
        ('modalPresentationStyle = .fullScreen', swift),
        ('accessibilityLabel = definition.0', swift),
        ('keyboardWillChangeFrameNotification', swift),
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
    if "UIAlertController" in swift:
        raise RuntimeError("iPad manual measurement still uses the fragile alert form")


patch_ios_plugin()
patch_native_web_shell()
patch_server_semantics()
patch_tests()
guard()
print("App Store iPad scanner fallback installed: RoomPlan on LiDAR + manual native measurement on non-LiDAR iOS.")
