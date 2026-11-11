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

/// Three tabs:
///  - Dashboard: the real LiveOpsHub dashboard (web, signed in, every screen the site has)
///  - Pick: the mobile Pick screen (/m/pick — built for the phone, same server and data)
///  - Pack: the native Pack station (camera or Bluetooth scanner + packing video)
struct RootView: View {
    enum Tab: Hashable { case dashboard, pick, pack }

    @StateObject private var dashboard = DashboardController()
    @StateObject private var pick = DashboardController()
    @State private var tab: Tab = .dashboard
    @State private var scanRequest: ScanRequest?
    @State private var packTracking: String?
    @State private var packOpenID = UUID()
    @State private var updateRequired = false

    /// A page asked for the camera scanner; the answer goes back to that same page.
    struct ScanRequest: Identifiable { let id: String; let web: WKWebView }

    var body: some View {
        TabView(selection: $tab) {
            webTab(dashboard, startPath: "/")
                .tabItem { Label("Dashboard", systemImage: "square.grid.2x2") }
                .tag(Tab.dashboard)

            webTab(pick, startPath: Self.pickPath, mobileHome: Self.pickPath)
                .tabItem { Label("Pick", systemImage: "checklist") }
                .tag(Tab.pick)

            PackFlowView(initialTracking: packTracking)
                .id(packOpenID)
                .tabItem { Label("Pack", systemImage: "video.badge.checkmark") }
                .tag(Tab.pack)
        }
        .onChange(of: tab) { _, t in
            switch t {
            case .pack:
                Task { await WebSession.shared.syncCookiesToNative() }
            case .pick:
                // Signed in on the Dashboard tab since this tab last loaded? Come back to Pick.
                pick.ensure(prefix: "/m/", path: Self.pickPath)
                pick.focus()
            case .dashboard:
                break
            }
        }
        .sheet(item: $scanRequest) { req in
            ScannerSheet { code in
                req.web.evaluateJavaScript(NativeBridge.resolveScanJS(id: req.id, code: code))
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

    static let pickPath = "/m/pick"

    /// A web tab with its loading bar and offline state.
    private func webTab(_ controller: DashboardController, startPath: String, mobileHome: String? = nil) -> some View {
        WebTab(controller: controller, startPath: startPath, mobileHome: mobileHome) { msg, web in
            handle(msg, from: web)
        }
    }

    private func handle(_ msg: NativeBridge.Message, from web: WKWebView) {
        switch msg {
        case .scan(let id):
            scanRequest = ScanRequest(id: id, web: web)
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

/// One web tab: the page, a thin loading bar, and an offline state with Retry.
/// It observes its own controller so the bar and the offline state update live.
struct WebTab: View {
    @ObservedObject var controller: DashboardController
    var startPath: String
    var mobileHome: String?
    var onNativeMessage: (NativeBridge.Message, WKWebView) -> Void

    var body: some View {
        ZStack(alignment: .top) {
            DashboardWebView(controller: controller, startPath: startPath, mobileHome: mobileHome,
                             onNativeMessage: onNativeMessage)
                .ignoresSafeArea(edges: .bottom)

            if controller.isLoading && controller.progress < 1 {
                ProgressView(value: controller.progress)
                    .progressViewStyle(.linear)
                    .tint(.accentColor)
            }

            if let err = controller.loadError {
                OfflineView(message: err) { controller.loadError = nil; controller.reload() }
            }
        }
    }
}

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
