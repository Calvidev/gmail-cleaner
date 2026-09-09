//  Projections.swift
//  Lo que se espera que anote cada jugador esta jornada.
//
//  Es la pieza que falta para poder decir "vas ganando pero vas a perder":
//  sin proyecciones, un marcador a mitad de domingo no significa gran cosa.
//
//  Se descarga y se guarda igual que las estadísticas: solo desde la app, en
//  el grupo de apps, y el widget lee el archivo.

import Foundation

struct Projections: Codable {
    /// player_id -> puntos proyectados para la jornada.
    var byPlayer: [String: Double]
    var season: String
    var week: Int
    var savedAt: Date

    func projected(for playerID: String) -> Double? { byPlayer[playerID] }
}

actor ProjectionStore {
    static let shared = ProjectionStore()

    private let fileName = "projections.json"
    /// Las proyecciones cambian poco dentro de una jornada: con una vez cada
    /// seis horas sobra.
    private let maxAge: TimeInterval = 60 * 60 * 6
    private var memory: Projections?

    private var fileURL: URL {
        SharedStore.containerURL.appendingPathComponent(fileName)
    }

    func cached() -> Projections? {
        if let memory { return memory }
        guard
            let data = try? Data(contentsOf: fileURL),
            let guardadas = try? SharedJSON.decoder.decode(Projections.self, from: data)
        else {
            return nil
        }
        memory = guardadas
        return guardadas
    }

    @discardableResult
    func refreshIfNeeded(season: String, week: Int) async -> Projections? {
        if let guardadas = cached(),
           guardadas.season == season,
           guardadas.week == week,
           Date().timeIntervalSince(guardadas.savedAt) < maxAge {
            return guardadas
        }

        guard
            let crudas: [String: [String: Double]] = try? await SleeperAPI.shared
                .get("/projections/nfl/regular/\(season)/\(week)")
        else {
            return cached()
        }

        // Sleeper proyecta en varios formatos; se usa PPR, que es el más común.
        // Si tu liga puntúa distinto, la proyección se desvía un poco, pero la
        // probabilidad de victoria aguanta bien esa imprecisión.
        var puntos: [String: Double] = [:]
        puntos.reserveCapacity(crudas.count)
        for (playerID, stats) in crudas {
            if let ppr = stats["pts_ppr"] ?? stats["pts_half_ppr"] ?? stats["pts_std"] {
                puntos[playerID] = ppr
            }
        }

        let nuevas = Projections(
            byPlayer: puntos, season: season, week: week, savedAt: Date()
        )
        memory = nuevas
        if let data = try? SharedJSON.encoder.encode(nuevas) {
            try? data.write(to: fileURL, options: .atomic)
        }
        return nuevas
    }
}
