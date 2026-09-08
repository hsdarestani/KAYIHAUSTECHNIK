import Foundation
import UIKit
import RoomPlan
import Capacitor
import simd

@objc(KayiRoomScannerPlugin)
public final class KayiRoomScannerPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "KayiRoomScannerPlugin"
    public let jsName = "KayiRoomScanner"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "getCapabilities", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "startScan", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "listPendingScans", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "uploadScan", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "deletePendingScan", returnType: CAPPluginReturnPromise)
    ]

    @objc public func getCapabilities(_ call: CAPPluginCall) {
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
            "operatingSystem": "iOS \(UIDevice.current.systemVersion)"
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
                    call.reject("Scan konnte nicht lokal gespeichert werden: \(error.localizedDescription)")
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
                call.reject("Aufmaß konnte nicht lokal gespeichert werden: \(error.localizedDescription)")
            }
        }
        presenter.present(controller, animated: true)
    }

    @objc public func listPendingScans(_ call: CAPPluginCall) {
        do {
            call.resolve(["scans": try KayiScanStore.list().map(\.dictionary)])
        } catch {
            call.reject("Lokale Scans konnten nicht gelesen werden: \(error.localizedDescription)")
        }
    }

    @objc public func uploadScan(_ call: CAPPluginCall) {
        guard let scanId = call.getString("scanId"),
              let projectId = call.getInt("projectId"),
              let apiBaseURL = call.getString("apiBaseUrl"),
              let token = call.getString("token"), !token.isEmpty else {
            call.reject("scanId, projectId, apiBaseUrl und token sind erforderlich.")
            return
        }
        Task {
            do {
                let response = try await KayiScanUploader.upload(scanId: scanId, projectId: projectId, apiBaseURL: apiBaseURL, token: token)
                call.resolve(response)
            } catch {
                call.reject("Upload fehlgeschlagen: \(error.localizedDescription)", "UPLOAD_FAILED")
            }
        }
    }

    @objc public func deletePendingScan(_ call: CAPPluginCall) {
        guard let scanId = call.getString("scanId") else { call.reject("scanId fehlt."); return }
        do { call.resolve(["deleted": try KayiScanStore.delete(scanId: scanId)]) }
        catch { call.reject("Scan konnte nicht gelöscht werden: \(error.localizedDescription)") }
    }
}

private final class KayiManualMeasurementViewController: UIViewController, UITextFieldDelegate {
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
    let modelURL: URL?
}

private final class KayiRoomCaptureViewController: UIViewController, RoomCaptureViewDelegate {
    private let captureView = RoomCaptureView(frame: .zero)
    private let roomName: String
    private var hasStopped = false
    var onComplete: ((KayiCapturedResult) -> Void)?
    var onCancel: (() -> Void)?

    init(roomName: String) { self.roomName = roomName; super.init(nibName: nil, bundle: nil); modalPresentationStyle = .fullScreen }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        captureView.delegate = self
        captureView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(captureView)
        NSLayoutConstraint.activate([
            captureView.leadingAnchor.constraint(equalTo: view.leadingAnchor), captureView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            captureView.topAnchor.constraint(equalTo: view.topAnchor), captureView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        let top = UIVisualEffectView(effect: UIBlurEffect(style: .systemThinMaterialDark))
        top.translatesAutoresizingMaskIntoConstraints = false; top.layer.cornerRadius = 18; top.clipsToBounds = true
        let title = UILabel(); title.text = "Raum vollständig scannen"; title.textColor = .white; title.font = .boldSystemFont(ofSize: 17)
        let hint = UILabel(); hint.text = "Langsam alle Wände, Türen, Fenster, Boden und Decke erfassen."; hint.textColor = .white; hint.font = .systemFont(ofSize: 12); hint.numberOfLines = 2
        let labels = UIStackView(arrangedSubviews: [title, hint]); labels.axis = .vertical; labels.spacing = 3
        let cancel = UIButton(type: .system); cancel.setTitle("Abbrechen", for: .normal); cancel.setTitleColor(.white, for: .normal); cancel.addTarget(self, action: #selector(cancelTapped), for: .touchUpInside)
        let row = UIStackView(arrangedSubviews: [labels, cancel]); row.spacing = 12; row.alignment = .center; row.translatesAutoresizingMaskIntoConstraints = false
        top.contentView.addSubview(row); view.addSubview(top)
        let done = UIButton(type: .system); done.setTitle("Scan beenden & prüfen", for: .normal); done.setTitleColor(.white, for: .normal); done.titleLabel?.font = .boldSystemFont(ofSize: 17); done.backgroundColor = UIColor(red: 0.09, green: 0.41, blue: 0.88, alpha: 0.96); done.layer.cornerRadius = 17; done.translatesAutoresizingMaskIntoConstraints = false; done.addTarget(self, action: #selector(doneTapped), for: .touchUpInside); view.addSubview(done)
        NSLayoutConstraint.activate([
            top.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 12), top.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -12), top.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 8),
            row.leadingAnchor.constraint(equalTo: top.contentView.leadingAnchor, constant: 14), row.trailingAnchor.constraint(equalTo: top.contentView.trailingAnchor, constant: -14), row.topAnchor.constraint(equalTo: top.contentView.topAnchor, constant: 10), row.bottomAnchor.constraint(equalTo: top.contentView.bottomAnchor, constant: -10),
            done.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 20), done.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -20), done.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -16), done.heightAnchor.constraint(equalToConstant: 56)
        ])
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        captureView.captureSession.run(configuration: RoomCaptureSession.Configuration())
    }

    @objc private func doneTapped() { guard !hasStopped else { return }; hasStopped = true; captureView.captureSession.stop() }
    @objc private func cancelTapped() { captureView.captureSession.stop(); dismiss(animated: true) { self.onCancel?() } }
    func captureView(shouldPresent roomDataForProcessing: CapturedRoomData, error: Error?) -> Bool { error == nil }

    func captureView(didPresent processedResult: CapturedRoom, error: Error?) {
        if let error { dismiss(animated: true) { self.onCancel?() }; return }
        do {
            let id = UUID()
            let directory = try KayiScanStore.directory(for: id, create: true)
            let modelURL = directory.appendingPathComponent("room.usdz")
            try processedResult.export(to: modelURL, exportOptions: .parametric)
            let payload = KayiRoomSerializer.payload(room: processedResult, roomName: roomName)
            dismiss(animated: true) { self.onComplete?(KayiCapturedResult(id: id, roomName: self.roomName, payload: payload, modelURL: modelURL)) }
        } catch {
            dismiss(animated: true) { self.onCancel?() }
        }
    }
}

private enum KayiRoomSerializer {
    static func payload(room: CapturedRoom, roomName: String) -> [String: Any] {
        let walls = room.walls.map { surface($0) }
        let doors = room.doors.map { surface($0) }
        let windows = room.windows.map { surface($0) }
        let openings = room.openings.map { surface($0) }
        let objects = room.objects.map { object($0) }
        let allSurfaces = room.walls + room.doors + room.windows + room.openings
        let bounds = roomBounds(surfaces: allSurfaces)
        return [
            "schema_version": "1.0", "provider": "apple_roomplan", "coordinate_system": "right_handed_y_up",
            "room": ["name": roomName, "dimensions": bounds], "walls": walls, "doors": doors, "windows": windows,
            "openings": openings, "objects": objects, "corners": [], "confidence": 0.88,
            "warnings": ["RoomPlan-Aufmaß vor Angebot oder Bestellung durch einen Benutzer bestätigen."]
        ]
    }
    static func surface(_ item: CapturedRoom.Surface) -> [String: Any] {
        ["identifier": item.identifier.uuidString, "category": String(describing: item.category), "dimensions": dimensions(item.dimensions), "transform": matrix(item.transform)]
    }
    static func object(_ item: CapturedRoom.Object) -> [String: Any] {
        ["identifier": item.identifier.uuidString, "category": String(describing: item.category), "dimensions": dimensions(item.dimensions), "transform": matrix(item.transform)]
    }
    static func dimensions(_ d: simd_float3) -> [String: Double] { ["width_m": Double(d.x), "height_m": Double(d.y), "depth_m": Double(d.z)] }
    static func matrix(_ m: simd_float4x4) -> [Double] { [m.columns.0.x,m.columns.0.y,m.columns.0.z,m.columns.0.w,m.columns.1.x,m.columns.1.y,m.columns.1.z,m.columns.1.w,m.columns.2.x,m.columns.2.y,m.columns.2.z,m.columns.2.w,m.columns.3.x,m.columns.3.y,m.columns.3.z,m.columns.3.w].map(Double.init) }
    static func roomBounds(surfaces: [CapturedRoom.Surface]) -> [String: Double] {
        guard !surfaces.isEmpty else { return ["length_m": 0.2, "width_m": 0.2, "height_m": 1.2] }
        var minX = Float.greatestFiniteMagnitude, maxX = -Float.greatestFiniteMagnitude, minZ = Float.greatestFiniteMagnitude, maxZ = -Float.greatestFiniteMagnitude, height: Float = 0
        for surface in surfaces {
            let center = surface.transform.columns.3
            let radius = max(surface.dimensions.x, surface.dimensions.z, 0.05) / 2
            minX = min(minX, center.x - radius); maxX = max(maxX, center.x + radius); minZ = min(minZ, center.z - radius); maxZ = max(maxZ, center.z + radius); height = max(height, surface.dimensions.y)
        }
        return ["length_m": Double(max(maxX-minX,0.2)), "width_m": Double(max(maxZ-minZ,0.2)), "height_m": Double(max(height,1.2))]
    }
}

private struct KayiPendingScan: Codable {
    let scanId: String; let provider: String; let roomName: String; let createdAt: String; let payloadPath: String; let modelPath: String
    var dictionary: [String: Any] { ["scanId":scanId,"provider":provider,"roomName":roomName,"createdAt":createdAt,"payloadPath":payloadPath,"modelPath":modelPath] }
}

private enum KayiScanStore {
    static var root: URL { FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("KayiRoomScans", isDirectory: true) }
    static func directory(for id: UUID, create: Bool) throws -> URL { let url=root.appendingPathComponent(id.uuidString,isDirectory:true); if create { try FileManager.default.createDirectory(at:url,withIntermediateDirectories:true) }; return url }
    static func save(result: KayiCapturedResult) throws -> KayiPendingScan {
        let dir=try directory(for:result.id,create:true); let payloadURL=dir.appendingPathComponent("payload.json"); try JSONSerialization.data(withJSONObject:result.payload,options:[.prettyPrinted,.sortedKeys]).write(to:payloadURL,options:.atomic)
        let metadata=KayiPendingScan(scanId:result.id.uuidString,provider:"apple_roomplan",roomName:result.roomName,createdAt:ISO8601DateFormatter().string(from:Date()),payloadPath:payloadURL.path,modelPath:result.modelURL?.path ?? "")
        try JSONEncoder().encode(metadata).write(to:dir.appendingPathComponent("metadata.json"),options:.atomic); return metadata
    }
    static func list() throws -> [KayiPendingScan] { guard FileManager.default.fileExists(atPath:root.path) else{return []}; return try FileManager.default.contentsOfDirectory(at:root,includingPropertiesForKeys:nil).compactMap{try? JSONDecoder().decode(KayiPendingScan.self,from:Data(contentsOf:$0.appendingPathComponent("metadata.json")))}.sorted{$0.createdAt>$1.createdAt} }
    static func load(scanId:String)throws->KayiPendingScan{guard let item=try list().first(where:{$0.scanId==scanId})else{throw NSError(domain:"KayiScanner",code:404,userInfo:[NSLocalizedDescriptionKey:"Lokaler Scan nicht gefunden."])};return item}
    static func delete(scanId:String)throws->Bool{guard let id=UUID(uuidString:scanId)else{return false};let dir=try directory(for:id,create:false);guard FileManager.default.fileExists(atPath:dir.path)else{return false};try FileManager.default.removeItem(at:dir);return true}
}

private enum KayiScanUploader {
    static func upload(scanId:String,projectId:Int,apiBaseURL:String,token:String)async throws->[String:Any]{
        let scan=try KayiScanStore.load(scanId:scanId);guard let url=URL(string:apiBaseURL.trimmingCharacters(in:CharacterSet(charactersIn:"/"))+"/api/native-scans/")else{throw URLError(.badURL)}
        let boundary="Boundary-\(UUID().uuidString)";var request=URLRequest(url:url);request.httpMethod="POST";request.setValue("Token \(token)",forHTTPHeaderField:"Authorization");request.setValue("multipart/form-data; boundary=\(boundary)",forHTTPHeaderField:"Content-Type")
        var body=Data();func field(_ name:String,_ value:String){body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(name)\"\r\n\r\n\(value)\r\n".data(using:.utf8)!)}
        field("client_scan_id",scan.scanId);field("project_id",String(projectId));field("provider",scan.provider);field("app_version",Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "");field("device_model",UIDevice.current.model);field("operating_system","iOS \(UIDevice.current.systemVersion)");field("payload",String(data:try Data(contentsOf:URL(fileURLWithPath:scan.payloadPath)),encoding:.utf8) ?? "{}")
        if !scan.modelPath.isEmpty {
            let fileURL=URL(fileURLWithPath:scan.modelPath)
            if FileManager.default.fileExists(atPath:fileURL.path) {
                let fileData=try Data(contentsOf:fileURL)
                body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"model_file\"; filename=\"room.usdz\"\r\nContent-Type: model/vnd.usdz+zip\r\n\r\n".data(using:.utf8)!)
                body.append(fileData)
                body.append("\r\n".data(using:.utf8)!)
            }
        }
        body.append("--\(boundary)--\r\n".data(using:.utf8)!);request.httpBody=body
        let(data,response)=try await URLSession.shared.data(for:request);guard let http=response as? HTTPURLResponse,(200...299).contains(http.statusCode)else{throw NSError(domain:"KayiScanner",code:(response as? HTTPURLResponse)?.statusCode ?? 500,userInfo:[NSLocalizedDescriptionKey:String(data:data,encoding:.utf8) ?? "Serverfehler"])}
        return (try JSONSerialization.jsonObject(with:data) as? [String:Any]) ?? [:]
    }
}
