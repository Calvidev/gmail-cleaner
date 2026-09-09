//  HostKind.swift
//  Las plataformas de fantasy que la app conoce (o conocerá).

import SwiftUI

enum HostKind: String, Codable, CaseIterable, Identifiable {
    case sleeper
    case yahoo
    case espn
    case nfl

    var id: String { rawValue }

    var title: String {
        switch self {
        case .sleeper: return "Sleeper"
        case .yahoo: return "Yahoo Fantasy"
        case .espn: return "ESPN Fantasy"
        case .nfl: return "NFL.com"
        }
    }

    /// Lo que hay que hacer para entrar, en una línea.
    var tagline: String {
        switch self {
        case .sleeper: return "Con tu nombre de usuario, sin contraseña"
        case .yahoo: return "Iniciar sesión con tu cuenta de Yahoo"
        case .espn: return "Necesita las cookies de tu sesión"
        case .nfl: return "Su API no es pública"
        }
    }

    var symbol: String {
        switch self {
        case .sleeper: return "moon.zzz.fill"
        case .yahoo: return "y.circle.fill"
        case .espn: return "e.circle.fill"
        case .nfl: return "football.fill"
        }
    }

    var accent: Color {
        switch self {
        case .sleeper: return Theme.accent
        case .yahoo: return Color(hex: "7B5CFF")
        case .espn: return Color(hex: "C8102E")
        case .nfl: return Color(hex: "3A75C4")
        }
    }

    /// Los dos que aún no están integrados salen apagados en el menú.
    var isAvailable: Bool {
        switch self {
        case .sleeper, .yahoo: return true
        case .espn, .nfl: return false
        }
    }
}

/// Una cuenta conectada, para pintar el menú sin volver a preguntar a nadie.
struct HostConnection: Codable, Equatable {
    var host: HostKind
    var accountName: String
    var connectedAt: Date
}
