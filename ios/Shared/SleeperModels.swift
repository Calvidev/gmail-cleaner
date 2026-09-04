//  SleeperModels.swift
//  Lo mínimo que hace falta de cada respuesta de la API de Sleeper.
//
//  Todas las claves se declaran a mano (nada de `convertFromSnakeCase`) para
//  que se vea de un vistazo qué campo del JSON alimenta a cada propiedad.

import Foundation

// MARK: - Estado de la temporada

struct NFLState: Decodable {
    let season: String?
    let seasonType: String?
    let week: Int?
    let displayWeek: Int?

    enum CodingKeys: String, CodingKey {
        case season
        case week
        case seasonType = "season_type"
        case displayWeek = "display_week"
    }

    /// La jornada que Sleeper enseña en su app. En pretemporada `display_week`
    /// puede llegar a 0, y una jornada 0 no existe: se corrige a 1.
    var currentWeek: Int {
        max(1, displayWeek ?? week ?? 1)
    }
}

// MARK: - Liga

struct League: Decodable {
    let leagueID: String?
    let name: String?
    let avatar: String?
    let season: String?
    let rosterPositions: [String]?

    enum CodingKeys: String, CodingKey {
        case leagueID = "league_id"
        case name
        case avatar
        case season
        case rosterPositions = "roster_positions"
    }

    /// Los huecos de la alineación titular, en el orden en que Sleeper los
    /// coloca: es el mismo orden del array `starters` de cada equipo.
    var starterSlots: [String] {
        (rosterPositions ?? []).filter { !["BN", "IR", "TAXI"].contains($0.uppercased()) }
    }
}

struct LeagueUser: Decodable, Identifiable {
    let userID: String
    let displayName: String?
    let avatar: String?
    let teamName: String?

    var id: String { userID }

    /// El nombre que el manager le ha puesto a su equipo; si no tiene, su
    /// nombre de usuario.
    var preferredName: String {
        if let teamName, !teamName.isEmpty { return teamName }
        if let displayName, !displayName.isEmpty { return displayName }
        return "Equipo"
    }

    var avatarURL: URL? {
        guard let avatar, !avatar.isEmpty else { return nil }
        return URL(string: "https://sleepercdn.com/avatars/thumbs/\(avatar)")
    }

    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case displayName = "display_name"
        case avatar
        case metadata
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        userID = try container.decode(String.self, forKey: .userID)
        displayName = try container.decodeIfPresent(String.self, forKey: .displayName)
        avatar = try container.decodeIfPresent(String.self, forKey: .avatar)
        // `metadata` es un cajón de sastre y no siempre trae solo textos, así
        // que se lee con tolerancia y solo se rescata el nombre del equipo.
        let metadata = try? container.decodeIfPresent(LenientStringDictionary.self, forKey: .metadata)
        teamName = metadata??.values["team_name"]
    }
}

struct RosterSettings: Decodable {
    let wins: Int?
    let losses: Int?
    let ties: Int?
}

struct Roster: Decodable {
    let rosterID: Int
    let ownerID: String?
    let players: [String]?
    let starters: [String]?
    let settings: RosterSettings?

    enum CodingKeys: String, CodingKey {
        case rosterID = "roster_id"
        case ownerID = "owner_id"
        case players
        case starters
        case settings
    }

    /// "3-1" o "3-1-1" cuando hay empates.
    var record: String? {
        guard let settings else { return nil }
        let wins = settings.wins ?? 0
        let losses = settings.losses ?? 0
        let ties = settings.ties ?? 0
        if wins == 0 && losses == 0 && ties == 0 { return nil }
        return ties > 0 ? "\(wins)-\(losses)-\(ties)" : "\(wins)-\(losses)"
    }
}

// MARK: - Enfrentamiento de la jornada

struct Matchup: Decodable {
    let rosterID: Int
    let matchupID: Int?
    let points: Double?
    let starters: [String]?
    let startersPoints: [Double]?
    let playersPoints: [String: Double]?

    enum CodingKeys: String, CodingKey {
        case rosterID = "roster_id"
        case matchupID = "matchup_id"
        case points
        case starters
        case startersPoints = "starters_points"
        case playersPoints = "players_points"
    }

    /// Titulares de verdad: Sleeper rellena con "0" los huecos vacíos.
    var filledStarters: [String] {
        (starters ?? []).filter { $0 != "0" && !$0.isEmpty }
    }

    /// Puntos del titular que ocupa el hueco `index`.
    func pointsForSlot(_ index: Int) -> Double {
        if let startersPoints, index < startersPoints.count {
            return startersPoints[index]
        }
        if let starters, index < starters.count, let playersPoints {
            return playersPoints[starters[index]] ?? 0
        }
        return 0
    }
}

// MARK: - Catálogo de jugadores

/// Una entrada del catálogo `/players/nfl` tal como llega (pesa ~5 MB entero).
struct RawCatalogPlayer: Decodable {
    let fullName: String?
    let firstName: String?
    let lastName: String?
    let position: String?
    let team: String?

    enum CodingKeys: String, CodingKey {
        case fullName = "full_name"
        case firstName = "first_name"
        case lastName = "last_name"
        case position
        case team
    }
}

/// Lo que guardamos de cada jugador (unos pocos cientos de KB en disco).
struct CatalogPlayer: Codable, Hashable {
    let name: String
    let position: String?
    let team: String?
}
