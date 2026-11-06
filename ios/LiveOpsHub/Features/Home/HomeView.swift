import SwiftUI

struct HomeView: View {
    @Environment(AppState.self) private var app
    @State private var stats: MyStats?
    @State private var fulfillment: Fulfillment?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                Section("You") {
                    HStack {
                        metric("Today", stats?.today?.count)
                        metric("This month", stats?.thisMonth?.count)
                        metric("Rank", stats?.rankThisMonth.map { "#\($0)" })
                    }
                    if let avg = stats?.today?.avgDur, avg > 0 {
                        LabeledContent("Avg. pack time today", value: String(format: "%.0f s", avg))
                    }
                }

                if app.canManage, let f = fulfillment {
                    Section("Warehouse") {
                        HStack {
                            metric("To pick", f.totalToPick)
                            metric("To pack", f.totalToPack)
                            metric("Open shows", f.showsRemaining)
                        }
                    }
                    if !f.shows.isEmpty {
                        Section("Shows") {
                            ForEach(f.shows) { s in
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(s.name).font(.headline)
                                    ProgressView(value: Double(s.total - s.toPack), total: Double(max(s.total, 1)))
                                    Text("\(s.toPick) to pick · \(s.toPack) to pack · \(s.total) orders")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                .padding(.vertical, 4)
                            }
                        }
                    }
                }

                if let e = error { Text(e).foregroundStyle(.red) }
            }
            .navigationTitle(app.companyName.isEmpty ? "Today" : app.companyName)
            .refreshable { await load() }
            .task { await load() }
        }
    }

    private func metric(_ title: String, _ value: Int?) -> some View {
        metric(title, value.map { String($0) })
    }

    private func metric(_ title: String, _ value: String?) -> some View {
        VStack(spacing: 2) {
            Text(value ?? "–").font(.title2.bold().monospacedDigit())
            Text(title).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func load() async {
        error = nil
        do { stats = try await APIClient.shared.get("/api/me/stats") }
        catch { app.handle(error); self.error = (error as? LocalizedError)?.errorDescription }
        if app.canManage {
            fulfillment = try? await APIClient.shared.get("/api/home/fulfillment")
        }
    }
}
