//  MatchupActivity.swift
//  El contrato de la Live Activity: lo que la app manda y el sistema pinta.
//
//  El estado de una Live Activity viaja serializado y tiene un límite duro de
//  4 KB, así que aquí no van imágenes: va el id del jugador y la foto se lee
//  del grupo de apps (`HeadshotCache`), que la app deja descargada antes.

import ActivityKit
import Foundation

/// Una anotación: alguien acaba de sumar puntos.
struct ScoringPlay: Codable, Hashable, Identifiable {
    var playerID: String
    var name: String
    var position: String?
    var team: String?
    /// Puntos totales del jugador tras la jugada.
    var total: Double
    /// Lo que acaba de sumar. Es el número que importa.
    var delta: Double
    /// True si es de tu equipo (para pintarlo en verde y no en rojo).
    var isMine: Bool
    var at: Date

    var id: String { "\(playerID)-\(at.timeIntervalSince1970)" }

    var subtitle: String {
        [position, team].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " ")
    }
}

struct MatchupActivityAttributes: ActivityAttributes {
    /// Lo que cambia jugada a jugada.
    struct ContentState: Codable, Hashable {
        var myPoints: Double
        var opponentPoints: Double
        var myStarters: Int
        var opponentStarters: Int
        var lastPlay: ScoringPlay?
        var updatedAt: Date

        var difference: Double { myPoints - opponentPoints }

        var share: Double {
            let total = myPoints + opponentPoints
            guard total > 0 else { return 0.5 }
            return myPoints / total
        }
    }

    /// Lo que no cambia durante el partido.
    var leagueName: String
    var week: Int
    var myTeam: String
    var opponentTeam: String
}

extension MatchupSnapshot {
    /// Lo fijo de la Live Activity a partir del marcador.
    var activityAttributes: MatchupActivityAttributes {
        MatchupActivityAttributes(
            leagueName: leagueName,
            week: week,
            myTeam: me.name,
            opponentTeam: opponent?.name ?? "Sin rival"
        )
    }

    /// Lo variable, con la última anotación conocida.
    func activityState(lastPlay: ScoringPlay? = nil) -> MatchupActivityAttributes.ContentState {
        MatchupActivityAttributes.ContentState(
            myPoints: me.points,
            opponentPoints: opponentPoints,
            myStarters: me.startersCount,
            opponentStarters: opponent?.startersCount ?? 0,
            lastPlay: lastPlay ?? plays.first,
            updatedAt: updatedAt
        )
    }
}
