import SwiftUI

/// Scan or type any label to see where that order stands — for customer
/// service questions on the floor ("was this one packed? who packed it?").
struct OrderLookupView: View {
    @Environment(AppState.self) private var app
    @State private var result: ShipmentLookup?
    @State private var loading = false
    @State private var error: String?
    @State private var scanning = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ManualCodeEntry(placeholder: "Tracking number or order ID") { c in Task { await lookup(c) } }
                    if BarcodeScannerView.isAvailable {
                        Button { scanning = true } label: { Label("Scan a label", systemImage: "barcode.viewfinder") }
                    }
                }
                if loading { ProgressView().frame(maxWidth: .infinity) }
                if let r = result, let s = r.shipment {
                    Section("Order") {
                        LabeledContent("Buyer", value: s.displayBuyer)
                        LabeledContent("Status") { StatusPill(status: s.status ?? "unknown") }
                        if let t = s.trackingCode { LabeledContent("Tracking", value: t) }
                        if let show = s.importLabel { LabeledContent("Show", value: show) }
                        if let p = s.platform { LabeledContent("Platform", value: p.capitalized) }
                        if let by = s.pickedBy, !by.isEmpty { LabeledContent("Picked by", value: by) }
                        if let by = s.packedBy, !by.isEmpty { LabeledContent("Packed by", value: by) }
                    }
                    Section("Items") {
                        ForEach(r.items ?? []) { i in
                            VStack(alignment: .leading) {
                                Text("\(i.quantity ?? 1)× \(i.productName ?? "Item")")
                                if let sku = i.sku, !sku.isEmpty {
                                    Text(sku).font(.caption.monospaced()).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("Lookup")
            .sheet(isPresented: $scanning) {
                BarcodeScannerView { c in scanning = false; Task { await lookup(c) } }
                    .ignoresSafeArea()
                    .presentationDetents([.medium])
            }
            .alert("Not found", isPresented: .constant(error != nil)) { Button("OK") { error = nil } } message: { Text(error ?? "") }
        }
    }

    private func lookup(_ raw: String) async {
        loading = true; result = nil; defer { loading = false }
        do {
            let path = "/api/shipment/" + PackFlowView.sanitize(raw)
            let r: ShipmentLookup = try await APIClient.shared.get(path)
            guard r.ok else { throw APIError.server(r.error ?? "Shipment not found") }
            result = r
        } catch { app.handle(error); self.error = (error as? LocalizedError)?.errorDescription }
    }
}

struct StatusPill: View {
    let status: String
    private var color: Color {
        switch status.lowercased() {
        case "pending": return .gray
        case "picked": return .blue
        case "packed": return .green
        case "shipped": return .teal
        case "cancelled": return .red
        case "issue": return .orange
        default: return .secondary
        }
    }
    var body: some View {
        Text(status.capitalized)
            .font(.caption.bold())
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color.opacity(0.15), in: Capsule())
            .foregroundStyle(color)
    }
}
