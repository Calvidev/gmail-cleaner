//  SeasonHistory.swift
//  Tu temporada jornada a jornada.
//
//  Cada jornada cerrada ya no cambia, así que se guarda y no se vuelve a pedir:
//  al final de la temporada son 17 llamadas hechas una sola vez.

import Foundation

struct WeekResult: Codable, Hashable, Identifiable {
    var week: Int
    var points: Double
    var opponentPoints: Double?
    var opponentName: String?

    var id: Int { week }

    /// Nil en las jornadas de descanso.
    var won: Bool? {
        guard let opponentPoints else { return nil }
        return points > opponentPoints
    }
}

struct SeasonHistory: Codable, Hashable {
    var leagueID: String
    var rosterID: Int
    var season: String
    var weeks: [WeekResult]
    var savedAt: Date

    var played: [WeekResult] { weeks.filter { $0.points > 0 } }

    var average: Double {
        let jugadas = played
        guard !jugadas.isEmpty else { return 0 }
        return jugadas.reduce(0) { $0 + $1.points } / Double(jugadas.count)
    }

    var best: WeekResult? { played.max { $0.points < $1.points } }
    var worst: WeekResult? { played.min { $0.points < $1.points } }

    var record: (wins: Int, losses: Int) {
        played.reduce(into: (0, 0)) { cuenta, jornada in
            switch jornada.won {
            case true?: cuenta.0 += 1
            case false?: cuenta.1 += 1
            default: break
            }
        }
    }
}

actor SeasonHistoryStore {
    static let shared = SeasonHistoryStore()

    private let maxAge: TimeInterval = 60 * 30
    private var memory: [String: SeasonHistory] = [:]

    private func fileURL(for league: LeagueConfig) -> URL {
        SharedStore.containerURL
            .appendingPathComponent("history-\(stableHash(league.id)).json")
    }

    func cached(for league: LeagueConfig) -> SeasonHistory? {
        if let guardada = memory[league.id] { return guardada }
        guard
            let data = try? Data(contentsOf: fileURL(for: league)),
            let historia = try? SharedJSON.decoder.decode(SeasonHistory.self, from: data)
        else {
            return nil
        }
        memory[league.id] = historia
        return historia
    }

    /// Descarga las jornadas que falten. Las ya guardadas no se vuelven a pedir.
    @discardableResult
    func refresh(
        league: LeagueConfig,
        season: String,
        upTo week: Int,
        api: SleeperAPI = .shared
    ) async -> SeasonHistory? {
        let guardada = cached(for: league)
        if let guardada,
           guardada.season == season,
           guardada.weeks.count >= week,
           Date().timeIntervalSince(guardada.savedAt) < maxAge {
            return guardada
        }

        // Las jornadas cerradas no cambian: solo se piden las que faltan y la
        // actual, que sí se mueve.
        var resultados: [Int: WeekResult] = [:]
        for anterior in guardada?.weeks ?? [] where anterior.week < week {
            resultados[anterior.week] = anterior
        }

        for jornada in 1...max(1, week) where resultados[jornada] == nil || jornada == week {
            guard
                let matchups = try? await api.matchups(leagueID: league.leagueID, week: jornada),
                let mio = matchups.first(where: { $0.rosterID == league.rosterID })
            else { continue }

            let rival = matchups.first {
                $0.rosterID != mio.rosterID && $0.matchupID != nil && $0.matchupID == mio.matchupID
            }
            resultados[jornada] = WeekResult(
                week: jornada,
                points: mio.points ?? 0,
                opponentPoints: rival?.points,
                opponentName: nil
            )
        }

        let historia = SeasonHistory(
            leagueID: league.leagueID,
            rosterID: league.rosterID,
            season: season,
            weeks: resultados.values.sorted { $0.week < $1.week },
            savedAt: Date()
        )
        memory[league.id] = historia
        if let data = try? SharedJSON.encoder.encode(historia) {
            try? data.write(to: fileURL(for: league), options: .atomic)
        }
        return historia
    }
}
