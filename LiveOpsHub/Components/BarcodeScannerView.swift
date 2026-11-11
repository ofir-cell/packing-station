import SwiftUI
import VisionKit

/// Live barcode scanner (shipping labels and product barcodes) built on VisionKit.
/// Calls `onScan` once per distinct code; the same code is ignored for 2 seconds so a
/// label held in front of the camera doesn't fire repeatedly.
struct BarcodeScannerView: UIViewControllerRepresentable {
    var onScan: (String) -> Void

    @MainActor static var isAvailable: Bool {
        DataScannerViewController.isSupported && DataScannerViewController.isAvailable
    }

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let vc = DataScannerViewController(
            recognizedDataTypes: [.barcode()],
            qualityLevel: .accurate,
            recognizesMultipleItems: false,
            isHighFrameRateTrackingEnabled: false,
            isPinchToZoomEnabled: true,
            isGuidanceEnabled: true,
            isHighlightingEnabled: true)
        vc.delegate = context.coordinator
        return vc
    }

    func updateUIViewController(_ vc: DataScannerViewController, context: Context) {
        context.coordinator.onScan = onScan
        if !vc.isScanning { try? vc.startScanning() }
    }

    static func dismantleUIViewController(_ vc: DataScannerViewController, coordinator: Coordinator) {
        vc.stopScanning()
    }

    func makeCoordinator() -> Coordinator { Coordinator(onScan: onScan) }

    @MainActor
    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        var onScan: (String) -> Void
        private var last: (code: String, at: Date)?

        init(onScan: @escaping (String) -> Void) { self.onScan = onScan }

        func dataScanner(_ dataScanner: DataScannerViewController,
                         didAdd addedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            for item in addedItems {
                guard case .barcode(let b) = item, let raw = b.payloadStringValue else { continue }
                let code = raw.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !code.isEmpty else { continue }
                if let l = last, l.code == code, Date().timeIntervalSince(l.at) < 2 { continue }
                last = (code, Date())
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                onScan(code)
            }
        }
    }
}

/// Fallback when the camera scanner isn't available (older device, simulator,
/// camera permission denied) or for a Bluetooth/USB handheld scanner that types.
struct ManualCodeEntry: View {
    var placeholder = "Tracking number"
    var onSubmit: (String) -> Void
    @State private var code = ""

    var body: some View {
        HStack {
            TextField(placeholder, text: $code)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .submitLabel(.go)
                .onSubmit(send)
                .textFieldStyle(.roundedBorder)
            Button("Go", action: send).buttonStyle(.borderedProminent).disabled(code.isEmpty)
        }
    }

    private func send() {
        let c = code.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !c.isEmpty else { return }
        onSubmit(c); code = ""
    }
}
