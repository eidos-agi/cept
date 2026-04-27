// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "cept-hud",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "cept-hud", targets: ["cept-hud"])
    ],
    targets: [
        .executableTarget(
            name: "cept-hud",
            path: "Sources/cept-hud"
        )
    ],
    swiftLanguageVersions: [.v5]
)
