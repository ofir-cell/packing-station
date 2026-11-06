import Foundation

/// Errors the UI knows how to present.
enum APIError: LocalizedError, Equatable {
    case notSignedIn
    case forbidden
    case billing(String)
    case server(String)
    case transport(String)
    case decoding(String)

    var errorDescription: String? {
        switch self {
        case .notSignedIn: return "Your session has ended. Please sign in again."
        case .forbidden: return "Your role doesn't have access to this."
        case .billing(let m): return m
        case .server(let m): return m
        case .transport(let m): return m
        case .decoding: return "Unexpected response from the server."
        }
    }
}

/// Talks to the LiveOpsHub Flask backend.
///
/// Auth is the same signed session cookie the web app uses, kept in the shared
/// `HTTPCookieStorage`. Every mutating request echoes the CSRF token (from
/// `/api/mobile/session`) in `X-CSRF-Token`. `X-Client` tells the server to answer
/// auth failures with JSON 401/403 instead of an HTML redirect.
final class APIClient: @unchecked Sendable {
    static let shared = APIClient()

    let baseURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()
    private var csrfToken: String?
    private let lock = NSLock()

    static var appVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0.0"
    }

    init() {
        let raw = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String ?? "https://www.getwhatnot.com"
        baseURL = URL(string: raw)!
        let cfg = URLSessionConfiguration.default
        cfg.httpCookieStorage = .shared
        cfg.httpCookieAcceptPolicy = .always
        cfg.httpShouldSetCookies = true
        cfg.timeoutIntervalForRequest = 30
        cfg.timeoutIntervalForResource = 300      // video uploads on warehouse Wi-Fi
        cfg.waitsForConnectivity = true
        session = URLSession(configuration: cfg)
    }

    // MARK: - Session

    @discardableResult
    func fetchSession() async throws -> SessionInfo {
        let info: SessionInfo = try await send("GET", "/api/mobile/session")
        setToken(info.csrfToken)
        return info
    }

    private func setToken(_ t: String?) { lock.lock(); csrfToken = t; lock.unlock() }
    private func token() -> String? { lock.lock(); defer { lock.unlock() }; return csrfToken }

    func clearCookies() {
        let storage = HTTPCookieStorage.shared
        for c in storage.cookies(for: baseURL) ?? [] { storage.deleteCookie(c) }
        setToken(nil)
    }

    /// Cookies for the backend host, used to sign the in-app web view in.
    func cookies() -> [HTTPCookie] { HTTPCookieStorage.shared.cookies(for: baseURL) ?? [] }

    // MARK: - JSON requests

    func get<T: Decodable>(_ path: String, query: [String: String] = [:]) async throws -> T {
        try await send("GET", path, query: query)
    }

    func post<T: Decodable>(_ path: String, body: [String: Any] = [:]) async throws -> T {
        try await send("POST", path, body: body)
    }

    private func makeRequest(_ method: String, _ path: String, query: [String: String]) -> URLRequest {
        var comps = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { comps.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) } }
        var req = URLRequest(url: comps.url!)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.setValue("lohub-ios/\(Self.appVersion)", forHTTPHeaderField: "X-Client")
        if method != "GET", let t = token() { req.setValue(t, forHTTPHeaderField: "X-CSRF-Token") }
        return req
    }

    private func send<T: Decodable>(_ method: String, _ path: String,
                                    query: [String: String] = [:],
                                    body: [String: Any]? = nil,
                                    retried: Bool = false) async throws -> T {
        if method != "GET", token() == nil { try await fetchSession() }
        var req = makeRequest(method, path, query: query)
        if let body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, resp) = try await perform(req)
        if let err = classify(resp, data) {
            // A stale CSRF token (cookie rotated) → refresh once and retry.
            if case .server(let m) = err, m.contains("CSRF"), !retried {
                try await fetchSession()
                return try await send(method, path, query: query, body: body, retried: true)
            }
            throw err
        }
        do { return try decoder.decode(T.self, from: data) }
        catch { throw APIError.decoding(String(describing: error)) }
    }

    private func perform(_ req: URLRequest) async throws -> (Data, HTTPURLResponse) {
        do {
            let (data, resp) = try await session.data(for: req)
            guard let http = resp as? HTTPURLResponse else { throw APIError.transport("No response") }
            return (data, http)
        } catch let e as APIError {
            throw e
        } catch {
            throw APIError.transport(error.localizedDescription)
        }
    }

    private func classify(_ resp: HTTPURLResponse, _ data: Data) -> APIError? {
        let msg = (try? decoder.decode(ErrorBody.self, from: data))
        switch resp.statusCode {
        case 200..<300, 409: return nil            // 409 carries a structured body (e.g. need_org_confirm)
        case 401: return .notSignedIn
        case 402: return .billing(msg?.message ?? "Your subscription is not active.")
        case 403: return msg?.error == "forbidden" || msg == nil ? .forbidden : .server(msg?.error ?? "Forbidden")
        case 429: return .server(msg?.error ?? "Too many attempts. Try again shortly.")
        default:  return .server(msg?.error ?? "Server error (\(resp.statusCode))")
        }
    }

    // MARK: - Packing video upload

    /// Uploads a packing video for one tracking number. Same endpoint the web
    /// station uses; the server detects MP4 and stores it as video/mp4.
    func uploadPackingVideo(tracking: String, duration: TimeInterval, videoURL: URL) async throws -> UploadResult {
        if token() == nil { try await fetchSession() }
        let boundary = "lohub-\(UUID().uuidString)"
        var req = makeRequest("POST", "/api/upload", query: [:])
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let bodyFile = FileManager.default.temporaryDirectory.appendingPathComponent("\(boundary).body")
        try Self.writeMultipart(to: bodyFile, boundary: boundary,
                                fields: ["tracking": tracking,
                                         "station": "IOS",
                                         "duration": String(format: "%.2f", duration)],
                                fileField: "video", fileName: "\(tracking).mp4",
                                mime: "video/mp4", fileURL: videoURL)
        defer { try? FileManager.default.removeItem(at: bodyFile) }

        let (data, resp): (Data, URLResponse)
        do { (data, resp) = try await session.upload(for: req, fromFile: bodyFile) }
        catch { throw APIError.transport(error.localizedDescription) }
        guard let http = resp as? HTTPURLResponse else { throw APIError.transport("No response") }
        if let err = classify(http, data) { throw err }
        let r = try decoder.decode(UploadResult.self, from: data)
        if !r.ok { throw APIError.server(r.error ?? "Upload failed") }
        return r
    }

    /// Streams the multipart body to disk so a 50 MB video never sits in memory twice.
    private static func writeMultipart(to url: URL, boundary: String, fields: [String: String],
                                       fileField: String, fileName: String, mime: String,
                                       fileURL: URL) throws {
        FileManager.default.createFile(atPath: url.path, contents: nil)
        let out = try FileHandle(forWritingTo: url)
        defer { try? out.close() }
        func w(_ s: String) { out.write(Data(s.utf8)) }
        for (k, v) in fields {
            w("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(k)\"\r\n\r\n\(v)\r\n")
        }
        w("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(fileField)\"; filename=\"\(fileName)\"\r\nContent-Type: \(mime)\r\n\r\n")
        let input = try FileHandle(forReadingFrom: fileURL)
        defer { try? input.close() }
        while let chunk = try input.read(upToCount: 1 << 20), !chunk.isEmpty { out.write(chunk) }
        w("\r\n--\(boundary)--\r\n")
    }
}

private struct ErrorBody: Decodable, Equatable {
    let error: String?
    let message: String?
}
