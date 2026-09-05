//  SettingsView.swift
//  Entrar con tu usuario de Sleeper, elegir liga y ver qué comparte con el widget.

import SwiftUI

@MainActor
final class SettingsModel: ObservableObject {
    // Cuenta
    @Published var username: String
    @Published private(set) var account: SleeperAccount?

    // Liga y equipo
    @Published var leagueID: String
    @Published var selectedRosterID: Int?
    @Published private(set) var teams: [LeagueTeam] = []
    @Published private(set) var leagueName: String?

    // Estado de la pantalla
    @Published private(set) var isLoadingAccount = false
    @Published private(set) var isLoadingTeams = false
    @Published private(set) var status: String?
    @Published private(set) var error: String?
    @Published private(set) var catalogDate: Date?

    private let service = MatchupService()

    init(config: LeagueConfig) {
        username = config.username ?? ""
        leagueID = config.leagueID
        selectedRosterID = config.rosterID
    }

    var selectedTeam: LeagueTeam? {
        teams.first { $0.rosterID == selectedRosterID }
    }

    var canSave: Bool {
        !leagueID.trimmingCharacters(in: .whitespaces).isEmpty && selectedRosterID != nil
    }

    // MARK: - Entrar con la cuenta

    /// Busca el usuario y sus ligas. La API de Sleeper es pública: esto no es
    /// un login, no hay contraseña; el nombre de usuario basta para leer.
    func loadAccount() async {
        isLoadingAccount = true
        error = nil
        status = nil
        defer { isLoadingAccount = false }
        do {
            let found = try await service.account(username: username)
            account = found
            if found.leagues.isEmpty {
                status = "\(found.user.name) no tiene ligas en \(found.season)."
            } else {
                status = "\(found.leagues.count) liga(s) en \(found.season). Elige una."
            }
        } catch {
            account = nil
            self.error = error.localizedDescription
        }
    }

    /// Al elegir una liga se detecta tu equipo comparando tu `user_id` con el
    /// dueño de cada roster. Si no aparece (equipo compartido raro, liga de
    /// otro), se puede elegir a mano de la lista.
    func choose(_ league: LeagueSummary) async {
        leagueID = league.leagueID
        await loadTeams(keepingSelection: false)
        guard let userID = account?.user.userID else { return }
        if let mine = teams.first(where: { $0.belongs(to: userID) }) {
            selectedRosterID = mine.rosterID
            status = "Tu equipo: \(mine.name)"
        } else {
            status = "No reconozco tu equipo en esta liga; elígelo de la lista."
        }
    }

    // MARK: - Equipos de la liga

    func loadTeams(keepingSelection: Bool = true) async {
        isLoadingTeams = true
        error = nil
        defer { isLoadingTeams = false }
        do {
            let result = try await service.teams(in: leagueID)
            leagueName = result.leagueName
            teams = result.teams
            let sigueValido = teams.contains { $0.rosterID == selectedRosterID }
            if !keepingSelection || !sigueValido {
                selectedRosterID = teams.first?.rosterID
            }
        } catch {
            teams = []
            leagueName = nil
            self.error = error.localizedDescription
        }
    }

    func loadCatalogDate() async {
        catalogDate = await PlayerCatalog.shared.savedAt
    }

    func config() -> LeagueConfig {
        LeagueConfig(
            leagueID: leagueID.trimmingCharacters(in: .whitespaces),
            rosterID: selectedRosterID ?? AppConfig.defaultRosterID,
            teamName: selectedTeam?.name,
            username: account?.user.username ?? (username.isEmpty ? nil : username),
            userID: account?.user.userID
        )
    }
}

struct SettingsView: View {
    @EnvironmentObject private var model: ScoreboardModel
    @Environment(\.dismiss) private var dismiss
    @StateObject private var settings: SettingsModel
    @State private var isRefreshingCatalog = false
    @State private var showingManualLeague = false

    init() {
        _settings = StateObject(wrappedValue: SettingsModel(config: SharedStore.loadConfig()))
    }

    var body: some View {
        NavigationStack {
            Form {
                accountSection
                messagesSection
                myLeaguesSection
                teamsSection
                manualSection
                widgetSection
                catalogSection
                aboutSection
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Ajustes")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cerrar") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Guardar") {
                        model.update(config: settings.config())
                        dismiss()
                    }
                    .disabled(!settings.canSave)
                }
            }
            .task {
                // Si ya había liga elegida, se carga para poder cambiar de equipo.
                if !settings.leagueID.isEmpty { await settings.loadTeams() }
                await settings.loadCatalogDate()
            }
        }
    }

    // MARK: - Cuenta

    private var accountSection: some View {
        Section {
            HStack(spacing: 10) {
                AsyncAvatar(url: settings.account?.user.avatarURL, size: 30)
                TextField("Tu usuario de Sleeper", text: $settings.username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.search)
                    .onSubmit { Task { await settings.loadAccount() } }
            }
            Button {
                Task { await settings.loadAccount() }
            } label: {
                if settings.isLoadingAccount {
                    HStack { ProgressView(); Text("Buscando tus ligas…") }
                } else {
                    Text("Buscar mis ligas")
                }
            }
            .disabled(settings.isLoadingAccount || settings.username.trimmingCharacters(in: .whitespaces).isEmpty)
        } header: {
            Text("Tu cuenta de Sleeper")
        } footer: {
            Text("El nombre de usuario con el que entras en Sleeper, no el correo. No se pide contraseña: la API de Sleeper es de solo lectura y pública.")
        }
    }

    @ViewBuilder
    private var messagesSection: some View {
        if settings.error != nil || settings.status != nil {
            Section {
                if let error = settings.error {
                    Label(error, systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                }
                if let status = settings.status {
                    Label(status, systemImage: "checkmark.circle")
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    @ViewBuilder
    private var myLeaguesSection: some View {
        if let leagues = settings.account?.leagues, !leagues.isEmpty {
            Section("Tus ligas") {
                ForEach(leagues) { league in
                    Button {
                        Task { await settings.choose(league) }
                    } label: {
                        HStack(spacing: 10) {
                            AsyncAvatar(url: league.avatarURL, size: 28)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(league.displayName)
                                    .foregroundStyle(.primary)
                                if !league.subtitle.isEmpty {
                                    Text(league.subtitle)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            Spacer()
                            if league.leagueID == settings.leagueID {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(Theme.accent)
                            }
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var teamsSection: some View {
        if !settings.teams.isEmpty {
            Section {
                ForEach(settings.teams) { team in
                    Button {
                        settings.selectedRosterID = team.rosterID
                    } label: {
                        HStack(spacing: 10) {
                            AsyncAvatar(url: team.avatarURL, size: 28)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(team.name)
                                    .foregroundStyle(.primary)
                                if let record = team.record {
                                    Text(record)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            Spacer()
                            if team.rosterID == settings.selectedRosterID {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(Theme.accent)
                            }
                        }
                    }
                }
            } header: {
                HStack {
                    Text(settings.leagueName ?? "Equipos")
                    if settings.isLoadingTeams {
                        Spacer()
                        ProgressView()
                    }
                }
            } footer: {
                Text("Marcado está el equipo cuyo marcador verás. Si entraste con tu usuario, ya viene elegido el tuyo.")
            }
        }
    }

    private var manualSection: some View {
        Section {
            DisclosureGroup("Usar el id de la liga", isExpanded: $showingManualLeague) {
                TextField("Id de la liga", text: $settings.leagueID)
                    .keyboardType(.numberPad)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button("Buscar equipos") {
                    Task { await settings.loadTeams(keepingSelection: false) }
                }
                .disabled(settings.isLoadingTeams)
                Text("El número de sleeper.com/leagues/**número**/team. Solo hace falta para una liga que no sea tuya.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Resto

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
                    await settings.loadCatalogDate()
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
            Text("Nombres de los jugadores")
        } footer: {
            if let date = settings.catalogDate {
                Text("Guardado el \(date.formatted(date: .abbreviated, time: .shortened)). Se renueva solo una vez al día.")
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
