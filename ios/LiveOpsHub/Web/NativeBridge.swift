import Foundation
import WebKit

/// JS ↔ native bridge, available on every LiveOpsHub page inside the iOS app.
///
/// From the web app:
///   if (window.LOHubNative) {
///     const code = await LOHubNative.scan();        // opens the native camera scanner, resolves the barcode (or null)
///     LOHubNative.pack('9400111…');                 // opens native Pack for that label (scan → record → upload)
///     LOHubNative.haptic('success');                // success | warning | error | tap
///   }
///   LOHubNative.isApp === true, LOHubNative.version === '1.0.0'
///
/// The page can also just check `navigator.userAgent.includes('LiveOpsHubiOS')`.
enum NativeBridge {
    static let handlerName = "lohub"

    enum Message {
        case scan(id: String)
        case pack(tracking: String?)
        case haptic(String)

        init?(_ body: Any) {
            guard let d = body as? [String: Any], let action = d["action"] as? String else { return nil }
            switch action {
            case "scan": self = .scan(id: d["id"] as? String ?? "")
            case "pack": self = .pack(tracking: d["tracking"] as? String)
            case "haptic": self = .haptic(d["style"] as? String ?? "tap")
            default: return nil
            }
        }
    }

    static var injectedJS: String {
        """
        (function(){
          if (window.LOHubNative) return;
          var pending = {}, seq = 0;
          function post(m){ window.webkit.messageHandlers.\(handlerName).postMessage(m); }
          window.LOHubNative = {
            isApp: true,
            version: '\(APIClient.appVersion)',
            scan: function(){ return new Promise(function(res){ var id = 's' + (++seq); pending[id] = res; post({action:'scan', id:id}); }); },
            pack: function(tracking){ post({action:'pack', tracking: tracking || null}); },
            haptic: function(style){ post({action:'haptic', style: style || 'tap'}); },
            _resolve: function(id, value){ var f = pending[id]; delete pending[id]; if (f) f(value); }
          };
          document.documentElement.classList.add('lohub-ios');
        })();
        """
    }

    /// JS that resolves a pending `scan()` promise with a code (or null).
    static func resolveScanJS(id: String, code: String?) -> String {
        let value: String
        if let code, let data = try? JSONSerialization.data(withJSONObject: [code]),
           let arr = String(data: data, encoding: .utf8) {
            value = String(arr.dropFirst().dropLast())          // JSON string literal, safely escaped
        } else {
            value = "null"
        }
        let safeID = id.filter { $0.isLetter || $0.isNumber }
        return "window.LOHubNative && LOHubNative._resolve('\(safeID)', \(value));"
    }
}
