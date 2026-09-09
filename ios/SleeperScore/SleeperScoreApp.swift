//  SleeperScoreApp.swift

import BackgroundTasks
import SwiftUI

@main
struct SleeperScoreApp: App {
    @StateObject private var model = ScoreboardModel()
    @Environment(\.scenePhase) private var scenePhase

    init() {
        // Hay que registrarla antes de que la app termine de arrancar.
        BackgroundRefresh.register()
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
                .preferredColorScheme(.dark)
                .tint(Theme.accent)
        }
        .onChange(of: scenePhase) { _, phase in
            // Al volver a la app se refresca; al salir se para el temporizador.
            switch phase {
            case .active:
                model.startAutoRefresh()
            default:
                model.stopAutoRefresh()
                // Al salir se pide el siguiente rato de segundo plano.
                BackgroundRefresh.schedule()
            }
        }
    }
}
