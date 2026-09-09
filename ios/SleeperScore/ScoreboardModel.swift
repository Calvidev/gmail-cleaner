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
    /// True mientras corre el partido de mentira del menú de pruebas.
    @Published private(set) var isSimulating = false

    private let service = MatchupService()
    private let live = LiveActivityController.shared
    private var refreshTask: Task<Void, Never>?
    private var simulationTask: Task<Void, Never>?

    init() {
        config = SharedStore.loadConfig()
        // Se arranca con lo último que se vio: la pantalla nunca aparece vacía.
        snapshot = SharedStore.cachedSnapshot()
    }

    var needsSetup: Bool { !config.isComplete }

    // MARK: - Descarga

    func refresh(showSpinner: Bool = true) async {
        guard config.isComplete else { return }
        // Con el partido simulado en marcha, traer los puntos reales borraría
        // lo que se está probando.
        guard !isSimulating else { return }
        if showSpinner { isLoading = true }
        defer { isLoading = false }

        do {
            let fresh = try await service.snapshot(for: config)
            await apply(fresh)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
            // Si no había nada en pantalla, al menos se enseña lo guardado.
            if snapshot == nil { snapshot = SharedStore.staleSnapshot() }
            else { snapshot?.isStale = true }
        }
    }

    /// Todo marcador nuevo entra por aquí, venga de la red o del simulador:
    /// se detectan las anotaciones, se guarda, se avisa a los widgets, a la
    /// Live Activity y al usuario.
    private func apply(_ fresh: MatchupSnapshot) async {
        var actualizado = fresh

        // Lo que ha pasado desde la última lectura: quién ha anotado.
        let anotaciones = ScoringDetector.plays(previous: snapshot, current: fresh)
        actualizado.recentPlays = Array((anotaciones + (snapshot?.plays ?? [])).prefix(6))

        snapshot = actualizado
        SharedStore.cache(actualizado)
        WidgetCenter.shared.reloadAllTimelines()

        // Las fotos, en disco, para el widget y la Live Activity.
        Task { await HeadshotCache.prefetch(lineup: actualizado.lineup) }

        live.update(with: actualizado, play: anotaciones.first)
        // Si tres jugadores anotan a la vez, tres avisos son demasiados.
        for anotacion in anotaciones.prefix(3) {
            await live.notify(anotacion)
        }
    }

    // MARK: - Pruebas

    /// Mete una anotación de mentira por el mismo camino que las de verdad.
    func simulate(_ play: MatchSimulator.Play, mine: Bool? = nil) async {
        guard let actual = snapshot,
              let simulado = MatchSimulator.apply(play, to: actual, mine: mine)
        else { return }
        await live.requestNotificationPermission()
        await apply(simulado)
    }

    /// Un partido de mentira: alguien anota cada pocos segundos.
    func startFakeGame(every seconds: UInt64 = 12) {
        guard !isSimulating else { return }
        isSimulating = true
        stopAutoRefresh()
        simulationTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: seconds * 1_000_000_000)
                if Task.isCancelled { return }
                guard let self else { return }
                let jugada = MatchSimulator.Play.allCases.randomElement() ?? .touchdown
                await self.simulate(jugada)
            }
        }
    }

    func stopFakeGame() {
        simulationTask?.cancel()
        simulationTask = nil
        isSimulating = false
        startAutoRefresh()
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
