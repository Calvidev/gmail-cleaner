//  LiveActivityController.swift
//  Enciende, actualiza y apaga la Live Activity, y avisa cuando alguien anota.
//
//  Límite que conviene tener presente: una Live Activity no se refresca sola
//  como un widget. Se actualiza cuando la app puede hacerlo (abierta, o en los
//  ratos de segundo plano que conceda iOS) o por push, y el push necesita la
//  capacidad de notificaciones, que pide cuenta de desarrollador de pago.

import ActivityKit
import Foundation
import UIKit
import UserNotifications

@MainActor
final class LiveActivityController: ObservableObject {
    /// Una sola por proceso: el sistema solo admite una actividad de este tipo
    /// y tanto el marcador como la pantalla la manejan.
    static let shared = LiveActivityController()

    @Published private(set) var isRunning = false
    @Published private(set) var lastError: String?

    private var activity: Activity<MatchupActivityAttributes>?

    init() {
        // Al arrancar puede haber una actividad viva de una sesión anterior.
        activity = Activity<MatchupActivityAttributes>.activities.first
        isRunning = activity != nil
    }

    var areActivitiesEnabled: Bool {
        ActivityAuthorizationInfo().areActivitiesEnabled
    }

    // MARK: - Ciclo de vida

    func start(with snapshot: MatchupSnapshot) {
        guard areActivitiesEnabled else {
            lastError = "Las Live Activities están desactivadas para esta app en Ajustes."
            return
        }
        guard activity == nil else {
            update(with: snapshot)
            return
        }
        do {
            activity = try Activity.request(
                attributes: snapshot.activityAttributes,
                content: ActivityContent(state: snapshot.activityState(), staleDate: nil),
                pushType: nil  // sin push: se actualiza desde la app
            )
            isRunning = true
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func update(with snapshot: MatchupSnapshot, play: ScoringPlay? = nil) {
        guard let activity else { return }
        Task {
            // Que la foto esté en disco antes de enseñarla: la Live Activity no
            // puede salir a la red mientras se pinta.
            if let play {
                await HeadshotCache.prefetch(
                    playerID: play.playerID, position: play.position, team: play.team
                )
            }
            let estado = snapshot.activityState(lastPlay: play)
            await activity.update(ActivityContent(state: estado, staleDate: nil))
        }
    }

    func stop() {
        guard let activity else { return }
        Task {
            await activity.end(nil, dismissalPolicy: .immediate)
            self.activity = nil
            self.isRunning = false
        }
    }

    // MARK: - Aviso de anotación

    func requestNotificationPermission() async {
        _ = try? await UNUserNotificationCenter.current()
            .requestAuthorization(options: [.alert, .sound])
    }

    /// Notificación con sonido, foto y puntos del jugador que acaba de anotar.
    func notify(_ play: ScoringPlay) async {
        let centro = UNUserNotificationCenter.current()
        let permisos = await centro.notificationSettings()
        guard permisos.authorizationStatus == .authorized else { return }

        let contenido = UNMutableNotificationContent()
        contenido.title = play.isMine ? "Anotó tu jugador" : "Anotó el rival"
        let sufijo = play.subtitle.isEmpty ? "" : " · \(play.subtitle)"
        contenido.body = "\(play.name)\(sufijo)  +\(play.delta.fantasyPoints) pts (\(play.total.fantasyPoints))"
        contenido.sound = .default
        contenido.interruptionLevel = .timeSensitive

        if let adjunto = await attachment(for: play) {
            contenido.attachments = [adjunto]
        }

        let peticion = UNNotificationRequest(
            identifier: play.id, content: contenido, trigger: nil
        )
        try? await centro.add(peticion)
    }

    /// Las notificaciones exigen un archivo con extensión reconocible, así que
    /// la foto cacheada se copia a temporales como .jpg.
    private func attachment(for play: ScoringPlay) async -> UNNotificationAttachment? {
        guard
            let datos = await HeadshotCache.prefetch(
                playerID: play.playerID, position: play.position, team: play.team
            )
        else { return nil }

        let destino = FileManager.default.temporaryDirectory
            .appendingPathComponent("play-\(play.playerID).jpg")
        do {
            try datos.write(to: destino, options: .atomic)
            return try UNNotificationAttachment(identifier: play.playerID, url: destino)
        } catch {
            return nil
        }
    }
}
