//  GameStatus.swift
//  Qué partidos de la NFL han terminado ya.
//
//  Sin esto, la proyección de un equipo sigue contando lo que "le queda por
//  anotar" a un jugador cuyo partido acabó hace horas. Es justo lo que hacía
//  que la proyección saliera alta: Kittle proyectaba 10.06, hizo 3.20 y su
//  partido estaba cerrado, pero se le seguían suponiendo 6.86 puntos más.
//
//  Sleeper no dice si el partido ha acabado, así que se pregunta al marcador
//  público de ESPN, que es la misma fuente que ya usa la herramienta web.

import Foundation

struct GameStatus: Codable {
    /// Abreviaturas de los equipos cuyo partido ya ha terminado.
    var finishedTeams: Set<String>
    /// Equipos que están jugando ahora mismo.
    var playingTeams: Set<String>
    var savedAt: Date

    func hasFinished(_ team: String?) -> Bool {
        guard let team, !team.isEmpty else { return false }
        return finishedTeams.contains(GameStatus.normalize(team))
    }

    /// ESPN y Sleeper no escriben igual todas las abreviaturas.
    static func normalize(_ team: String) -> String {
        let alias = [
            "WSH": "WAS", "JAC": "JAX", "LA": "LAR",
            "SD": "LAC", "OAK": "LV", "STL": "LAR",
        ]
        let mayus = team.uppercased()
        return alias[mayus] ?? mayus
    }
}

actor GameStatusStore {
    static let shared = GameStatusStore()

    private let endpoint = URL(
        string: "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    )!
    private let fileName = "game-status.json"
    /// En domingo esto cambia cada pocos minutos.
    private let maxAge: TimeInterval = 180
    private var memory: GameStatus?

    private var fileURL: URL {
        SharedStore.containerURL.appendingPathComponent(fileName)
    }

    func cached() -> GameStatus? {
        if let memory { return memory }
        guard
            let data = try? Data(contentsOf: fileURL),
            let guardado = try? SharedJSON.decoder.decode(GameStatus.self, from: data)
        else {
            return nil
        }
        memory = guardado
        return guardado
    }

    @discardableResult
    func refreshIfNeeded() async -> GameStatus? {
        if let guardado = cached(), Date().timeIntervalSince(guardado.savedAt) < maxAge {
            return guardado
        }
        guard let data = try? await SleeperAPI.shared.download(endpoint) else {
            return cached()
        }
        guard let nuevo = Self.parse(data) else { return cached() }

        memory = nuevo
        if let codificado = try? SharedJSON.encoder.encode(nuevo) {
            try? codificado.write(to: fileURL, options: .atomic)
        }
        return nuevo
    }

    // MARK: - Parseo del marcador de ESPN

    private struct Respuesta: Decodable {
        struct Evento: Decodable {
            struct Competicion: Decodable {
                struct Competidor: Decodable {
                    struct Equipo: Decodable { let abbreviation: String? }
                    let team: Equipo?
                }
                struct Estado: Decodable {
                    struct Tipo: Decodable {
                        let completed: Bool?
                        let state: String?  // "pre", "in", "post"
                    }
                    let type: Tipo?
                }
                let competitors: [Competidor]?
                let status: Estado?
            }
            let competitions: [Competicion]?
        }
        let events: [Evento]?
    }

    static func parse(_ data: Data) -> GameStatus? {
        guard let respuesta = try? JSONDecoder().decode(Respuesta.self, from: data) else {
            return nil
        }
        var terminados = Set<String>()
        var jugando = Set<String>()

        for evento in respuesta.events ?? [] {
            for competicion in evento.competitions ?? [] {
                let tipo = competicion.status?.type
                let acabado = tipo?.completed == true || tipo?.state == "post"
                let enJuego = tipo?.state == "in"
                guard acabado || enJuego else { continue }

                for competidor in competicion.competitors ?? [] {
                    guard let abreviatura = competidor.team?.abbreviation else { continue }
                    let normalizada = GameStatus.normalize(abreviatura)
                    if acabado {
                        terminados.insert(normalizada)
                    } else {
                        jugando.insert(normalizada)
                    }
                }
            }
        }
        return GameStatus(finishedTeams: terminados, playingTeams: jugando, savedAt: Date())
    }
}
