//  InjuryWatcher.swift
//  Cambios en el parte de lesiones de tus titulares.
//
//  Sleeper no publica un endpoint ligero de lesiones: el estado de cada
//  jugador viene dentro del catálogo. Así que esto compara el catálogo nuevo
//  con lo último que se vio de TUS jugadores (un archivo diminuto) y devuelve
//  solo lo que ha cambiado.

import Foundation

struct InjuryChange: Codable, Hashable, Identifiable {
    var playerID: String
    var name: String
    var position: String?
    var team: String?
    /// Nil significa "sano".
    var before: String?
    var after: String?
    var at: Date

    var id: String { "\(playerID)-\(at.timeIntervalSince1970)" }

    /// Un parte que empeora es el que urge: de sano a duda, de duda a fuera.
    var isWorse: Bool {
        Self.severity(after) > Self.severity(before)
    }

    var headline: String {
        if after == nil { return "\(name) está sano" }
        if before == nil { return "\(name): \(Self.label(after))" }
        return "\(name): \(Self.label(before)) → \(Self.label(after))"
    }

    static func label(_ status: String?) -> String {
        switch (status ?? "").uppercased() {
        case "": return "Sano"
        case "QUESTIONABLE", "Q": return "Duda"
        case "DOUBTFUL", "D": return "Muy dudoso"
        case "OUT", "O": return "Fuera"
        case "IR": return "Lista de lesionados"
        case "PUP": return "PUP"
        case "SUS": return "Sancionado"
        case "NA": return "No disponible"
        default: return status ?? "Sano"
        }
    }

    /// Para saber si el cambio es a peor.
    static func severity(_ status: String?) -> Int {
        switch (status ?? "").uppercased() {
        case "": return 0
        case "QUESTIONABLE", "Q": return 1
        case "DOUBTFUL", "D": return 2
        case "OUT", "O": return 3
        case "SUS", "NA", "PUP": return 4
        case "IR": return 5
        default: return 1
        }
    }
}

enum InjuryWatcher {
    private static let fileName = "injury-status.json"

    private static var fileURL: URL {
        SharedStore.containerURL.appendingPathComponent(fileName)
    }

    private static func saved() -> [String: String] {
        guard
            let data = try? Data(contentsOf: fileURL),
            let guardados = try? SharedJSON.decoder.decode([String: String].self, from: data)
        else {
            return [:]
        }
        return guardados
    }

    private static func save(_ estados: [String: String]) {
        guard let data = try? SharedJSON.encoder.encode(estados) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }

    /// Compara el catálogo con lo último visto de los jugadores del marcador.
    /// La primera vez no avisa de nada: solo toma nota.
    static func changes(
        in snapshot: MatchupSnapshot,
        catalog: [String: CatalogPlayer],
        at moment: Date = Date()
    ) -> [InjuryChange] {
        guard !catalog.isEmpty else { return [] }

        // Solo interesan los jugadores que ves en el marcador.
        var mios: [String] = []
        for fila in snapshot.lineup {
            if let mine = fila.mine { mios.append(mine.playerID) }
            if let theirs = fila.theirs { mios.append(theirs.playerID) }
        }

        let anteriores = saved()
        // Se parte de lo que ya había: con varias ligas, quedarse solo con los
        // jugadores de la liga que miras ahora haría que los de la otra
        // parecieran nuevos al volver, y avisaría de cambios que no existen.
        var actuales = anteriores
        var cambios: [InjuryChange] = []

        for playerID in mios {
            guard let jugador = catalog[playerID] else { continue }
            let estado = jugador.injuryStatus ?? ""
            let anterior = anteriores[playerID]
            actuales[playerID] = estado

            // Un jugador que no habíamos visto nunca solo se apunta: su estado
            // actual no es una noticia.
            guard let anterior, anterior != estado else { continue }
            cambios.append(
                InjuryChange(
                    playerID: playerID,
                    name: jugador.name,
                    position: jugador.position,
                    team: jugador.team,
                    before: anterior.isEmpty ? nil : anterior,
                    after: estado.isEmpty ? nil : estado,
                    at: moment
                )
            )
        }

        save(actuales)
        return cambios
    }
}
