import SwiftUI
import UIKit

/// Receives barcodes from a Bluetooth (or USB) handheld scanner.
///
/// A handheld scanner pairs with the iPhone/iPad as a keyboard: it "types" the barcode
/// and presses Return. To catch that without the packer tapping a text field first,
/// this puts an invisible view in the screen that holds keyboard focus and has no
/// on-screen keyboard. Each completed scan is handed to `onScan`.
///
/// It steps aside for real typing: while a text field is being edited it does not take
/// focus, and it takes focus back once the field is done.
///
/// Usage:  `.background(HardwareScannerCapture { code in … })`
struct HardwareScannerCapture: UIViewRepresentable {
    var isEnabled = true
    var onScan: (String) -> Void

    func makeUIView(context: Context) -> KeyCaptureView {
        let v = KeyCaptureView()
        v.onScan = onScan
        v.isEnabled = isEnabled
        return v
    }

    func updateUIView(_ v: KeyCaptureView, context: Context) {
        v.onScan = onScan
        v.isEnabled = isEnabled
        v.claimFocusIfIdle()
    }

    static func dismantleUIView(_ v: KeyCaptureView, coordinator: ()) {
        v.stop()
    }
}

final class KeyCaptureView: UIView, UIKeyInput {
    var onScan: ((String) -> Void)?
    var isEnabled = true { didSet { if !isEnabled { buffer = "" } } }

    /// A scanner sends a whole barcode in a burst. A pause this long means the previous
    /// characters were not part of this scan (a stray key press), so they are dropped.
    private static let burstGap: TimeInterval = 0.6
    private static let minLength = 4

    private var buffer = ""
    private var lastKey = Date.distantPast
    private var timer: Timer?
    private let noKeyboard = UIView()          // an empty input view = no on-screen keyboard

    override init(frame: CGRect) {
        super.init(frame: frame)
        isUserInteractionEnabled = false       // never intercepts touches
        backgroundColor = .clear
        // No shortcut bar (undo/redo/paste) above the missing keyboard on iPad.
        inputAssistantItem.leadingBarButtonGroups = []
        inputAssistantItem.trailingBarButtonGroups = []
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }

    // MARK: First responder

    override var canBecomeFirstResponder: Bool { isEnabled && window != nil }
    override var inputView: UIView? { noKeyboard }
    override var inputAccessoryView: UIView? { nil }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        if window == nil { stop(); return }
        claimFocusIfIdle()
        // Focus is lost whenever a text field finishes or a sheet closes; take it back.
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.7, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.claimFocusIfIdle() }
        }
    }

    func stop() {
        timer?.invalidate(); timer = nil
        buffer = ""
        if isFirstResponder { resignFirstResponder() }
    }

    /// Take keyboard focus unless someone is typing in a real text field.
    func claimFocusIfIdle() {
        guard isEnabled, window != nil, !isFirstResponder else { return }
        if let current = UIResponder.currentFirstResponder, current is UITextInput { return }
        becomeFirstResponder()
    }

    // MARK: UITextInputTraits — plain characters only, exactly as the scanner sends them

    var autocorrectionType: UITextAutocorrectionType = .no
    var autocapitalizationType: UITextAutocapitalizationType = .none
    var spellCheckingType: UITextSpellCheckingType = .no
    var smartQuotesType: UITextSmartQuotesType = .no
    var smartDashesType: UITextSmartDashesType = .no
    var smartInsertDeleteType: UITextSmartInsertDeleteType = .no
    var keyboardType: UIKeyboardType = .asciiCapable

    // MARK: UIKeyInput

    var hasText: Bool { !buffer.isEmpty }

    func insertText(_ text: String) {
        guard isEnabled else { return }
        let now = Date()
        if now.timeIntervalSince(lastKey) > Self.burstGap { buffer = "" }
        lastKey = now
        for ch in text {
            if ch.isNewline || ch == "\t" { flush() } else { buffer.append(ch) }
        }
    }

    func deleteBackward() {
        if !buffer.isEmpty { buffer.removeLast() }
    }

    private func flush() {
        let code = buffer.trimmingCharacters(in: .whitespacesAndNewlines)
        buffer = ""
        guard code.count >= Self.minLength else { return }
        onScan?(code)
    }
}

extension UIResponder {
    private static weak var found: UIResponder?

    /// The view currently holding keyboard focus, if any.
    static var currentFirstResponder: UIResponder? {
        found = nil
        UIApplication.shared.sendAction(#selector(reportAsFirstResponder), to: nil, from: nil, for: nil)
        return found
    }

    @objc private func reportAsFirstResponder() {
        UIResponder.found = self
    }
}
