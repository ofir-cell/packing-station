import AVFoundation
import SwiftUI

/// Records the packing video for one order.
///
/// Captures H.264 720p (small enough to upload over warehouse Wi-Fi), writes a
/// QuickTime file, then remuxes it to MP4 without re-encoding so the web dashboard
/// can play it in any browser.
// @unchecked Sendable: every AVCaptureSession/output call is serialized on `queue`,
// and all UI state (@Published) is @MainActor-isolated.
final class PackingRecorder: NSObject, ObservableObject, AVCaptureFileOutputRecordingDelegate, @unchecked Sendable {
    enum State: Equatable { case idle, configuring, ready, recording, finishing, failed(String) }

    @MainActor @Published private(set) var state: State = .idle
    @MainActor @Published private(set) var elapsed: TimeInterval = 0
    /// The camera in use, once configured. The preview needs it to stay upright on iPad.
    @MainActor @Published private(set) var camera: AVCaptureDevice?

    let session = AVCaptureSession()
    private let output = AVCaptureMovieFileOutput()
    private let queue = DispatchQueue(label: "lohub.recorder")
    private var startedAt: Date?
    private var timer: Timer?
    private var finish: CheckedContinuation<URL, Error>?
    /// Tells us how the device is being held, so the saved video is upright in any
    /// orientation (an iPad on a stand is usually landscape). Used on `queue` only.
    private var rotation: AVCaptureDevice.RotationCoordinator?
    private var builtCamera: AVCaptureDevice?

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
        if let err = result { state = .failed(err) } else { camera = builtCamera; state = .ready }
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
        builtCamera = cam
        rotation = AVCaptureDevice.RotationCoordinator(device: cam, previewLayer: nil)

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
        }
        applyCaptureRotation()
        output.maxRecordedDuration = CMTime(seconds: 600, preferredTimescale: 1)   // 10-min safety cap
        session.startRunning()
        return nil
    }

    /// Runs on `queue`. Rotates the recording to match how the device is held right now.
    /// The angle is fixed when a recording starts, so this is called just before each one.
    private func applyCaptureRotation() {
        guard let conn = output.connection(with: .video) else { return }
        let angle = rotation?.videoRotationAngleForHorizonLevelCapture ?? 90
        if conn.isVideoRotationAngleSupported(angle) { conn.videoRotationAngle = angle }
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
        queue.async {
            self.applyCaptureRotation()
            self.output.startRecording(to: url, recordingDelegate: self)
        }
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

/// Camera preview for the recorder. Stays upright in every orientation (iPhone
/// portrait, iPad portrait or landscape).
struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    /// The recorder's camera, once it is configured.
    var camera: AVCaptureDevice?

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> PreviewView {
        let v = PreviewView()
        v.previewLayer.session = session
        v.previewLayer.videoGravity = .resizeAspectFill
        return v
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {
        context.coordinator.follow(camera, layer: uiView.previewLayer)
    }

    static func dismantleUIView(_ uiView: PreviewView, coordinator: Coordinator) {
        coordinator.stop()
    }

    /// Keeps the preview's rotation in step with the device orientation.
    @MainActor
    final class Coordinator {
        private var rotation: AVCaptureDevice.RotationCoordinator?
        private var observation: NSKeyValueObservation?
        private weak var device: AVCaptureDevice?

        func follow(_ camera: AVCaptureDevice?, layer: AVCaptureVideoPreviewLayer) {
            guard let camera else { apply(90, to: layer); return }     // not configured yet
            if device !== camera {
                stop()
                device = camera
                let rc = AVCaptureDevice.RotationCoordinator(device: camera, previewLayer: layer)
                rotation = rc
                observation = rc.observe(\.videoRotationAngleForHorizonLevelPreview, options: [.new]) { [weak self, weak layer] rc, _ in
                    let angle = rc.videoRotationAngleForHorizonLevelPreview
                    Task { @MainActor in
                        guard let self, let layer else { return }
                        self.apply(angle, to: layer)
                    }
                }
            }
            if let rc = rotation { apply(rc.videoRotationAngleForHorizonLevelPreview, to: layer) }
        }

        func stop() {
            observation?.invalidate(); observation = nil
            rotation = nil; device = nil
        }

        private func apply(_ angle: CGFloat, to layer: AVCaptureVideoPreviewLayer) {
            guard let c = layer.connection, c.isVideoRotationAngleSupported(angle) else { return }
            if c.videoRotationAngle != angle { c.videoRotationAngle = angle }
        }
    }

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }
}
