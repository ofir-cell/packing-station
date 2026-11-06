import SwiftUI

struct LoginView: View {
    @Environment(AppState.self) private var app
    @State private var username = ""
    @State private var password = ""
    @State private var busy = false
    @State private var error: String?
    @FocusState private var focus: Field?
    private enum Field { case user, pass }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(spacing: 8) {
                        Image(systemName: "shippingbox.and.arrow.backward.fill")
                            .font(.system(size: 44))
                            .foregroundStyle(.tint)
                        Text("LiveOpsHub").font(.largeTitle.bold())
                        Text("Pick, pack and prove every live-sale order.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .listRowBackground(Color.clear)
                }

                Section {
                    TextField("Username", text: $username)
                        .textContentType(.username)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($focus, equals: .user)
                        .submitLabel(.next)
                        .onSubmit { focus = .pass }
                    SecureField("Password", text: $password)
                        .textContentType(.password)
                        .focused($focus, equals: .pass)
                        .submitLabel(.go)
                        .onSubmit { Task { await submit() } }
                } footer: {
                    if let msg = error ?? app.bannerError {
                        Text(msg).foregroundStyle(.red)
                    }
                }

                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        HStack {
                            Spacer()
                            if busy { ProgressView() } else { Text("Sign in").bold() }
                            Spacer()
                        }
                    }
                    .disabled(busy || username.isEmpty || password.isEmpty)
                }

                Section {
                    Link("New to LiveOpsHub? Request access",
                         destination: LegalLinks.requestAccess)
                } footer: {
                    Text("Accounts are created by your company's LiveOpsHub admin.")
                }
            }
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private func submit() async {
        guard !busy else { return }
        busy = true; error = nil; app.bannerError = nil
        defer { busy = false }
        do {
            try await app.signIn(username: username.trimmingCharacters(in: .whitespaces).lowercased(),
                                 password: password)
            password = ""
        } catch {
            self.error = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }
}
