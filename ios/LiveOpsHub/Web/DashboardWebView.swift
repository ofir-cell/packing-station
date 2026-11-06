import SwiftUI
import WebKit
import QuickLook

/// Controls the dashboard web view from SwiftUI (reload, go home, run JS).
@MainActor
final class DashboardController: ObservableObject {
    weak var webView: WKWebView?
    @Published var isLoading = false
    @Published var progress: Double = 0
    @Published var loadError: String?
    @Published var downloadedFile: URL?

    func reload() { webView?.reload() }
    func goHome() { load(path: "/home") }
    func load(path: String) {
        let url = APIClient.shared.baseURL.appendingPathComponent(path)
        webView?.load(URLRequest(url: url))
    }
    func evaluate(_ js: String) { webView?.evaluateJavaScript(js) }
}

/// The real LiveOpsHub dashboard, full screen. Everything a bare WKWebView silently
/// breaks is handled here: JS alert/confirm/prompt, target=_blank / window.open,
/// file downloads (CSV/PDF exports), camera/mic permission for in-page capture,
/// external links (open in Safari), pull-to-refresh and offline errors.
struct DashboardWebView: UIViewRepresentable {
    @ObservedObject var controller: DashboardController
    var startPath = "/"
    var onNativeMessage: (NativeBridge.Message, WKWebView) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = WebSession.shared.dataStore
        cfg.processPool = WebSession.shared.processPool
        cfg.allowsInlineMediaPlayback = true
        cfg.mediaTypesRequiringUserActionForPlayback = []
        cfg.applicationNameForUserAgent = "LiveOpsHubiOS/\(APIClient.appVersion) Mobile"
        let ucc = WKUserContentController()
        ucc.add(context.coordinator, name: NativeBridge.handlerName)
        ucc.addUserScript(WKUserScript(source: NativeBridge.injectedJS,
                                       injectionTime: .atDocumentStart, forMainFrameOnly: true))
        cfg.userContentController = ucc

        let web = WKWebView(frame: .zero, configuration: cfg)
        web.navigationDelegate = context.coordinator
        web.uiDelegate = context.coordinator
        web.allowsBackForwardNavigationGestures = true
        web.scrollView.contentInsetAdjustmentBehavior = .automatic
        #if DEBUG
        if #available(iOS 16.4, *) { web.isInspectable = true }   // Safari › Develop for debugging
        #endif

        let refresh = UIRefreshControl()
        refresh.addTarget(context.coordinator, action: #selector(Coordinator.pullToRefresh(_:)), for: .valueChanged)
        web.scrollView.refreshControl = refresh

        context.coordinator.progressObs = web.observe(\.estimatedProgress) { w, _ in
            Task { @MainActor in controller.progress = w.estimatedProgress }
        }
        controller.webView = web
        web.load(URLRequest(url: APIClient.shared.baseURL.appendingPathComponent(startPath)))
        return web
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    // MARK: - Coordinator

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, WKDownloadDelegate {
        let parent: DashboardWebView
        var progressObs: NSKeyValueObservation?
        private var downloadDest: URL?

        init(_ p: DashboardWebView) { parent = p }

        @objc func pullToRefresh(_ rc: UIRefreshControl) {
            parent.controller.reload()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) { rc.endRefreshing() }
        }

        private var host: String { APIClient.shared.baseURL.host?.lowercased() ?? "" }

        private func isOurs(_ url: URL?) -> Bool {
            guard let h = url?.host?.lowercased() else { return true }      // about:, data:, blob:
            return h == host || h.hasSuffix("getwhatnot.com")
        }

        /// TikTok's shop-authorization pages must stay in-app so the OAuth callback
        /// lands back in this session.
        private func isAuthFlow(_ url: URL?) -> Bool {
            guard let h = url?.host?.lowercased() else { return false }
            return ["tiktok.com", "tiktokshop.com", "tiktokv.com", "tiktokcdn.com",
                    "ttwstatic.com", "byteoversea.com", "ibytedtos.com"].contains { h.hasSuffix($0) }
        }

        // MARK: Navigation

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void) {
            guard let url = action.request.url else { decisionHandler(.allow); return }
            let scheme = url.scheme?.lowercased() ?? ""
            if ["tel", "mailto", "sms", "itms-apps", "maps"].contains(scheme) {
                UIApplication.shared.open(url); decisionHandler(.cancel); return
            }
            if action.shouldPerformDownload { decisionHandler(.download); return }
            if action.targetFrame?.isMainFrame == false || isOurs(url) || isAuthFlow(url) {
                decisionHandler(.allow); return
            }
            // Anything else (tracking pages, help docs, TikTok Seller Center...) → Safari.
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
        }

        func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
                     decisionHandler: @escaping @MainActor (WKNavigationResponsePolicy) -> Void) {
            if let http = response.response as? HTTPURLResponse {
                let cd = (http.value(forHTTPHeaderField: "Content-Disposition") ?? "").lowercased()
                if cd.contains("attachment") || !response.canShowMIMEType {
                    decisionHandler(.download); return
                }
            }
            decisionHandler(.allow)
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.controller.isLoading = true
            parent.controller.loadError = nil
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.controller.isLoading = false
            webView.scrollView.refreshControl?.endRefreshing()
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            fail(error)
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            fail(error)
        }

        private func fail(_ error: Error) {
            parent.controller.isLoading = false
            let ns = error as NSError
            // -999 = a navigation replaced by another one; 102 = handed off to a download.
            if ns.code == NSURLErrorCancelled || (ns.domain == "WebKitErrorDomain" && ns.code == 102) { return }
            parent.controller.loadError = error.localizedDescription
        }

        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }

        // MARK: target=_blank / window.open

        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            guard let url = action.request.url else { return nil }
            if isOurs(url) || isAuthFlow(url) { webView.load(action.request) }
            else { UIApplication.shared.open(url) }
            return nil
        }

        // MARK: JS dialogs (the site uses alert/confirm/prompt in ~110 places)

        private func present(_ alert: UIAlertController) {
            guard let root = UIApplication.shared.connectedScenes
                    .compactMap({ ($0 as? UIWindowScene)?.keyWindow?.rootViewController }).first else { return }
            var top = root
            while let p = top.presentedViewController { top = p }
            top.present(alert, animated: true)
        }

        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor () -> Void) {
            let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            present(a)
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor (Bool) -> Void) {
            let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) })
            a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
            present(a)
        }

        func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String,
                     defaultText: String?, initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping @MainActor (String?) -> Void) {
            let a = UIAlertController(title: nil, message: prompt, preferredStyle: .alert)
            a.addTextField { $0.text = defaultText }
            a.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(nil) })
            a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(a.textFields?.first?.text) })
            present(a)
        }

        // MARK: Camera / mic for in-page capture (getUserMedia) on our own pages only

        func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                     initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType,
                     decisionHandler: @escaping @MainActor (WKPermissionDecision) -> Void) {
            let h = origin.host.lowercased()
            decisionHandler(h == host || h.hasSuffix("getwhatnot.com") ? .grant : .prompt)
        }

        // MARK: Downloads (CSV / PDF exports, packing videos)

        func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
            download.delegate = self
        }

        func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
            download.delegate = self
        }

        func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                      suggestedFilename: String, completionHandler: @escaping @MainActor (URL?) -> Void) {
            let dir = FileManager.default.temporaryDirectory.appendingPathComponent("downloads", isDirectory: true)
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let dest = dir.appendingPathComponent(suggestedFilename)
            try? FileManager.default.removeItem(at: dest)
            downloadDest = dest
            completionHandler(dest)
        }

        func downloadDidFinish(_ download: WKDownload) {
            if let d = downloadDest { parent.controller.downloadedFile = d }
        }

        func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
            parent.controller.loadError = "Download failed: \(error.localizedDescription)"
        }

        // MARK: Native bridge

        func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == NativeBridge.handlerName,
                  isOurs(message.frameInfo.request.url),
                  let m = NativeBridge.Message(message.body),
                  let web = message.webView else { return }
            parent.onNativeMessage(m, web)
        }
    }
}

/// Share sheet for a finished download (Save to Files, AirDrop, Mail…).
struct ShareSheet: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}
