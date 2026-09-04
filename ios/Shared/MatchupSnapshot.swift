//  MatchupSnapshot.swift
//  La foto del enfrentamiento: lo único que la app y el widget pintan.
//
//  Es `Codable` a propósito. Se guarda entera en el grupo de apps, así que el
//  widget puede enseñar el último marcador conocido aunque no haya red.

import Foundation

struct TeamSide: Codable, Hashable, Identifiable {
    var rosterID: Int
    var name: String
    var avatarURL: URL?
    var avatarData: Data?
    var points: Double
    var startersCount: Int
    var record: String?

    var id: Int { rosterID }
}

struct PlayerLine: Codable, Hashable {
    var playerID: String
    var points: Double
    var name: String?
    var position: String?
    var team: String?

    /// "T. Hill · WR KC" cuando hay catálogo; si no, algo legible igualmente.
    var subtitle: String {
        [position, team].compactMap { $0 }.joined(separator: " ")
    }

    var displayName: String {
        if let name, !name.isEmpty { return name }
        return "Jugador \(playerID)"
    }
}

/// Un hueco de la alineación con los dos jugadores que lo ocupan.
struct LineupRow: Codable, Hashable, Identifiable {
    var index: Int
    var slot: String
    var mine: PlayerLine?
    var theirs: PlayerLine?

    var id: Int { index }

    var slotLabel: String {
        switch slot.uppercased() {
        case "SUPER_FLEX": return "SFLX"
        case "REC_FLEX": return "RFLX"
        case "IDP_FLEX": return "IDP"
        default: return slot.uppercased()
        }
    }
}

struct MatchupSnapshot: Codable, Hashable {
    var leagueName: String
    var week: Int
    var me: TeamSide
    var opponent: TeamSide?
    var lineup: [LineupRow]
    var updatedAt: Date
    /// True cuando estos datos salen de la caché porque la descarga falló.
    var isStale: Bool

    var opponentPoints: Double { opponent?.points ?? 0 }

    var difference: Double { me.points - opponentPoints }

    /// Parte de la barra que ocupa mi equipo. Con 0-0 se pinta a la mitad.
    var myShare: Double {
        let total = me.points + opponentPoints
        guard total > 0 else { return 0.5 }
        return me.points / total
    }

    var isLeading: Bool { difference >= 0 }

    /// Hay partido en marcha (algo se está moviendo): sirve para decidir cada
    /// cuánto pedirle a WidgetKit que refresque.
    var looksLive: Bool { me.points > 0 || opponentPoints > 0 }

    static func placeholder() -> MatchupSnapshot {
        MatchupSnapshot(
            leagueName: "Tu liga de Sleeper",
            week: 1,
            me: TeamSide(
                rosterID: 1, name: "Tu equipo", avatarURL: nil, avatarData: nil,
                points: 88.4, startersCount: 9, record: "3-1"
            ),
            opponent: TeamSide(
                rosterID: 2, name: "Rival", avatarURL: nil, avatarData: nil,
                points: 74.2, startersCount: 9, record: "2-2"
            ),
            lineup: [],
            updatedAt: Date(),
            isStale: false
        )
    }
}

extension Double {
    /// Los puntos de fantasy se leen siempre con un decimal.
    var fantasyPoints: String {
        String(format: "%.1f", self)
    }

    var signedFantasyPoints: String {
        (self >= 0 ? "+" : "") + fantasyPoints
    }
}
