import SwiftUI
import WebKit

/// Opens a page of the LiveOpsHub web app, already signed in with the app's session.
/// Used for flows that live on the web side, such as authorizing a TikTok shop
/// (TikTok's OAuth page → /api/tiktok/callback → back to /admin/tiktok).
struct AuthenticatedWebView: UIViewRepresentable {
    let path: String

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .default()
        let web = WKWebView(frame: .zero, configuration: cfg)
        web.allowsBackForwardNavigationGestures = true
        web.navigationDelegate = context.coordinator

        let url = APIClient.shared.baseURL.appendingPathComponent(path)
        let store = cfg.websiteDataStore.httpCookieStore
        let cookies = APIClient.shared.cookies()
        let group = DispatchGroup()
        for c in cookies {
            group.enter()
            store.setCookie(c) { group.leave() }
        }
        group.notify(queue: .main) { web.load(URLRequest(url: url)) }
        return web
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, WKNavigationDelegate {
        /// Keep the user on our host and TikTok's auth pages; anything else opens in Safari.
        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let host = action.request.url?.host?.lowercased() else { decisionHandler(.allow); return }
            let ours = APIClient.shared.baseURL.host?.lowercased() ?? ""
            let allowed = host == ours || host.hasSuffix("getwhatnot.com")
                || host.hasSuffix("tiktok.com") || host.hasSuffix("tiktokshop.com")
                || host.hasSuffix("tiktokv.com") || host.hasSuffix("tiktokcdn.com")
                || host.hasSuffix("ttwstatic.com") || host.hasSuffix("byteoversea.com")
            if allowed || action.targetFrame?.isMainFrame == false {
                decisionHandler(.allow)
            } else {
                if let u = action.request.url { UIApplication.shared.open(u) }
                decisionHandler(.cancel)
            }
        }
    }
}
