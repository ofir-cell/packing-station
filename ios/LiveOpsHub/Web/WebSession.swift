import Foundation
import WebKit

/// One shared web session for the whole app.
///
/// The dashboard runs in a WKWebView, so the login (password, badge, 2FA) happens on
/// the real site and the session cookie lives in WebKit's cookie store. The native
/// Pack tab talks to the same server through URLSession, so before any native call we
/// copy WebKit's cookies for our host into `HTTPCookieStorage.shared`.
@MainActor
final class WebSession {
    static let shared = WebSession()

    let dataStore = WKWebsiteDataStore.default()
    let processPool = WKProcessPool()
    var baseURL: URL { APIClient.shared.baseURL }

    /// Copy the dashboard's cookies into URLSession's store (WebKit → native).
    func syncCookiesToNative() async {
        let all = await dataStore.httpCookieStore.allCookies()
        let host = baseURL.host ?? ""
        let storage = HTTPCookieStorage.shared
        for c in storage.cookies ?? [] where host.hasSuffix(c.domain.trimmingCharacters(in: CharacterSet(charactersIn: "."))) {
            storage.deleteCookie(c)
        }
        for c in all where host.hasSuffix(c.domain.trimmingCharacters(in: CharacterSet(charactersIn: "."))) {
            storage.setCookie(c)
        }
    }

    /// True when the web session is signed in (checked against the server).
    func isSignedIn() async -> Bool {
        await syncCookiesToNative()
        return (try? await APIClient.shared.fetchSession().signedIn) ?? false
    }
}
