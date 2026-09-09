//  HeadshotCache.swift
//  Fotos de los jugadores, guardadas en el grupo de apps.
//
//  El widget y la Live Activity no pueden salir a la red mientras pintan, así
//  que la app descarga las fotos y ellos leen el archivo. Misma idea que
//  `AvatarLoader`, pero indexado por jugador.

import Foundation

enum HeadshotCache {
    private static let folderName = "Headshots"
    private static let maxAge: TimeInterval = 60 * 60 * 24 * 30  // un mes

    private static var folderURL: URL {
        let url = SharedStore.containerURL.appendingPathComponent(folderName, isDirectory: true)
        if !FileManager.default.fileExists(atPath: url.path) {
            try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        }
        return url
    }

    /// La foto de Sleeper. Las defensas no tienen cara: se usa el escudo.
    static func remoteURL(playerID: String, position: String?, team: String?) -> URL? {
        if position?.uppercased() == "DEF" {
            guard let team, !team.isEmpty else { return nil }
            return URL(string: "https://sleepercdn.com/images/team_logos/nfl/\(team.lowercased()).png")
        }
        guard playerID.allSatisfy({ $0.isNumber }), !playerID.isEmpty else { return nil }
        return URL(string: "https://sleepercdn.com/content/nfl/players/thumb/\(playerID).jpg")
    }

    static func fileURL(playerID: String) -> URL {
        folderURL.appendingPathComponent("\(stableHash(playerID)).img")
    }

    /// Lectura sin red: es lo único que pueden hacer el widget y la Live Activity.
    static func cachedData(playerID: String) -> Data? {
        try? Data(contentsOf: fileURL(playerID: playerID))
    }

    /// Descarga la foto si no está o si ha caducado. No lanza nunca.
    @discardableResult
    static func prefetch(playerID: String, position: String?, team: String?) async -> Data? {
        let destino = fileURL(playerID: playerID)
        if let atributos = try? FileManager.default.attributesOfItem(atPath: destino.path),
           let modificado = atributos[.modificationDate] as? Date,
           Date().timeIntervalSince(modificado) < maxAge,
           let datos = try? Data(contentsOf: destino) {
            return datos
        }
        guard
            let url = remoteURL(playerID: playerID, position: position, team: team),
            let datos = try? await SleeperAPI.shared.download(url)
        else {
            return try? Data(contentsOf: destino)
        }
        try? datos.write(to: destino, options: .atomic)
        return datos
    }

    /// Se piden todas a la vez, de cuatro en cuatro para no saturar la red.
    static func prefetch(lineup: [LineupRow]) async {
        var pendientes: [PlayerLine] = []
        for fila in lineup {
            if let mine = fila.mine { pendientes.append(mine) }
            if let theirs = fila.theirs { pendientes.append(theirs) }
        }
        await withTaskGroup(of: Void.self) { grupo in
            var enCurso = 0
            for jugador in pendientes {
                if enCurso >= 4 {
                    _ = await grupo.next()
                    enCurso -= 1
                }
                grupo.addTask {
                    await prefetch(
                        playerID: jugador.playerID,
                        position: jugador.position,
                        team: jugador.team
                    )
                }
                enCurso += 1
            }
        }
    }
}
