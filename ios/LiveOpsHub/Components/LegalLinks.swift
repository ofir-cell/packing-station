import Foundation

/// Public pages App Review and users can reach from inside the app.
/// The marketing site (site/ in this repo) serves privacy.html and terms.html.
enum LegalLinks {
    static let site = URL(string: "https://getwhatnot.com")!
    static let privacy = URL(string: "https://getwhatnot.com/privacy")!
    static let terms = URL(string: "https://getwhatnot.com/terms")!
    static let requestAccess = URL(string: "https://getwhatnot.com/apply")!
    static let supportEmail = "support@getwhatnot.com"
}
