//  SharedStore.swift
//  Lo que la app deja escrito para que el widget lo lea.
//
//  Todo pasa por el grupo de apps. Si el grupo no está activado (pasa con las
//  cuentas de Apple gratuitas), no se rompe nada: la app usa su propio
//  almacenamiento y el widget tira de los valores por defecto de `AppConfig`.

import Foundation

/// Liga y equipo elegidos.
struct LeagueConfig: Codable, Equatable {
    var leagueID: String
    var rosterID: Int
    var teamName: String?

    static let `default` = LeagueConfig(
        leagueID: AppConfig.defaultLeagueID,
        rosterID: AppConfig.defaultRosterID,
        teamName: nil
    )

    var isComplete: Bool { !leagueID.trimmingCharacters(in: .whitespaces).isEmpty }
}

enum SharedStore {
    private static let configKey = "leagueConfig"
    private static let snapshotFile = "matchup-snapshot.json"

    // MARK: - Dónde se guarda

    /// `true` cuando el grupo de apps está bien configurado y firmado.
    static var usesAppGroup: Bool {
        FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: AppConfig.appGroupID) != nil
    }

    static var defaults: UserDefaults {
        UserDefaults(suiteName: AppConfig.appGroupID) ?? .standard
    }

    /// Carpeta compartida; si no hay grupo, la caché propia del proceso.
    static var containerURL: URL {
        if let shared = FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: AppConfig.appGroupID
        ) {
            return shared
        }
        return FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
    }

    private static func fileURL(_ name: String) -> URL {
        containerURL.appendingPathComponent(name)
    }

    // MARK: - Liga elegida

    static func loadConfig() -> LeagueConfig {
        guard
            let data = defaults.data(forKey: configKey),
            let config = try? SharedJSON.decoder.decode(LeagueConfig.self, from: data)
        else {
            return .default
        }
        return config
    }

    static func save(_ config: LeagueConfig) {
        guard let data = try? SharedJSON.encoder.encode(config) else { return }
        defaults.set(data, forKey: configKey)
    }

    // MARK: - Último marcador conocido

    static func cachedSnapshot() -> MatchupSnapshot? {
        guard let data = try? Data(contentsOf: fileURL(snapshotFile)) else { return nil }
        return try? SharedJSON.decoder.decode(MatchupSnapshot.self, from: data)
    }

    static func cache(_ snapshot: MatchupSnapshot) {
        guard let data = try? SharedJSON.encoder.encode(snapshot) else { return }
        try? data.write(to: fileURL(snapshotFile), options: .atomic)
    }

    /// El marcador guardado, marcado ya como viejo para que la interfaz lo diga.
    static func staleSnapshot() -> MatchupSnapshot? {
        guard var snapshot = cachedSnapshot() else { return nil }
        snapshot.isStale = true
        return snapshot
    }
}
