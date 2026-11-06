import AVFoundation
import SwiftUI

/// Records the packing video for one order.
///
/// Captures H.264 720p (small enough to upload over warehouse Wi-Fi), writes a
/// QuickTime file, then remuxes it to MP4 without re-encoding so the web dashboard
/// can play it in any browser.
final class PackingRecorder: NSObject, ObservableObject, AVCaptureFileOutputRecordingDelegate {
    enum State: Equatable { case idle, configuring, ready, recording, finishing, failed(String) }

    @MainActor @Published private(set) var state: State = .idle
    @MainActor @Published private(set) var elapsed: TimeInterval = 0

    let session = AVCaptureSession()
    private let output = AVCaptureMovieFileOutput()
    private let queue = DispatchQueue(label: "lohub.recorder")
    private var startedAt: Date?
    private var timer: Timer?
    private var finish: CheckedContinuation<URL, Error>?

    static func requestAccess() async -> Bool {
        let cam = await AVCaptureDevice.requestAccess(for: .video)
        _ = await AVCaptureDevice.requestAccess(for: .audio)   // audio is optional
        return cam
    }

    @MainActor
    func configure() async {
        guard state == .idle || state.isFailed else { return }
        state = .configuring
        guard await Self.requestAccess() else {
            state = .failed("Camera access is off. Turn it on in Settings › LiveOpsHub.")
            return
        }
        let result: String? = await withCheckedContinuation { cont in
            queue.async { cont.resume(returning: self.buildSession()) }
        }
        if let err = result { state = .failed(err) } else { state = .ready }
    }

    /// Runs on `queue`. Returns an error message or nil.
    private func buildSession() -> String? {
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        session.sessionPreset = session.canSetSessionPreset(.hd1280x720) ? .hd1280x720 : .high

        guard let cam = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let vin = try? AVCaptureDeviceInput(device: cam), session.canAddInput(vin)
        else { return "No camera available on this device." }
        session.addInput(vin)

        if AVCaptureDevice.authorizationStatus(for: .audio) == .authorized,
           let mic = AVCaptureDevice.default(for: .audio),
           let ain = try? AVCaptureDeviceInput(device: mic), session.canAddInput(ain) {
            session.addInput(ain)
        }

        guard session.canAddOutput(output) else { return "Can't record video on this device." }
        session.addOutput(output)
        if let conn = output.connection(with: .video) {
            if output.availableVideoCodecTypes.contains(.h264) {
                output.setOutputSettings([AVVideoCodecKey: AVVideoCodecType.h264], for: conn)
            }
            if conn.isVideoRotationAngleSupported(90) { conn.videoRotationAngle = 90 }
        }
        output.maxRecordedDuration = CMTime(seconds: 600, preferredTimescale: 1)   // 10-min safety cap
        session.startRunning()
        return nil
    }

    @MainActor
    func start() {
        guard state == .ready else { return }
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("pack-\(UUID().uuidString).mov")
        state = .recording
        startedAt = Date(); elapsed = 0
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, let s = self.startedAt else { return }
                self.elapsed = Date().timeIntervalSince(s)
            }
        }
        queue.async { self.output.startRecording(to: url, recordingDelegate: self) }
    }

    /// Stops recording and returns an MP4 file plus its duration.
    @MainActor
    func stop() async throws -> (url: URL, duration: TimeInterval) {
        guard state == .recording else { throw APIError.server("Not recording") }
        state = .finishing
        timer?.invalidate(); timer = nil
        let duration = startedAt.map { Date().timeIntervalSince($0) } ?? elapsed
        let mov: URL = try await withCheckedThrowingContinuation { cont in
            finish = cont
            queue.async { self.output.stopRecording() }
        }
        defer { try? FileManager.default.removeItem(at: mov) }
        let mp4 = try await Self.remuxToMP4(mov)
        state = .ready
        return (mp4, duration)
    }

    @MainActor
    func cancel() {
        timer?.invalidate(); timer = nil
        if state == .recording { queue.async { self.output.stopRecording() } }
        state = .ready
    }

    func shutdown() {
        queue.async { if self.session.isRunning { self.session.stopRunning() } }
    }

    // MARK: AVCaptureFileOutputRecordingDelegate

    func fileOutput(_ output: AVCaptureFileOutput, didFinishRecordingTo outputFileURL: URL,
                    from connections: [AVCaptureConnection], error: Error?) {
        // A max-duration stop reports an error but still produces a valid file.
        let ok = error == nil
            || ((error as NSError?)?.userInfo[AVErrorRecordingSuccessfullyFinishedKey] as? Bool ?? false)
        Task { @MainActor in
            guard let cont = self.finish else {
                // Cancelled: discard the file.
                try? FileManager.default.removeItem(at: outputFileURL)
                return
            }
            self.finish = nil
            if ok { cont.resume(returning: outputFileURL) }
            else { cont.resume(throwing: error ?? APIError.server("Recording failed")) }
        }
    }

    // MARK: Remux

    static func remuxToMP4(_ src: URL) async throws -> URL {
        let dst = src.deletingPathExtension().appendingPathExtension("mp4")
        try? FileManager.default.removeItem(at: dst)
        let asset = AVURLAsset(url: src)
        guard let export = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetPassthrough)
        else { throw APIError.server("Couldn't prepare the video") }
        export.outputURL = dst
        export.outputFileType = .mp4
        export.shouldOptimizeForNetworkUse = true          // moov atom first → instant playback
        await export.export()
        guard export.status == .completed else {
            throw APIError.server(export.error?.localizedDescription ?? "Couldn't save the video")
        }
        return dst
    }
}

extension PackingRecorder.State {
    var isFailed: Bool { if case .failed = self { return true }; return false }
}

/// Camera preview for the recorder.
struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession

    func makeUIView(context: Context) -> PreviewView {
        let v = PreviewView()
        v.previewLayer.session = session
        v.previewLayer.videoGravity = .resizeAspectFill
        return v
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {
        if let c = uiView.previewLayer.connection, c.isVideoRotationAngleSupported(90) {
            c.videoRotationAngle = 90          // the app is portrait-only on iPhone
        }
    }

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }
}
