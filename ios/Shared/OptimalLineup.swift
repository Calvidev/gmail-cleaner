//  OptimalLineup.swift
//  La mejor alineación que podrías haber puesto, y lo que costó no ponerla.
//
//  Es el dato que más duele y más se mira: "dejaste 23,4 puntos en el
//  banquillo". Sale de comparar tus titulares con la mejor combinación posible
//  de toda tu plantilla en los huecos de tu liga.

import Foundation

struct BenchReport: Codable, Hashable {
    /// Lo que sumaron tus titulares.
    var actual: Double
    /// Lo que habría sumado la mejor alineación posible.
    var best: Double
    /// Jugadores del banquillo que debieron jugar, con lo que anotaron.
    var missed: [PlayerLine]

    /// Nunca negativo: si alineaste lo mejor posible, es cero.
    var pointsLeft: Double { max(0, best - actual) }

    var perfect: Bool { pointsLeft < 0.05 }
}

enum OptimalLineup {
    /// Qué posiciones acepta cada hueco.
    static func eligible(_ slot: String) -> Set<String> {
        switch slot.uppercased() {
        case "QB": return ["QB"]
        case "RB": return ["RB"]
        case "WR": return ["WR"]
        case "TE": return ["TE"]
        case "K": return ["K"]
        case "DEF", "DST": return ["DEF"]
        case "FLEX": return ["RB", "WR", "TE"]
        case "WRRB_FLEX": return ["RB", "WR"]
        case "REC_FLEX": return ["WR", "TE"]
        case "SUPER_FLEX": return ["QB", "RB", "WR", "TE"]
        default: return ["QB", "RB", "WR", "TE"]
        }
    }

    /// La mejor combinación posible.
    ///
    /// Se rellenan antes los huecos más exigentes (un QB solo cabe en QB) y
    /// dentro de cada uno se coge al que más anotó. Con las alineaciones de
    /// fantasy —pocos huecos y poca solapa— esto da el óptimo real.
    static func best(
        players: [PlayerLine],
        slots: [String]
    ) -> (total: Double, chosen: [PlayerLine]) {
        var disponibles = players.sorted { $0.points > $1.points }
        var elegidos: [PlayerLine] = []

        let ordenados = slots.sorted { eligible($0).count < eligible($1).count }
        for hueco in ordenados {
            let acepta = eligible(hueco)
            guard
                let indice = disponibles.firstIndex(where: {
                    acepta.contains(($0.position ?? "").uppercased())
                })
            else { continue }
            elegidos.append(disponibles.remove(at: indice))
        }
        return (elegidos.reduce(0) { $0 + $1.points }, elegidos)
    }

    /// Compara lo que alineaste con lo mejor posible.
    static func report(
        starters: [PlayerLine],
        bench: [PlayerLine],
        slots: [String]
    ) -> BenchReport? {
        guard !slots.isEmpty, !bench.isEmpty else { return nil }

        let actual = starters.reduce(0) { $0 + $1.points }
        let mejor = best(players: starters + bench, slots: slots)

        // Los del banquillo que sí entraban en la mejor alineación.
        let idsTitulares = Set(starters.map(\.playerID))
        let perdidos = mejor.chosen
            .filter { !idsTitulares.contains($0.playerID) }
            .sorted { $0.points > $1.points }

        return BenchReport(actual: actual, best: mejor.total, missed: perdidos)
    }
}
