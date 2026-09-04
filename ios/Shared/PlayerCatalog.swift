//  PlayerCatalog.swift
//  Nombres de los jugadores para la alineación.
//
//  El catálogo de Sleeper pesa unos 5 MB, así que se descarga como mucho una
//  vez al día y se guarda recortado (nombre, posición y equipo) en el grupo de
//  apps. El widget solo lee ese archivo: nunca descarga los 5 MB.

import Foundation

actor PlayerCatalog {
    static let shared = PlayerCatalog()

    private let fileName = "players-catalog.json"
    private let maxAge: TimeInterval = 60 * 60 * 24  // un día
    private var memory: [String: CatalogPlayer]?

    private var fileURL: URL {
        SharedStore.containerURL.appendingPathComponent(fileName)
    }

    /// Fecha del catálogo guardado, o nil si no hay ninguno.
    var savedAt: Date? {
        let attributes = try? FileManager.default.attributesOfItem(atPath: fileURL.path)
        return attributes?[.modificationDate] as? Date
    }

    var isStale: Bool {
        guard let savedAt else { return true }
        return Date().timeIntervalSince(savedAt) > maxAge
    }

    /// Lo que hay guardado. No descarga nada: es lo que usa el widget.
    func cached() -> [String: CatalogPlayer] {
        if let memory { return memory }
        guard
            let data = try? Data(contentsOf: fileURL),
            let decoded = try? SharedJSON.decoder.decode([String: CatalogPlayer].self, from: data)
        else {
            return [:]
        }
        memory = decoded
        return decoded
    }

    /// Catálogo al día, descargándolo si hace falta. Solo desde la app.
    @discardableResult
    func refreshIfNeeded(force: Bool = false) async -> [String: CatalogPlayer] {
        if !force && !isStale {
            let saved = cached()
            if !saved.isEmpty { return saved }
        }
        guard let raw = try? await SleeperAPI.shared.playersCatalog() else {
            return cached()
        }

        var trimmed: [String: CatalogPlayer] = [:]
        trimmed.reserveCapacity(raw.count)
        for (playerID, entry) in raw {
            let name = Self.name(for: playerID, entry: entry)
            guard !name.isEmpty else { continue }
            trimmed[playerID] = CatalogPlayer(
                name: name, position: entry.position, team: entry.team
            )
        }

        memory = trimmed
        if let data = try? SharedJSON.encoder.encode(trimmed) {
            try? data.write(to: fileURL, options: .atomic)
        }
        return trimmed
    }

    /// Las defensas no traen nombre: su id es la abreviatura del equipo.
    private static func name(for playerID: String, entry: RawCatalogPlayer) -> String {
        if let full = entry.fullName, !full.isEmpty { return full }
        let parts = [entry.firstName, entry.lastName].compactMap { $0 }.filter { !$0.isEmpty }
        if !parts.isEmpty { return parts.joined(separator: " ") }
        if entry.position == "DEF" { return "\(entry.team ?? playerID) D/ST" }
        return ""
    }
}
