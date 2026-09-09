//  ScoreboardModel.swift
//  Estado del marcador: descarga, caché, refresco automático y widgets.

import Foundation
import SwiftUI
import WidgetKit

@MainActor
final class ScoreboardModel: ObservableObject {
    @Published private(set) var snapshot: MatchupSnapshot?
    @Published private(set) var isLoading = false
    @Published private(set) var lastError: String?
    @Published private(set) var config: LeagueConfig

    private let service = MatchupService()
    private let live = LiveActivityController.shared
    private var refreshTask: Task<Void, Never>?

    init() {
        config = SharedStore.loadConfig()
        // Se arranca con lo último que se vio: la pantalla nunca aparece vacía.
        snapshot = SharedStore.cachedSnapshot()
    }

    var needsSetup: Bool { !config.isComplete }

    // MARK: - Descarga

    func refresh(showSpinner: Bool = true) async {
        guard config.isComplete else { return }
        if showSpinner { isLoading = true }
        defer { isLoading = false }

        do {
            var fresh = try await service.snapshot(for: config)

            // Lo que ha pasado desde la última lectura: quién ha anotado.
            let anotaciones = ScoringDetector.plays(previous: snapshot, current: fresh)
            fresh.recentPlays = Array((anotaciones + (snapshot?.plays ?? [])).prefix(6))

            snapshot = fresh
            lastError = nil
            SharedStore.cache(fresh)
            WidgetCenter.shared.reloadAllTimelines()

            // Las fotos, en disco, para el widget y la Live Activity.
            Task { await HeadshotCache.prefetch(lineup: fresh.lineup) }

            live.update(with: fresh, play: anotaciones.first)
            // Si tres jugadores anotan a la vez, tres avisos son demasiados.
            for anotacion in anotaciones.prefix(3) {
                await live.notify(anotacion)
            }
        } catch {
            lastError = error.localizedDescription
            // Si no había nada en pantalla, al menos se enseña lo guardado.
            if snapshot == nil { snapshot = SharedStore.staleSnapshot() }
            else { snapshot?.isStale = true }
        }
    }

    /// Los nombres de la alineación vienen del catálogo; se pone al día en
    /// segundo plano y luego se vuelve a montar el marcador ya con nombres.
    func refreshCatalogIfNeeded() async {
        let stale = await PlayerCatalog.shared.isStale
        guard stale else { return }
        await PlayerCatalog.shared.refreshIfNeeded()
        await refresh(showSpinner: false)
    }

    func forceCatalogRefresh() async {
        isLoading = true
        defer { isLoading = false }
        await PlayerCatalog.shared.refreshIfNeeded(force: true)
        await refresh(showSpinner: false)
    }

    // MARK: - Live Activity

    var isLiveActivityRunning: Bool { live.isRunning }

    var canStartLiveActivity: Bool { live.areActivitiesEnabled }

    func startLiveActivity() async {
        guard let snapshot else { return }
        await live.requestNotificationPermission()
        live.start(with: snapshot)
        objectWillChange.send()
    }

    func stopLiveActivity() {
        live.stop()
        objectWillChange.send()
    }

    // MARK: - Ajustes

    func update(config newConfig: LeagueConfig) {
        config = newConfig
        SharedStore.save(newConfig)
        snapshot = nil
        WidgetCenter.shared.reloadAllTimelines()
        Task { await refresh() }
    }

    // MARK: - Refresco automático

    func startAutoRefresh() {
        stopAutoRefresh()
        refreshTask = Task { [weak self] in
            guard let self else { return }
            await self.refresh(showSpinner: self.snapshot == nil)
            await self.refreshCatalogIfNeeded()
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: AppConfig.foregroundRefreshSeconds * 1_000_000_000)
                if Task.isCancelled { return }
                await self.refresh(showSpinner: false)
            }
        }
    }

    func stopAutoRefresh() {
        refreshTask?.cancel()
        refreshTask = nil
    }
}
