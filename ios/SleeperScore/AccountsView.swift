//  AccountsView.swift
//  El menú de cuentas: con qué plataforma entras.
//
//  Sleeper y Yahoo se pueden conectar. ESPN y NFL.com salen apagadas a
//  propósito: están para decir "esto viene después", no para engañar.

import SwiftUI

struct AccountsView: View {
    @EnvironmentObject private var model: ScoreboardModel
    @Environment(\.dismiss) private var dismiss
    @StateObject private var yahoo = YahooAuth()

    @State private var connections: [HostKind: HostConnection] = SharedStore.connections()
    @State private var showingYahoo = false
    @State private var catalogDate: Date?
    @State private var isRefreshingCatalog = false

    var body: some View {
        NavigationStack {
            Form {
                accountsSection
                testingSection
                widgetSection
                catalogSection
                aboutSection
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Cuentas")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cerrar") { dismiss() }
                }
            }
            .sheet(isPresented: $showingYahoo) {
                YahooLoginView(auth: yahoo)
                    .preferredColorScheme(.dark)
            }
            .task {
                catalogDate = await PlayerCatalog.shared.savedAt
            }
            .onChange(of: showingYahoo) { _, abierto in
                if !abierto { connections = SharedStore.connections() }
            }
        }
    }

    // MARK: - Plataformas

    private var accountsSection: some View {
        Section {
            NavigationLink {
                SleeperSettingsView()
                    .environmentObject(model)
            } label: {
                HostRow(host: .sleeper, connection: connections[.sleeper])
            }

            Button {
                showingYahoo = true
            } label: {
                HostRow(host: .yahoo, connection: connections[.yahoo])
            }

            ForEach(HostKind.allCases.filter { !$0.isAvailable }) { host in
                HostRow(host: host, connection: nil)
                    .opacity(0.45)
                    // No es solo estética: no se puede tocar.
                    .allowsHitTesting(false)
                    .accessibilityHint("Todavía no disponible")
            }
        } header: {
            Text("Dónde juegas")
        } footer: {
            Text("ESPN y NFL.com llegarán más adelante: sus API no son públicas y hace falta resolver antes cómo entrar en cada una.")
        }
    }

    // MARK: - Pruebas

    /// Anotaciones de mentira para probar la Live Activity y los avisos sin
    /// esperar a que se juegue la jornada. Solo en compilaciones de depuración.
    @ViewBuilder
    private var testingSection: some View {
        #if DEBUG
        Section {
            Button("Anota tu jugador (+6)") {
                Task { await model.simulate(.touchdown, mine: true) }
            }
            Button("Anota el rival (+6)") {
                Task { await model.simulate(.touchdown, mine: false) }
            }
            Button("Field goal (+3)") {
                Task { await model.simulate(.fieldGoal, mine: true) }
            }
            Button(model.isSimulating ? "Parar el partido simulado" : "Partido simulado (cada 12 s)") {
                if model.isSimulating {
                    model.stopFakeGame()
                } else {
                    model.startFakeGame()
                }
            }
            .foregroundStyle(model.isSimulating ? Color.orange : Theme.accent)
        } header: {
            Text("Pruebas")
        } footer: {
            Text("Suma puntos a un titular al azar y lo mete por el mismo camino que los datos reales: detección de anotación, Live Activity y notificación. Mientras el partido simulado esté en marcha no se descargan los puntos de verdad.")
        }
        #endif
    }

    // MARK: - Resto de ajustes

    private var widgetSection: some View {
        Section {
            Label(
                SharedStore.usesAppGroup ? "Compartido con el widget" : "Widget sin datos compartidos",
                systemImage: SharedStore.usesAppGroup ? "checkmark.seal.fill" : "exclamationmark.triangle.fill"
            )
            .foregroundStyle(SharedStore.usesAppGroup ? Theme.accent : .orange)
        } header: {
            Text("Widget")
        } footer: {
            Text(
                SharedStore.usesAppGroup
                ? "El widget usa la liga y el equipo que elijas aquí."
                : "Falta activar el grupo de apps (App Groups) en Xcode. Sin él, el widget se queda con la liga por defecto del código."
            )
        }
    }

    private var catalogSection: some View {
        Section {
            Button {
                isRefreshingCatalog = true
                Task {
                    await model.forceCatalogRefresh()
                    catalogDate = await PlayerCatalog.shared.savedAt
                    isRefreshingCatalog = false
                }
            } label: {
                if isRefreshingCatalog {
                    HStack { ProgressView(); Text("Descargando…") }
                } else {
                    Text("Actualizar catálogo de jugadores")
                }
            }
            .disabled(isRefreshingCatalog)
        } header: {
            Text("Nombres y fotos de los jugadores")
        } footer: {
            if let catalogDate {
                Text("Guardado el \(catalogDate.formatted(date: .abbreviated, time: .shortened)). Se renueva solo una vez al día.")
            } else {
                Text("Aún no se ha descargado. Son unos 5 MB y solo hace falta una vez al día.")
            }
        }
    }

    private var aboutSection: some View {
        Section {
            LabeledContent("Versión", value: Bundle.main.shortVersion)
            Link("API de Sleeper", destination: URL(string: "https://docs.sleeper.com")!)
        }
    }
}

/// Una fila del menú: plataforma, estado y a qué invita.
struct HostRow: View {
    var host: HostKind
    var connection: HostConnection?

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: host.symbol)
                .font(.system(size: 20))
                .foregroundStyle(host.isAvailable ? host.accent : Color.secondary)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 2) {
                Text(host.title)
                    .foregroundStyle(.primary)
                Text(connection.map { "Conectado como \($0.accountName)" } ?? host.tagline)
                    .font(.caption)
                    .foregroundStyle(connection == nil ? Color.secondary : Theme.accent)
            }

            Spacer()

            if !host.isAvailable {
                Text("Próximamente")
                    .font(.caption2.weight(.semibold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Color.secondary.opacity(0.18), in: Capsule())
                    .foregroundStyle(.secondary)
            } else if connection != nil {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(Theme.accent)
            }
        }
        .padding(.vertical, 2)
    }
}

// MARK: - Yahoo

struct YahooLoginView: View {
    @ObservedObject var auth: YahooAuth
    @Environment(\.dismiss) private var dismiss
    @State private var isWorking = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                if auth.isConnected {
                    Section {
                        Label("Sesión iniciada", systemImage: "checkmark.seal.fill")
                            .foregroundStyle(Theme.accent)
                        Button("Cerrar sesión", role: .destructive) {
                            auth.signOut()
                        }
                    } footer: {
                        Text("El token queda en el llavero del iPhone. Leer tus ligas de Yahoo es el siguiente paso y todavía no está hecho: el marcador sigue viniendo de Sleeper.")
                    }
                } else {
                    Section {
                        TextField("Client ID", text: $auth.credentials.clientID)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        SecureField("Client Secret", text: $auth.credentials.clientSecret)
                        TextField("Redirect URI", text: $auth.credentials.redirectURI)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    } header: {
                        Text("Tu app de Yahoo")
                    } footer: {
                        Text("Se sacan registrando una app en developer.yahoo.com con permiso de Fantasy Sports de solo lectura. No vienen en el código a propósito: un secreto metido en una app de iPhone lo puede extraer cualquiera. Se guardan en el llavero de este teléfono.")
                    }

                    Section {
                        Button {
                            Task { await connect() }
                        } label: {
                            if isWorking {
                                HStack { ProgressView(); Text("Abriendo Yahoo…") }
                            } else {
                                Text("Iniciar sesión con Yahoo")
                            }
                        }
                        .disabled(isWorking || !auth.credentials.isComplete)
                    }
                }

                if let error {
                    Section {
                        Label(error, systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.orange)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Yahoo")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cerrar") { dismiss() }
                }
            }
        }
    }

    private func connect() async {
        isWorking = true
        error = nil
        defer { isWorking = false }
        do {
            try await auth.signIn()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// Avatar de red con hueco de reserva, para las listas de ajustes.
struct AsyncAvatar: View {
    var url: URL?
    var size: CGFloat

    var body: some View {
        AsyncImage(url: url) { image in
            image.resizable().scaledToFill()
        } placeholder: {
            Image(systemName: "person.crop.circle.fill")
                .resizable()
                .scaledToFit()
                .foregroundStyle(.secondary)
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
    }
}

extension Bundle {
    var shortVersion: String {
        let version = infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }
}
