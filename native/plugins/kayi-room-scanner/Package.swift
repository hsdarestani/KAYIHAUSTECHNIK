// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "KayiRoomScanner",
    platforms: [.iOS(.v16)],
    products: [.library(name: "KayiRoomScanner", targets: ["KayiRoomScannerPlugin"])],
    dependencies: [.package(url: "https://github.com/ionic-team/capacitor-swift-pm.git", from: "8.0.0")],
    targets: [.target(name: "KayiRoomScannerPlugin", dependencies: [.product(name: "Capacitor", package: "capacitor-swift-pm")], path: "ios/Sources/KayiRoomScannerPlugin")]
)
