//  BackgroundRefresh.swift
//  Comprobar el marcador con la app cerrada.
//
//  Es lo más parecido a un aviso en vivo que se puede tener sin push (y el
//  push de verdad necesita servidor y cuenta de desarrollador de pago). iOS
//  decide cuándo conceder estos ratos: típicamente cada 15-30 minutos, y
//  aprende de cuánto usas la app. No es inmediato, pero es gratis y funciona
//  con el teléfono en el bolsillo.

import BackgroundTasks
import Foundation
import WidgetKit

enum BackgroundRefresh {
    static let taskID = "dev.calvi.sleeperscore.refresh"

    /// Se llama una vez al arrancar la app.
    static func register() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: taskID, using: nil
        ) { task in
            guard let refresco = task as? BGAppRefreshTask else {
                task.setTaskCompleted(success: false)
                return
            }
            handle(refresco)
        }
    }

    /// Pide el siguiente rato. Hay que volver a pedirlo cada vez que se usa.
    static func schedule(after minutes: Double = 15) {
        let peticion = BGAppRefreshTaskRequest(identifier: taskID)
        peticion.earliestBeginDate = Date().addingTimeInterval(minutes * 60)
        try? BGTaskScheduler.shared.submit(peticion)
    }

    private static func handle(_ task: BGAppRefreshTask) {
        schedule()  // encadenar el siguiente antes de nada

        let trabajo = Task {
            await run()
            task.setTaskCompleted(success: true)
        }
        task.expirationHandler = {
            trabajo.cancel()
            task.setTaskCompleted(success: false)
        }
    }

    /// Descarga el marcador, avisa de lo que haya pasado y deja todo guardado.
    /// Sin interfaz de por medio: esto corre con la app cerrada.
    static func run() async {
        let config = SharedStore.loadConfig()
        guard config.isComplete else { return }

        let anterior = SharedStore.cachedSnapshot(for: config)
        guard var fresco = try? await MatchupService().snapshot(for: config) else { return }

        let anotaciones = ScoringDetector.plays(previous: anterior, current: fresco)
        fresco.recentPlays = Array((anotaciones + (anterior?.plays ?? [])).prefix(6))
        SharedStore.cache(fresco, for: config)
        WidgetCenter.shared.reloadAllTimelines()

        for anotacion in anotaciones.prefix(3) {
            await Notifier.play(anotacion)
        }

        // El parte de lesiones cambia mucho más despacio que el marcador, así
        // que solo se mira cuando el catálogo ya toca renovarse.
        if await PlayerCatalog.shared.isStale {
            let catalogo = await PlayerCatalog.shared.refreshIfNeeded()
            for cambio in InjuryWatcher.changes(in: fresco, catalog: catalogo).prefix(3) {
                await Notifier.injury(cambio)
            }
        }
    }
}
