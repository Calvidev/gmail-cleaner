//  ScoringDetector.swift
//  Quién ha anotado entre dos lecturas del marcador.
//
//  Sleeper no avisa de las jugadas: da los puntos acumulados de cada titular.
//  Restando la lectura anterior sale lo que acaba de pasar.

import Foundation

enum ScoringDetector {
    /// Menos de esto no es una anotación: son ajustes de décimas que hace
    /// Sleeper al corregir estadísticas.
    static let minimumDelta = 0.1

    static func plays(
        previous: MatchupSnapshot?,
        current: MatchupSnapshot,
        at moment: Date = Date()
    ) -> [ScoringPlay] {
        guard let previous else { return [] }  // la primera lectura no anota nada

        var anteriores: [String: Double] = [:]
        for fila in previous.lineup {
            if let mine = fila.mine { anteriores[mine.playerID] = mine.points }
            if let theirs = fila.theirs { anteriores[theirs.playerID] = theirs.points }
        }

        var jugadas: [ScoringPlay] = []
        for fila in current.lineup {
            if let mine = fila.mine, let jugada = play(for: mine, isMine: true, anteriores: anteriores, at: moment) {
                jugadas.append(jugada)
            }
            if let theirs = fila.theirs, let jugada = play(for: theirs, isMine: false, anteriores: anteriores, at: moment) {
                jugadas.append(jugada)
            }
        }
        // Primero la jugada más gorda: es la que se enseña.
        return jugadas.sorted { $0.delta > $1.delta }
    }

    private static func play(
        for line: PlayerLine,
        isMine: Bool,
        anteriores: [String: Double],
        at moment: Date
    ) -> ScoringPlay? {
        // Un jugador que no estaba antes (cambio de alineación) no ha anotado.
        guard let anterior = anteriores[line.playerID] else { return nil }
        let delta = line.points - anterior
        guard delta >= minimumDelta else { return nil }
        return ScoringPlay(
            playerID: line.playerID,
            name: line.displayName,
            position: line.position,
            team: line.team,
            total: line.points,
            delta: delta,
            isMine: isMine,
            stats: line.stats,
            at: moment
        )
    }
}
