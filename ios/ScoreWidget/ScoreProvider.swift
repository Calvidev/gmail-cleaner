//  ScoreProvider.swift
//  De dónde saca el widget el marcador y cada cuánto vuelve a mirar.

import AppIntents
import Foundation
import WidgetKit

struct ScoreEntry: TimelineEntry {
    let date: Date
    let snapshot: MatchupSnapshot?
    let message: String?
}

struct ScoreProvider: AppIntentTimelineProvider {
    typealias Entry = ScoreEntry
    typealias Intent = SelectLeagueIntent

    /// Con partido en marcha se pide refresco cada diez minutos; el resto del
    /// tiempo, cada hora. Es una petición, no una promesa: iOS decide.
    private let liveInterval: TimeInterval = 60 * 10
    private let idleInterval: TimeInterval = 60 * 60

    func placeholder(in context: Context) -> ScoreEntry {
        ScoreEntry(date: Date(), snapshot: .placeholder(), message: nil)
    }

    func snapshot(for configuration: SelectLeagueIntent, in context: Context) async -> ScoreEntry {
        // La vista previa de la galería no debe salir a la red.
        if context.isPreview {
            return ScoreEntry(date: Date(), snapshot: .placeholder(), message: nil)
        }
        let guardado = SharedStore.cachedSnapshot(for: league(for: configuration))
        return ScoreEntry(date: Date(), snapshot: guardado ?? .placeholder(), message: nil)
    }

    func timeline(for configuration: SelectLeagueIntent, in context: Context) async -> Timeline<ScoreEntry> {
        let entry = await loadEntry(for: configuration)
        let interval = (entry.snapshot?.looksLive ?? false) ? liveInterval : idleInterval
        let next = Date().addingTimeInterval(interval)
        return Timeline(entries: [entry], policy: .after(next))
    }

    /// La liga elegida en este widget; si no se eligió ninguna, la activa en
    /// la app. Así dos widgets pueden seguir equipos distintos.
    private func league(for configuration: SelectLeagueIntent) -> LeagueConfig {
        SharedStore.league(withID: configuration.league?.id) ?? SharedStore.loadConfig()
    }

    private func loadEntry(for configuration: SelectLeagueIntent) async -> ScoreEntry {
        let config = league(for: configuration)
        let anterior = SharedStore.cachedSnapshot(for: config)
        do {
            var snapshot = try await MatchupService().snapshot(for: config)
            // El widget también detecta anotaciones: si no, al guardar borraría
            // las que la app había apuntado.
            let anotaciones = ScoringDetector.plays(previous: anterior, current: snapshot)
            snapshot.recentPlays = Array((anotaciones + (anterior?.plays ?? [])).prefix(6))
            SharedStore.cache(snapshot, for: config)
            return ScoreEntry(date: Date(), snapshot: snapshot, message: nil)
        } catch {
            // Sin red se enseña lo último bueno, marcado como viejo.
            if var stale = anterior {
                stale.isStale = true
                return ScoreEntry(date: Date(), snapshot: stale, message: nil)
            }
            return ScoreEntry(date: Date(), snapshot: nil, message: error.localizedDescription)
        }
    }
}
