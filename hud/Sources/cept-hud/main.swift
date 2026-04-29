// cept-hud — translucent floating panel showing live cept progress.
//
// Reads JSONL events from stdin (one per line). Updates a single floating
// panel in the top-right of the active screen. On EOF (cept closed stdin)
// or terminal phases (run.done / run.error) the panel briefly lingers
// then the process exits.
//
// Build:
//   swift build -c release
// Run (manually, for testing):
//   echo '{"run_id":"x","seq":1,"ts":"now","phase":"locating","level":"info","msg":"finding session"}' | .build/release/cept-hud --once
// From cept:
//   CEPT_HUD_CMD="/abs/path/to/cept-hud --once" cept-cli --goal "..." --emit hud
//   (or symlink cept-hud into $PATH and just use --emit hud)

import AppKit
import SwiftUI
import Foundation

// MARK: - Event model -------------------------------------------------------

struct CeptEvent: Decodable {
    let run_id: String
    let seq: Int
    let ts: String
    let phase: String
    let level: String
    let msg: String
}

// MARK: - State -------------------------------------------------------------

final class HudState: ObservableObject {
    @Published var headline: String = ""
    @Published var phase: String = "starting"
    @Published var msg: String = "cept is warming up…"
    @Published var level: String = "info"
    @Published var seq: Int = 0
    @Published var startedAt: Date = Date()
    @Published var finished: Bool = false

    func apply(_ ev: CeptEvent) {
        // The headline event is a one-shot: it sets the persistent header and
        // does NOT overwrite the phase/msg row. All other events update the
        // running phase/msg as before.
        if ev.phase == "request.headline" {
            self.headline = ev.msg
            self.seq = ev.seq
            return
        }
        self.phase = ev.phase
        self.msg = ev.msg.isEmpty ? ev.phase : ev.msg
        self.level = ev.level
        self.seq = ev.seq
        if ev.phase.hasPrefix("run.done") || ev.phase.hasPrefix("run.error") {
            self.finished = true
        }
    }
}

// MARK: - View --------------------------------------------------------------

struct HudView: View {
    @ObservedObject var state: HudState

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if !state.headline.isEmpty {
                Text(state.headline)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(.primary)
                    .lineLimit(1)
                    .truncationMode(.tail)
            }
            HStack(spacing: 8) {
                Circle()
                    .fill(levelColor)
                    .frame(width: 8, height: 8)
                Text("cept")
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundColor(.secondary)
                Text(state.phase)
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .foregroundColor(.primary)
                Spacer()
                Text(elapsed)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.secondary)
            }
            Text(state.msg)
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .lineLimit(2)
                .truncationMode(.tail)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .frame(width: 380, alignment: .leading)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 10))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(Color.white.opacity(0.08), lineWidth: 0.5)
        )
        .opacity(state.finished ? 0.65 : 1.0)
        .animation(.easeOut(duration: 0.25), value: state.finished)
    }

    private var levelColor: Color {
        switch state.level {
        case "error": return .red
        case "warn":  return .orange
        default:      return state.finished ? .green : .blue
        }
    }

    private var elapsed: String {
        let s = Int(Date().timeIntervalSince(state.startedAt))
        if s < 60 { return "\(s)s" }
        return "\(s / 60)m\(s % 60)s"
    }
}

// MARK: - App delegate ------------------------------------------------------

final class AppDelegate: NSObject, NSApplicationDelegate {
    var panel: NSPanel?
    let state = HudState()
    var fadeTimer: Timer?
    var elapsedTimer: Timer?

    func applicationDidFinishLaunching(_: Notification) {
        let view = HudView(state: state)
        let hosting = NSHostingView(rootView: view)

        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 380, height: 96),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.contentView = hosting
        panel.level = .floating
        panel.isFloatingPanel = true
        panel.becomesKeyOnlyIfNeeded = true
        panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle, .fullScreenAuxiliary]
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.isOpaque = false
        panel.ignoresMouseEvents = true

        if let screen = NSScreen.main {
            let r = screen.visibleFrame
            let x = r.maxX - 380 - 24
            let y = r.maxY - 96 - 36
            panel.setFrameOrigin(NSPoint(x: x, y: y))
        }
        panel.orderFrontRegardless()
        self.panel = panel

        // Force the SwiftUI elapsed counter to redraw every second.
        elapsedTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            // Triggering an objectWillChange via a no-op @Published touch.
            Task { @MainActor in
                let s = self.state
                let cur = s.seq
                s.seq = cur  // re-assign to nudge SwiftUI
            }
        }

        // Read stdin on a background thread.
        let pipe = FileHandle.standardInput
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.readLoop(handle: pipe)
        }
    }

    private func readLoop(handle: FileHandle) {
        var buffer = Data()
        let decoder = JSONDecoder()
        while true {
            let chunk = handle.availableData
            if chunk.isEmpty {
                // EOF
                DispatchQueue.main.async { [weak self] in
                    self?.handleEOF()
                }
                return
            }
            buffer.append(chunk)
            while let nl = buffer.firstIndex(of: 0x0A /* \n */) {
                let idx = buffer.distance(from: buffer.startIndex, to: nl)
                let line = buffer.subdata(in: 0..<idx)
                buffer.removeSubrange(0...idx)
                if line.isEmpty { continue }
                if let ev = try? decoder.decode(CeptEvent.self, from: line) {
                    DispatchQueue.main.async { [weak self] in
                        self?.state.apply(ev)
                        if self?.state.finished == true {
                            self?.scheduleFade(after: 1.5)
                        }
                    }
                }
            }
        }
    }

    private func handleEOF() {
        // Even if no terminal phase arrived, fade after a short grace period.
        state.finished = true
        scheduleFade(after: 1.0)
    }

    private func scheduleFade(after seconds: TimeInterval) {
        fadeTimer?.invalidate()
        fadeTimer = Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { _ in
            NSApp.terminate(nil)
        }
    }
}

// MARK: - Entry ------------------------------------------------------------

// Mode flag is a no-op for v1 — the only behavior is "read stdin until EOF
// then exit." Reserving --once for future --listen mode parity.
let _args = CommandLine.arguments

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)  // no Dock icon
app.run()
