import SwiftUI

@main
struct LiveOpsHubApp: App {
    @State private var app = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(app)
                .task { await app.bootstrap() }
        }
    }
}

struct RootView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        switch app.phase {
        case .launching:
            ZStack {
                Color.accentColor.ignoresSafeArea()
                ProgressView().tint(.white)
            }
        case .signedOut:
            LoginView()
        case .updateRequired:
            UpdateRequiredView()
        case .signedIn:
            MainTabView()
        }
    }
}

struct MainTabView: View {
    @Environment(AppState.self) private var app

    var body: some View {
        TabView {
            if app.canPack {
                PackFlowView()
                    .tabItem { Label("Pack", systemImage: "video.badge.checkmark") }
            }
            if app.canPick {
                PickQueueView()
                    .tabItem { Label("Pick", systemImage: "checklist") }
            }
            OrderLookupView()
                .tabItem { Label("Lookup", systemImage: "magnifyingglass") }
            HomeView()
                .tabItem { Label("Today", systemImage: "chart.bar") }
            SettingsView()
                .tabItem { Label("Account", systemImage: "person.crop.circle") }
        }
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
