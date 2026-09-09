//  Entitlements.swift
//  Qué desbloquea el plan de cada usuario.
//
//  Hoy el plan se guarda en local y no hay compra de verdad: esto es el hueco
//  donde entrará StoreKit. Está aparte a propósito, para que el día que haya
//  suscripción no haya que tocar ni la interfaz ni el modelo, solo esta pieza.

import Foundation

enum Plan: String, Codable, CaseIterable {
    case free
    case pro

    var title: String {
        switch self {
        case .free: return "Gratis"
        case .pro: return "Pro"
        }
    }
}

struct Entitlements: Codable, Equatable {
    var plan: Plan = .free

    /// El gratis lleva un equipo; el Pro, todos los que quieras.
    var maxLeagues: Int { plan == .pro ? 20 : 1 }

    var allowsMultiplePlatforms: Bool { plan == .pro }

    func canAddLeague(current: Int) -> Bool { current < maxLeagues }
}

enum EntitlementStore {
    private static let key = "entitlements"

    static var current: Entitlements {
        guard
            let data = SharedStore.defaults.data(forKey: key),
            let guardadas = try? SharedJSON.decoder.decode(Entitlements.self, from: data)
        else {
            return Entitlements()
        }
        return guardadas
    }

    static func set(plan: Plan) {
        var actuales = current
        actuales.plan = plan
        guard let data = try? SharedJSON.encoder.encode(actuales) else { return }
        SharedStore.defaults.set(data, forKey: key)
    }
}
