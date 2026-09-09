//  SharedStore.swift
//  Lo que la app deja escrito para que el widget lo lea.
//
//  Todo pasa por el grupo de apps. Si el grupo no está activado (pasa con las
//  cuentas de Apple gratuitas), no se rompe nada: la app usa su propio
//  almacenamiento y el widget tira de los valores por defecto de `AppConfig`.

import Foundation

/// Una liga tuya: dónde juegas y con qué equipo.
///
/// `username` y `userID` se guardan cuando entras con tu cuenta de Sleeper:
/// no hacen falta para pintar el marcador, pero permiten volver a encontrar
/// tu equipo si cambias de liga sin tener que preguntarte nada otra vez.
struct LeagueConfig: Codable, Equatable, Identifiable, Hashable {
    var leagueID: String
    var rosterID: Int
    var teamName: String?
    var username: String? = nil
    var userID: String? = nil
    /// Para el selector de ligas: el nombre que enseña Sleeper.
    var leagueName: String? = nil
    /// Preparado para cuando haya Yahoo: dos ligas de plataformas distintas
    /// pueden compartir número. Opcional en el archivo para que una
    /// configuración guardada por la versión anterior se siga leyendo.
    var host: HostKind?

    /// La plataforma, ya sin opcional.
    var platform: HostKind { host ?? .sleeper }

    var id: String { "\(platform.rawValue):\(leagueID)" }

    static let `default` = LeagueConfig(
        leagueID: AppConfig.defaultLeagueID,
        rosterID: AppConfig.defaultRosterID,
        teamName: nil
    )

    var isComplete: Bool { !leagueID.trimmingCharacters(in: .whitespaces).isEmpty }

    var displayName: String {
        if let leagueName, !leagueName.isEmpty { return leagueName }
        return "Liga \(leagueID)"
    }
}

/// Todas tus ligas y cuál se está mirando.
struct LeagueBook: Codable, Equatable {
    var leagues: [LeagueConfig] = []
    var activeID: String?

    var active: LeagueConfig? {
        if let activeID, let encontrada = leagues.first(where: { $0.id == activeID }) {
            return encontrada
        }
        return leagues.first
    }

    var isEmpty: Bool { leagues.isEmpty }

    mutating func upsert(_ league: LeagueConfig, makeActive: Bool = true) {
        if let indice = leagues.firstIndex(where: { $0.id == league.id }) {
            leagues[indice] = league
        } else {
            leagues.append(league)
        }
        if makeActive { activeID = league.id }
    }

    mutating func remove(_ league: LeagueConfig) {
        leagues.removeAll { $0.id == league.id }
        if activeID == league.id { activeID = leagues.first?.id }
    }
}

enum SharedStore {
    private static let configKey = "leagueConfig"
    private static let bookKey = "leagueBook"
    private static let connectionsKey = "hostConnections"
    private static let snapshotFile = "matchup-snapshot.json"

    private static func snapshotFile(for league: LeagueConfig?) -> String {
        guard let league else { return snapshotFile }
        // Un archivo por liga: cambiar de liga no debe borrar el marcador de
        // la otra ni enseñar el de quien no toca.
        return "matchup-\(stableHash(league.id)).json"
    }

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

    /// La liga que se está mirando. Es lo que usan el widget y la Live Activity.
    static func loadConfig() -> LeagueConfig {
        loadBook().active ?? .default
    }

    /// Todas las ligas guardadas.
    ///
    /// Si solo hay una configuración de la versión anterior (una liga suelta),
    /// se convierte en un cuaderno de una liga: nadie pierde lo que tenía.
    static func loadBook() -> LeagueBook {
        if let data = defaults.data(forKey: bookKey),
           let libro = try? SharedJSON.decoder.decode(LeagueBook.self, from: data),
           !libro.isEmpty {
            return libro
        }
        if let data = defaults.data(forKey: configKey),
           let antigua = try? SharedJSON.decoder.decode(LeagueConfig.self, from: data),
           antigua.isComplete {
            var libro = LeagueBook()
            libro.upsert(antigua)
            save(libro)
            return libro
        }
        return LeagueBook()
    }

    /// Una liga concreta por su id; nil si ya no está guardada.
    static func league(withID id: String?) -> LeagueConfig? {
        guard let id else { return nil }
        return loadBook().leagues.first { $0.id == id }
    }

    static func save(_ book: LeagueBook) {
        guard let data = try? SharedJSON.encoder.encode(book) else { return }
        defaults.set(data, forKey: bookKey)
    }

    /// Guarda una liga suelta (la deja activa).
    static func save(_ config: LeagueConfig) {
        var libro = loadBook()
        libro.upsert(config)
        save(libro)
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

    static func cachedSnapshot(for league: LeagueConfig? = nil) -> MatchupSnapshot? {
        let liga = league ?? loadBook().active
        guard let data = try? Data(contentsOf: fileURL(snapshotFile(for: liga))) else {
            return nil
        }
        return try? SharedJSON.decoder.decode(MatchupSnapshot.self, from: data)
    }

    static func cache(_ snapshot: MatchupSnapshot, for league: LeagueConfig? = nil) {
        let liga = league ?? loadBook().active
        guard let data = try? SharedJSON.encoder.encode(snapshot) else { return }
        try? data.write(to: fileURL(snapshotFile(for: liga)), options: .atomic)
    }

    /// El marcador guardado, marcado ya como viejo para que la interfaz lo diga.
    static func staleSnapshot(for league: LeagueConfig? = nil) -> MatchupSnapshot? {
        guard var snapshot = cachedSnapshot(for: league) else { return nil }
        snapshot.isStale = true
        return snapshot
    }
}
