import SwiftUI

/// Scan a label → see what goes in the box → record → upload. Then the next label.
/// Same flow as the web packing station, with the phone camera doing both jobs.
struct PackFlowView: View {
    /// Set when the dashboard asks to pack a specific label (LOHubNative.pack(code)).
    var initialTracking: String? = nil
    @StateObject private var recorder = PackingRecorder()

    enum Step: Equatable {
        case scan
        case loading(String)
        case order(ShipmentLookupBox)
        case uploading(ShipmentLookupBox)
        case done(String)
    }

    @State private var step: Step = .scan
    @State private var error: String?
    @AppStorage("pack.autoRecord") private var autoRecord = true

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                switch step {
                case .scan, .loading:
                    scanStage
                case .order(let box), .uploading(let box):
                    orderStage(box)
                case .done(let trk):
                    doneStage(trk)
                }
            }
            .navigationTitle("Pack")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Toggle(isOn: $autoRecord) { Image(systemName: "record.circle") }
                        .toggleStyle(.button)
                        .accessibilityLabel("Start recording automatically after a scan")
                }
            }
            .alert("Couldn't continue", isPresented: .constant(error != nil)) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
        }
        .task {
            if let t = initialTracking, !t.isEmpty, case .scan = step {
                await WebSession.shared.syncCookiesToNative()
                await lookup(t)
            }
        }
        .onDisappear {
            if recorder.state == .recording { recorder.cancel() }
            recorder.shutdown()
        }
    }

    // MARK: Stage 1 — scan the label

    private var scanStage: some View {
        VStack(spacing: 16) {
            ZStack {
                if BarcodeScannerView.isAvailable {
                    BarcodeScannerView { code in Task { await lookup(code) } }
                } else {
                    ContentUnavailableView("Camera scanner unavailable",
                                           systemImage: "barcode.viewfinder",
                                           description: Text("Type the tracking number or use a handheld scanner."))
                }
                if case .loading(let code) = step {
                    VStack(spacing: 8) {
                        ProgressView()
                        Text(code).font(.caption.monospaced())
                    }
                    .padding().background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
                }
            }
            .frame(maxHeight: .infinity)
            .clipShape(RoundedRectangle(cornerRadius: 16))

            Text("Scan the shipping label").font(.headline)
            ManualCodeEntry { code in Task { await lookup(code) } }
        }
        .padding()
    }

    // MARK: Stage 2 — contents + recording

    private func orderStage(_ box: ShipmentLookupBox) -> some View {
        let order = box.value
        return VStack(spacing: 12) {
            ZStack(alignment: .topLeading) {
                CameraPreview(session: recorder.session)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                if recorder.state == .recording {
                    Label(timeString(recorder.elapsed), systemImage: "record.circle.fill")
                        .font(.headline.monospacedDigit())
                        .padding(8)
                        .background(.red, in: Capsule())
                        .foregroundStyle(.white)
                        .padding(10)
                }
                if case .failed(let msg) = recorder.state {
                    Text(msg).padding().background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12)).padding()
                }
            }
            .frame(maxHeight: .infinity)

            OrderContentsCard(order: order)

            if case .uploading = step {
                HStack { ProgressView(); Text("Saving packing video…") }
                    .frame(maxWidth: .infinity, minHeight: 54)
            } else if recorder.state == .recording {
                Button { Task { await stopAndUpload(box) } } label: {
                    Label("Stop & save", systemImage: "stop.circle.fill").frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.borderedProminent).tint(.red)
            } else {
                HStack {
                    Button("Cancel") { reset() }.buttonStyle(.bordered)
                    Button { recorder.start() } label: {
                        Label("Record", systemImage: "record.circle").frame(maxWidth: .infinity, minHeight: 44)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(recorder.state != .ready)
                }
            }
        }
        .padding()
        .task(id: order.shipment?.shipmentId) {
            await recorder.configure()
            if autoRecord, recorder.state == .ready { recorder.start() }
        }
    }

    // MARK: Stage 3 — done

    private func doneStage(_ trk: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "checkmark.seal.fill").font(.system(size: 72)).foregroundStyle(.green)
            Text("Packed").font(.title.bold())
            Text(trk).font(.callout.monospaced()).foregroundStyle(.secondary)
            Spacer()
            Button { reset() } label: {
                Label("Scan next label", systemImage: "barcode.viewfinder").frame(maxWidth: .infinity, minHeight: 44)
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
        .task {
            try? await Task.sleep(for: .seconds(1.5))
            if case .done = step { reset() }          // keep the line moving
        }
    }

    // MARK: Actions

    private func lookup(_ raw: String) async {
        guard case .scan = step else { return }
        step = .loading(raw)
        do {
            let path = "/api/shipment/" + Self.sanitize(raw)
            let r: ShipmentLookup = try await APIClient.shared.get(path)
            guard r.ok, r.shipment != nil else { throw APIError.server(r.error ?? "Shipment not found") }
            if let st = r.shipment?.status?.lowercased(), st == "cancelled" {
                throw APIError.server("This order is cancelled — don't ship it.")
            }
            step = .order(ShipmentLookupBox(r))
        } catch {
            self.error = Self.message(for: error)
            step = .scan
        }
    }

    private func stopAndUpload(_ box: ShipmentLookupBox) async {
        guard let trk = box.value.shipment?.trackingCode ?? box.value.shipment?.shipmentId else { return }
        step = .uploading(box)
        do {
            let (file, duration) = try await recorder.stop()
            defer { try? FileManager.default.removeItem(at: file) }
            _ = try await APIClient.shared.uploadPackingVideo(tracking: trk, duration: duration, videoURL: file)
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            step = .done(trk)
        } catch {
            self.error = Self.message(for: error)
            step = .order(box)
        }
    }

    /// A lost session means the dashboard tab needs a sign-in; say so plainly.
    static func message(for error: Error) -> String {
        if let e = error as? APIError, e == .notSignedIn {
            return "You're signed out. Open the Dashboard tab and sign in, then come back to Pack."
        }
        return (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
    }

    private func reset() {
        if recorder.state == .recording { recorder.cancel() }
        step = .scan
    }

    /// The server only accepts [A-Za-z0-9_-]; strip anything a scanner adds (spaces, GS1 separators).
    static func sanitize(_ raw: String) -> String {
        String(raw.unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) && $0.isASCII || $0 == "-" || $0 == "_" })
    }

    private func timeString(_ t: TimeInterval) -> String {
        String(format: "%d:%02d", Int(t) / 60, Int(t) % 60)
    }
}

/// `ShipmentLookup` isn't Equatable; box it so it can ride in the Step enum.
struct ShipmentLookupBox: Equatable {
    let id = UUID()
    let value: ShipmentLookup
    init(_ v: ShipmentLookup) { value = v }
    static func == (a: Self, b: Self) -> Bool { a.id == b.id }
}

struct OrderContentsCard: View {
    let order: ShipmentLookup

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(order.shipment?.displayBuyer ?? "").font(.headline)
                Spacer()
                if order.isGiveaway == true { Label("Giveaway", systemImage: "gift").font(.caption.bold()) }
                if let n = order.combinedFrom?.count, n > 0 {
                    Text("Combined ×\(n + 1)").font(.caption.bold()).foregroundStyle(.orange)
                }
            }
            if let show = order.shipment?.importLabel, !show.isEmpty {
                Text(show).font(.caption).foregroundStyle(.secondary)
            }
            Divider()
            ForEach(order.items ?? []) { item in
                HStack(alignment: .top) {
                    Text("\(item.quantity ?? 1)×").font(.body.monospacedDigit().bold())
                    VStack(alignment: .leading) {
                        Text(item.productName ?? "Item")
                        if let s = item.sku, !s.isEmpty { Text(s).font(.caption.monospaced()).foregroundStyle(.secondary) }
                    }
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
    }
}
