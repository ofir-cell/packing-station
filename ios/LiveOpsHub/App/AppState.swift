import Foundation
import Observation

/// Global signed-in state. One instance lives for the life of the app.
@MainActor
@Observable
final class AppState {
    enum Phase: Equatable { case launching, signedOut, signedIn, updateRequired }

    var phase: Phase = .launching
    var user: String = ""
    var name: String = ""
    var roles: [String] = []
    var org: String = ""
    var companyName: String = ""
    var bannerError: String?

    private let api = APIClient.shared

    // Role gates mirror the server's decorators (the server stays the real gate).
    var isAdmin: Bool { roles.contains("admin") }
    var canManage: Bool { roles.contains { ["admin", "manager", "cs"].contains($0) } }
    var canPick: Bool { roles.contains { ["picker", "worker", "admin", "cs", "manager"].contains($0) } }
    var canPack: Bool { roles.contains { ["worker", "picker", "admin", "cs", "manager"].contains($0) } }
    var canConnectShops: Bool { roles.contains("admin") }

    func bootstrap() async {
        do {
            let s = try await api.fetchSession()
            if let min = s.minVersion, Self.isVersion(APIClient.appVersion, olderThan: min) {
                phase = .updateRequired; return
            }
            apply(s)
        } catch {
            // Offline at launch: show sign-in with the reason rather than spinning forever.
            bannerError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            phase = .signedOut
        }
    }

    func signIn(username: String, password: String) async throws {
        try await api.fetchSession()                       // fresh CSRF token
        let r: LoginResponse = try await api.post("/api/login",
                                                  body: ["username": username, "password": password])
        guard r.ok else { throw APIError.server(r.error ?? "Sign-in failed") }
        apply(try await api.fetchSession())
    }

    func signOut() async {
        // /logout clears the server session; ignore the HTML redirect it returns.
        var req = URLRequest(url: api.baseURL.appendingPathComponent("/logout"))
        req.setValue("lohub-ios/\(APIClient.appVersion)", forHTTPHeaderField: "X-Client")
        _ = try? await URLSession.shared.data(for: req)
        api.clearCookies()
        reset()
    }

    /// Called whenever any request reports the session is gone.
    func handle(_ error: Error) {
        if let e = error as? APIError, e == .notSignedIn {
            api.clearCookies(); reset()
        }
    }

    func reset() {
        user = ""; name = ""; roles = []; org = ""; companyName = ""
        phase = .signedOut
    }

    private func apply(_ s: SessionInfo) {
        guard s.signedIn else { reset(); return }
        user = s.user ?? ""
        name = s.name ?? s.user ?? ""
        roles = s.roles ?? [s.role].compactMap { $0 }
        org = s.org ?? ""
        companyName = s.companyName ?? s.org ?? ""
        phase = .signedIn
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
