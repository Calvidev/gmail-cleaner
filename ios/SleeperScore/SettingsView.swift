//  SettingsView.swift
//  Elegir liga y equipo, y ver el estado de lo que comparte con el widget.

import SwiftUI

@MainActor
final class SettingsModel: ObservableObject {
    @Published var leagueID: String
    @Published var selectedRosterID: Int?
    @Published private(set) var teams: [LeagueTeam] = []
    @Published private(set) var leagueName: String?
    @Published private(set) var isLoading = false
    @Published private(set) var error: String?
    @Published private(set) var catalogDate: Date?

    private let service = MatchupService()

    init(config: LeagueConfig) {
        leagueID = config.leagueID
        selectedRosterID = config.rosterID
    }

    var selectedTeam: LeagueTeam? {
        teams.first { $0.rosterID == selectedRosterID }
    }

    var canSave: Bool {
        !leagueID.trimmingCharacters(in: .whitespaces).isEmpty && selectedRosterID != nil
    }

    func loadTeams() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let result = try await service.teams(in: leagueID)
            leagueName = result.leagueName
            teams = result.teams
            // Si el equipo guardado ya no existe en esta liga, se elige el primero.
            if selectedRosterID == nil || !teams.contains(where: { $0.rosterID == selectedRosterID }) {
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
            teamName: selectedTeam?.name
        )
    }
}

struct SettingsView: View {
    @EnvironmentObject private var model: ScoreboardModel
    @Environment(\.dismiss) private var dismiss
    @StateObject private var settings: SettingsModel
    @State private var isRefreshingCatalog = false

    init() {
        _settings = StateObject(wrappedValue: SettingsModel(config: SharedStore.loadConfig()))
    }

    var body: some View {
        NavigationStack {
            Form {
                leagueSection
                teamsSection
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
                await settings.loadTeams()
                await settings.loadCatalogDate()
            }
        }
    }

    // MARK: - Secciones

    private var leagueSection: some View {
        Section {
            TextField("Id de la liga", text: $settings.leagueID)
                .keyboardType(.numberPad)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            Button {
                Task { await settings.loadTeams() }
            } label: {
                if settings.isLoading {
                    HStack { ProgressView(); Text("Buscando equipos…") }
                } else {
                    Text("Buscar equipos")
                }
            }
            .disabled(settings.isLoading)
        } header: {
            Text("Liga de Sleeper")
        } footer: {
            Text("Es el número de la dirección de tu liga: sleeper.com/leagues/**número**/team")
        }
    }

    @ViewBuilder
    private var teamsSection: some View {
        if let error = settings.error {
            Section {
                Label(error, systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
            }
        }
        if !settings.teams.isEmpty {
            Section(settings.leagueName ?? "Equipos") {
                ForEach(settings.teams) { team in
                    Button {
                        settings.selectedRosterID = team.rosterID
                    } label: {
                        HStack(spacing: 10) {
                            AsyncImage(url: team.avatarURL) { image in
                                image.resizable().scaledToFill()
                            } placeholder: {
                                Image(systemName: "person.crop.circle.fill")
                                    .resizable()
                                    .foregroundStyle(.secondary)
                            }
                            .frame(width: 28, height: 28)
                            .clipShape(Circle())

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
            }
        }
    }

    private var widgetSection: some View {
        Section {
            HStack {
                Label(
                    SharedStore.usesAppGroup ? "Compartido con el widget" : "Widget sin datos compartidos",
                    systemImage: SharedStore.usesAppGroup ? "checkmark.seal.fill" : "exclamationmark.triangle.fill"
                )
                .foregroundStyle(SharedStore.usesAppGroup ? Theme.accent : .orange)
            }
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

extension Bundle {
    var shortVersion: String {
        let version = infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }
}
