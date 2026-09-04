//  ScoreProvider.swift
//  De dónde saca el widget el marcador y cada cuánto vuelve a mirar.

import Foundation
import WidgetKit

struct ScoreEntry: TimelineEntry {
    let date: Date
    let snapshot: MatchupSnapshot?
    let message: String?
}

struct ScoreProvider: TimelineProvider {
    /// Con partido en marcha se pide refresco cada diez minutos; el resto del
    /// tiempo, cada hora. Es una petición, no una promesa: iOS decide.
    private let liveInterval: TimeInterval = 60 * 10
    private let idleInterval: TimeInterval = 60 * 60

    func placeholder(in context: Context) -> ScoreEntry {
        ScoreEntry(date: Date(), snapshot: .placeholder(), message: nil)
    }

    func getSnapshot(in context: Context, completion: @escaping (ScoreEntry) -> Void) {
        // La vista previa de la galería no debe salir a la red.
        if context.isPreview {
            completion(ScoreEntry(date: Date(), snapshot: .placeholder(), message: nil))
            return
        }
        let cached = SharedStore.cachedSnapshot() ?? .placeholder()
        completion(ScoreEntry(date: Date(), snapshot: cached, message: nil))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<ScoreEntry>) -> Void) {
        Task {
            let entry = await loadEntry()
            let interval = (entry.snapshot?.looksLive ?? false) ? liveInterval : idleInterval
            let next = Date().addingTimeInterval(interval)
            completion(Timeline(entries: [entry], policy: .after(next)))
        }
    }

    private func loadEntry() async -> ScoreEntry {
        let config = SharedStore.loadConfig()
        do {
            let snapshot = try await MatchupService().snapshot(for: config)
            SharedStore.cache(snapshot)
            return ScoreEntry(date: Date(), snapshot: snapshot, message: nil)
        } catch {
            // Sin red se enseña lo último bueno, marcado como viejo.
            if let stale = SharedStore.staleSnapshot() {
                return ScoreEntry(date: Date(), snapshot: stale, message: nil)
            }
            return ScoreEntry(date: Date(), snapshot: nil, message: error.localizedDescription)
        }
    }
}
