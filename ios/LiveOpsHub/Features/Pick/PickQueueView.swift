import SwiftUI

struct PickQueueView: View {
    @Environment(AppState.self) private var app
    @State private var rows: [PickQueueRow] = []
    @State private var show: String = ""
    @State private var loading = false
    @State private var error: String?
    @State private var scanning = false
    @State private var path: [String] = []

    private var shows: [String] {
        Array(Set(rows.compactMap { $0.importLabel }.filter { !$0.isEmpty })).sorted()
    }
    private var filtered: [PickQueueRow] {
        show.isEmpty ? rows : rows.filter { $0.importLabel == show }
    }

    var body: some View {
        NavigationStack(path: $path) {
            List {
                if !shows.isEmpty {
                    Picker("Show", selection: $show) {
                        Text("All shows").tag("")
                        ForEach(shows, id: \.self) { Text($0).tag($0) }
                    }
                }
                Section("\(filtered.count) to pick") {
                    ForEach(filtered) { r in
                        NavigationLink(value: r.shipmentId) {
                            VStack(alignment: .leading, spacing: 2) {
                                HStack {
                                    Text(r.displayBuyer).font(.headline)
                                    Spacer()
                                    Text("\(r.pickedCount ?? 0)/\(r.itemCount ?? 0)")
                                        .font(.subheadline.monospacedDigit())
                                        .foregroundStyle((r.pickedCount ?? 0) > 0 ? Color.orange : Color.secondary)
                                }
                                if let by = r.pickStartedBy, !by.isEmpty {
                                    Text("Started by \(by)").font(.caption).foregroundStyle(.orange)
                                } else if let t = r.trackingCode {
                                    Text(t).font(.caption.monospaced()).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            .overlay {
                if loading && rows.isEmpty { ProgressView() }
                else if !loading && filtered.isEmpty {
                    ContentUnavailableView("Nothing to pick", systemImage: "checkmark.circle",
                                           description: Text("New orders appear here after a live."))
                }
            }
            .refreshable { await load() }
            .navigationTitle("Pick")
            .navigationDestination(for: String.self) { sid in PickDetailView(shipmentId: sid) }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { scanning = true } label: { Image(systemName: "barcode.viewfinder") }
                        .accessibilityLabel("Scan a label to open its order")
                }
            }
            .sheet(isPresented: $scanning) {
                NavigationStack {
                    VStack {
                        if BarcodeScannerView.isAvailable {
                            BarcodeScannerView { code in open(code) }
                                .clipShape(RoundedRectangle(cornerRadius: 16))
                        }
                        ManualCodeEntry { code in open(code) }
                    }
                    .padding()
                    .navigationTitle("Scan label")
                    .toolbar { Button("Close") { scanning = false } }
                }
            }
            .alert("Error", isPresented: .constant(error != nil)) { Button("OK") { error = nil } } message: { Text(error ?? "") }
            .task { await load() }
            .onChange(of: path) { _, p in if p.isEmpty { Task { await load() } } }   // back from an order
        }
    }

    private func open(_ code: String) {
        let c = code.uppercased()
        // USPS IMpb labels prepend a routing prefix; the tracking number is the tail.
        func matches(_ row: PickQueueRow) -> Bool {
            let t = (row.trackingCode ?? "").uppercased()
            if t == c || row.shipmentId.uppercased() == c { return true }
            return !t.isEmpty && c.count > t.count && c.hasSuffix(t)
        }
        if let r = rows.first(where: matches) {
            scanning = false
            path = [r.shipmentId]
        } else {
            error = "That label isn't in the pick queue (already picked, cancelled, or not imported yet)."
            scanning = false
        }
    }

    private func load() async {
        loading = true; defer { loading = false }
        do { rows = try await APIClient.shared.get("/api/pick/queue") }
        catch { app.handle(error); self.error = (error as? LocalizedError)?.errorDescription }
    }
}

struct PickDetailView: View {
    @Environment(AppState.self) private var app
    @Environment(\.dismiss) private var dismiss
    let shipmentId: String

    @State private var detail: PickDetail?
    @State private var items: [PickItem] = []
    @State private var busy = false
    @State private var error: String?

    private var active: [PickItem] { items.filter { !$0.isCancelled } }
    private var allPicked: Bool { !active.isEmpty && active.allSatisfy(\.isPicked) }

    var body: some View {
        List {
            if let d = detail {
                if d.cleanoutRequired == true {
                    warning("Clear the table for this show before picking.", "tray.full")
                }
                if d.cleanupBlocked == true {
                    warning("This show still has cancelled items on the table. Put them back first.", "exclamationmark.triangle")
                }
                if d.alreadyPicked == true {
                    warning("Already picked\(d.pickedBy.map { " by \($0)" } ?? "").", "checkmark.circle")
                }
                Section {
                    LabeledContent("Buyer", value: d.shipment?.displayBuyer ?? "")
                    if let t = d.shipment?.trackingCode { LabeledContent("Tracking", value: t) }
                    if let s = d.shipment?.importLabel { LabeledContent("Show", value: s) }
                }
                Section("Items") {
                    ForEach(items) { item in
                        Button { Task { await toggle(item) } } label: {
                            HStack {
                                Image(systemName: item.isPicked ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle(item.isPicked ? Color.green : Color.secondary)
                                    .font(.title2)
                                VStack(alignment: .leading) {
                                    Text("\(item.quantity ?? 1)× \(item.productName ?? "Item")")
                                        .strikethrough(item.isCancelled)
                                    if let s = item.sku, !s.isEmpty {
                                        Text(s).font(.caption.monospaced()).foregroundStyle(.secondary)
                                    }
                                }
                                Spacer()
                                if item.isCancelled { Text("Cancelled").font(.caption.bold()).foregroundStyle(.red) }
                            }
                        }
                        .disabled(item.isCancelled || blocked || busy)
                        .foregroundStyle(.primary)
                    }
                }
            }
        }
        .overlay { if detail == nil { ProgressView() } }
        .navigationTitle("Order")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            if detail != nil, !blocked {
                Button { Task { await complete() } } label: {
                    Text(allPicked ? "Done — order picked" : "Mark whole order picked")
                        .bold().frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.borderedProminent)
                .tint(allPicked ? .green : .accentColor)
                .disabled(busy)
                .padding()
                .background(.bar)
            }
        }
        .alert("Error", isPresented: .constant(error != nil)) { Button("OK") { error = nil } } message: { Text(error ?? "") }
        .task { await load() }
    }

    private var blocked: Bool {
        guard let d = detail else { return true }
        return d.cleanoutRequired == true || d.cleanupBlocked == true || d.alreadyPicked == true
    }

    private func warning(_ text: String, _ icon: String) -> some View {
        Label(text, systemImage: icon).foregroundStyle(.orange).font(.subheadline.bold())
    }

    private func load() async {
        do {
            let d: PickDetail = try await APIClient.shared.get("/api/pick/\(shipmentId)")
            guard d.ok else { throw APIError.server(d.error ?? "Order not found") }
            detail = d; items = d.items ?? []
        } catch { app.handle(error); self.error = (error as? LocalizedError)?.errorDescription }
    }

    private func toggle(_ item: PickItem) async {
        busy = true; defer { busy = false }
        do {
            let r: ToggleResponse = try await APIClient.shared.post("/api/pick/item/\(item.id)/toggle")
            guard r.ok else { throw APIError.server(r.error ?? "Couldn't update item") }
            if let i = items.firstIndex(where: { $0.id == item.id }) { items[i].picked = r.picked ?? (item.isPicked ? 0 : 1) }
            UISelectionFeedbackGenerator().selectionChanged()
        } catch { app.handle(error); self.error = (error as? LocalizedError)?.errorDescription }
    }

    private func complete() async {
        busy = true; defer { busy = false }
        do {
            let r: OKResponse = try await APIClient.shared.post("/api/pick/complete/\(shipmentId)")
            guard r.ok else { throw APIError.server(r.error ?? "Couldn't complete the order") }
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            dismiss()
        } catch { app.handle(error); self.error = (error as? LocalizedError)?.errorDescription }
    }
}
