import SwiftUI
import WebKit

@main
struct LiveOpsHubApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}

/// Two tabs: the real LiveOpsHub dashboard (web, signed in, every screen the site has)
/// and the native Pack station (camera scanner + packing video).
struct RootView: View {
    enum Tab: Hashable { case dashboard, pack }

    @StateObject private var dashboard = DashboardController()
    @State private var tab: Tab = .dashboard
    @State private var scanRequest: ScanRequest?
    @State private var packTracking: String?
    @State private var packOpenID = UUID()
    @State private var updateRequired = false

    struct ScanRequest: Identifiable { let id: String }

    var body: some View {
        TabView(selection: $tab) {
            dashboardTab
                .tabItem { Label("Dashboard", systemImage: "square.grid.2x2") }
                .tag(Tab.dashboard)

            PackFlowView(initialTracking: packTracking)
                .id(packOpenID)
                .tabItem { Label("Pack", systemImage: "video.badge.checkmark") }
                .tag(Tab.pack)
        }
        .onChange(of: tab) { _, t in
            if t == .pack { Task { await WebSession.shared.syncCookiesToNative() } }
        }
        .sheet(item: $scanRequest) { req in
            ScannerSheet { code in
                dashboard.evaluate(NativeBridge.resolveScanJS(id: req.id, code: code))
                scanRequest = nil
            }
        }
        .sheet(item: Binding(get: { dashboard.downloadedFile.map(DownloadItem.init) },
                             set: { if $0 == nil { dashboard.downloadedFile = nil } })) { item in
            ShareSheet(url: item.url).presentationDetents([.medium, .large])
        }
        .fullScreenCover(isPresented: $updateRequired) { UpdateRequiredView() }
        .task { await checkVersion() }
    }

    private var dashboardTab: some View {
        ZStack(alignment: .top) {
            DashboardWebView(controller: dashboard, startPath: "/") { msg, _ in
                handle(msg)
            }
            .ignoresSafeArea(edges: .bottom)

            if dashboard.isLoading && dashboard.progress < 1 {
                ProgressView(value: dashboard.progress)
                    .progressViewStyle(.linear)
                    .tint(.accentColor)
            }

            if let err = dashboard.loadError {
                OfflineView(message: err) { dashboard.loadError = nil; dashboard.reload() }
            }
        }
    }

    private func handle(_ msg: NativeBridge.Message) {
        switch msg {
        case .scan(let id):
            scanRequest = ScanRequest(id: id)
        case .pack(let tracking):
            packTracking = tracking
            packOpenID = UUID()
            tab = .pack
        case .haptic(let style):
            switch style {
            case "success": UINotificationFeedbackGenerator().notificationOccurred(.success)
            case "warning": UINotificationFeedbackGenerator().notificationOccurred(.warning)
            case "error": UINotificationFeedbackGenerator().notificationOccurred(.error)
            default: UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
        }
    }

    private func checkVersion() async {
        guard let s = try? await APIClient.shared.fetchSession(), let min = s.minVersion else { return }
        updateRequired = Self.isVersion(APIClient.appVersion, olderThan: min)
    }

    static func isVersion(_ a: String, olderThan b: String) -> Bool {
        let pa = a.split(separator: ".").map { Int($0) ?? 0 }
        let pb = b.split(separator: ".").map { Int($0) ?? 0 }
        for i in 0..<max(pa.count, pb.count) {
            let x = i < pa.count ? pa[i] : 0, y = i < pb.count ? pb[i] : 0
            if x != y { return x < y }
        }
        return false
    }
}

struct DownloadItem: Identifiable { let url: URL; var id: String { url.path } }

/// Native camera scanner for `LOHubNative.scan()` calls from the web app.
struct ScannerSheet: View {
    var onDone: (String?) -> Void
    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                if BarcodeScannerView.isAvailable {
                    BarcodeScannerView { code in onDone(code) }
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                } else {
                    ContentUnavailableView("Camera unavailable", systemImage: "barcode.viewfinder",
                                           description: Text("Type the code instead."))
                }
                ManualCodeEntry(placeholder: "Type a code") { onDone($0) }
            }
            .padding()
            .navigationTitle("Scan")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { Button("Cancel") { onDone(nil) } }
        }
        .interactiveDismissDisabled()
    }
}

struct OfflineView: View {
    let message: String
    var retry: () -> Void
    var body: some View {
        ContentUnavailableView {
            Label("Can't reach LiveOpsHub", systemImage: "wifi.exclamationmark")
        } description: {
            Text(message)
        } actions: {
            Button("Try again", action: retry).buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
    }
}

struct UpdateRequiredView: View {
    var body: some View {
        ContentUnavailableView {
            Label("Update required", systemImage: "arrow.down.app")
        } description: {
            Text("This version of LiveOpsHub is no longer supported. Update from the App Store to continue.")
        } actions: {
            Link("Open App Store", destination: URL(string: "itms-apps://apps.apple.com")!)
                .buttonStyle(.borderedProminent)
        }
    }
}
