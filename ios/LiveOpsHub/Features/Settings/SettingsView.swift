import SwiftUI

struct SettingsView: View {
    @Environment(AppState.self) private var app
    @State private var showShops = false
    @State private var confirmDelete = false
    @State private var confirmWipeOrg = false
    @State private var deleting = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                Section {
                    LabeledContent("Name", value: app.name)
                    LabeledContent("Username", value: app.user)
                    LabeledContent("Company", value: app.companyName)
                    LabeledContent("Role", value: app.roles.map(roleLabel).joined(separator: ", "))
                }

                if app.canConnectShops {
                    Section {
                        Button { showShops = true } label: {
                            Label("TikTok Shop connections", systemImage: "link")
                        }
                    } footer: {
                        Text("Connect or re-authorize the TikTok shops whose orders flow into LiveOpsHub.")
                    }
                }

                Section {
                    Link(destination: LegalLinks.privacy) { Label("Privacy Policy", systemImage: "hand.raised") }
                    Link(destination: LegalLinks.terms) { Label("Terms of Service", systemImage: "doc.text") }
                    Link(destination: URL(string: "mailto:\(LegalLinks.supportEmail)")!) {
                        Label("Contact support", systemImage: "envelope")
                    }
                    LabeledContent("Version", value: APIClient.appVersion)
                }

                Section {
                    Button("Sign out") { Task { await app.signOut() } }
                }

                Section {
                    Button(role: .destructive) { confirmDelete = true } label: {
                        if deleting { ProgressView() } else { Text("Delete my account") }
                    }
                    .disabled(deleting)
                } footer: {
                    Text("Permanently deletes your LiveOpsHub login. Order history you handled stays with your company.")
                }
            }
            .navigationTitle("Account")
            .sheet(isPresented: $showShops) {
                NavigationStack {
                    AuthenticatedWebView(path: "/admin/tiktok")
                        .navigationTitle("TikTok Shop")
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar { Button("Done") { showShops = false } }
                }
            }
            .confirmationDialog("Delete your account?", isPresented: $confirmDelete, titleVisibility: .visible) {
                Button("Delete account", role: .destructive) { Task { await delete(wipeOrg: false) } }
            } message: {
                Text("This can't be undone.")
            }
            .confirmationDialog("You're the last admin", isPresented: $confirmWipeOrg, titleVisibility: .visible) {
                Button("Delete account and company data", role: .destructive) { Task { await delete(wipeOrg: true) } }
            } message: {
                Text("Deleting your account will also permanently delete your company's LiveOpsHub data: orders, packing videos, inventory and users.")
            }
            .alert("Error", isPresented: .constant(error != nil)) { Button("OK") { error = nil } } message: { Text(error ?? "") }
        }
    }

    private func delete(wipeOrg: Bool) async {
        deleting = true; defer { deleting = false }
        do {
            let r: DeleteAccountResponse = try await APIClient.shared.post("/api/account/delete",
                                                                         body: ["wipe_org": wipeOrg])
            if r.needOrgConfirm == true { confirmWipeOrg = true; return }
            guard r.ok else { throw APIError.server(r.error ?? r.message ?? "Couldn't delete the account") }
            APIClient.shared.clearCookies()
            app.reset()
        } catch { app.handle(error); self.error = (error as? LocalizedError)?.errorDescription }
    }

    private func roleLabel(_ r: String) -> String {
        switch r {
        case "admin": return "Admin"
        case "manager": return "Warehouse Manager"
        case "cs": return "Customer Service"
        case "host": return "Host"
        case "worker", "picker": return "Warehouse Associate"
        default: return r.capitalized
        }
    }
}
