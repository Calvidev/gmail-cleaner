//  LeagueIntent.swift
//  Elegir qué liga enseña cada widget.
//
//  Con esto, dos widgets en la misma pantalla pueden seguir equipos distintos:
//  se elige al mantener pulsado el widget > Editar widget. Es lo que hace útil
//  el plan Pro cuando sigues más de una liga.

import AppIntents
import WidgetKit

struct LeagueEntity: AppEntity, Identifiable {
    var id: String
    var name: String
    var team: String?

    static var typeDisplayRepresentation: TypeDisplayRepresentation { "Liga" }

    var displayRepresentation: DisplayRepresentation {
        if let team, !team.isEmpty {
            return DisplayRepresentation(title: "\(name)", subtitle: "\(team)")
        }
        return DisplayRepresentation(title: "\(name)")
    }

    static var defaultQuery = LeagueQuery()
}

struct LeagueQuery: EntityQuery {
    func entities(for identifiers: [LeagueEntity.ID]) async throws -> [LeagueEntity] {
        todas().filter { identifiers.contains($0.id) }
    }

    /// Lo que se ofrece en el desplegable al editar el widget.
    func suggestedEntities() async throws -> [LeagueEntity] {
        todas()
    }

    private func todas() -> [LeagueEntity] {
        SharedStore.loadBook().leagues.map {
            LeagueEntity(id: $0.id, name: $0.displayName, team: $0.teamName)
        }
    }
}

struct SelectLeagueIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource { "Elegir liga" }
    static var description: IntentDescription {
        IntentDescription("Qué liga enseña este widget.")
    }

    /// Sin elegir nada, el widget sigue la liga activa en la app.
    @Parameter(title: "Liga")
    var league: LeagueEntity?

    init() {}
}
