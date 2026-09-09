//  SharedStore.swift
//  Lo que la app deja escrito para que el widget lo lea.
//
//  Todo pasa por el grupo de apps. Si el grupo no está activado (pasa con las
//  cuentas de Apple gratuitas), no se rompe nada: la app usa su propio
//  almacenamiento y el widget tira de los valores por defecto de `AppConfig`.

import Foundation

/// Liga y equipo elegidos.
///
/// `username` y `userID` se guardan cuando entras con tu cuenta de Sleeper:
/// no hacen falta para pintar el marcador, pero permiten volver a encontrar
/// tu equipo si cambias de liga sin tener que preguntarte nada otra vez.
struct LeagueConfig: Codable, Equatable {
    var leagueID: String
    var rosterID: Int
    var teamName: String?
    var username: String? = nil
    var userID: String? = nil

    static let `default` = LeagueConfig(
        leagueID: AppConfig.defaultLeagueID,
        rosterID: AppConfig.defaultRosterID,
        teamName: nil
    )

    var isComplete: Bool { !leagueID.trimmingCharacters(in: .whitespaces).isEmpty }
}

enum SharedStore {
    private static let configKey = "leagueConfig"
    private static let connectionsKey = "hostConnections"
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

    // MARK: - Cuentas conectadas

    /// Qué plataformas hay conectadas y con qué cuenta.
    static func connections() -> [HostKind: HostConnection] {
        guard
            let data = defaults.data(forKey: connectionsKey),
            let guardadas = try? SharedJSON.decoder.decode([String: HostConnection].self, from: data)
        else {
            return [:]
        }
        var resultado: [HostKind: HostConnection] = [:]
        for (clave, conexion) in guardadas {
            if let host = HostKind(rawValue: clave) { resultado[host] = conexion }
        }
        return resultado
    }

    static func connect(_ host: HostKind, accountName: String) {
        var actuales = connections()
        actuales[host] = HostConnection(
            host: host, accountName: accountName, connectedAt: Date()
        )
        saveConnections(actuales)
    }

    static func disconnect(_ host: HostKind) {
        var actuales = connections()
        actuales.removeValue(forKey: host)
        saveConnections(actuales)
    }

    private static func saveConnections(_ conexiones: [HostKind: HostConnection]) {
        let porClave = Dictionary(
            uniqueKeysWithValues: conexiones.map { ($0.key.rawValue, $0.value) }
        )
        guard let data = try? SharedJSON.encoder.encode(porClave) else { return }
        defaults.set(data, forKey: connectionsKey)
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
