import Foundation

/// Public pages App Review and users can reach from inside the app.
/// Served by the Flask app from site/privacy.html and site/terms.html.
enum LegalLinks {
    static let site = URL(string: "https://www.getwhatnot.com")!
    static let privacy = URL(string: "https://www.getwhatnot.com/privacy")!
    static let terms = URL(string: "https://www.getwhatnot.com/terms")!
    static let requestAccess = URL(string: "https://www.getwhatnot.com/apply")!
    static let supportEmail = "ofir@5secbeauty.com"
}
