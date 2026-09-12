//  Notifier.swift
//  Los avisos: anotaciones y cambios en el parte de lesiones.
//
//  Vive fuera del controlador de la Live Activity porque también lo usa el
//  refresco en segundo plano, que corre sin interfaz.

import Foundation
import UserNotifications

enum Notifier {
    /// Sonidos propios, dentro del paquete de la app. iOS solo admite WAV, CAF
    /// o AIFF de menos de 30 segundos, y hay que nombrarlos con su extensión.
    /// Se generan con `tools/generate_sounds.py`.
    private enum Sonido {
        /// Tres notas subiendo: anotó uno de los tuyos.
        static let anotacion = UNNotificationSound(named: UNNotificationSoundName("anotacion.wav"))
        /// Dos notas bajando: una lesión o una noticia, nada que celebrar.
        static let aviso = UNNotificationSound(named: UNNotificationSoundName("aviso.wav"))
        /// Dos golpes iguales: te han pasado (o has vuelto a pasar tú).
        static let alerta = UNNotificationSound(named: UNNotificationSoundName("alerta.wav"))
    }

    static func requestPermission() async {
        _ = try? await UNUserNotificationCenter.current()
            .requestAuthorization(options: [.alert, .sound])
    }

    private static func authorized() async -> Bool {
        let ajustes = await UNUserNotificationCenter.current().notificationSettings()
        return ajustes.authorizationStatus == .authorized
            || ajustes.authorizationStatus == .provisional
    }

    // MARK: - Anotación

    static func play(_ play: ScoringPlay) async {
        guard await authorized() else { return }

        let contenido = UNMutableNotificationContent()
        contenido.title = play.isMine
            ? String(localized: "Anotó tu jugador")
            : String(localized: "Anotó el rival")
        contenido.subtitle = String(
            localized: "+\(play.delta.fantasyPoints) pts · \(play.total.fantasyPoints) en total"
        )
        let detalle = play.stats ?? play.subtitle
        contenido.body = detalle.isEmpty ? play.name : "\(play.name) — \(detalle)"
        contenido.sound = Sonido.anotacion
        contenido.interruptionLevel = .timeSensitive

        if let adjunto = await attachment(
            playerID: play.playerID, position: play.position, team: play.team
        ) {
            contenido.attachments = [adjunto]
        }
        await add(contenido, id: play.id)
    }

    // MARK: - Noticia

    static func news(_ item: NewsItem, playerName: String?) async {
        guard await authorized() else { return }

        let contenido = UNMutableNotificationContent()
        contenido.title = playerName
            .map { String(localized: "Noticia de \($0)") }
            ?? String(localized: "Noticia de tu equipo")
        contenido.body = item.headline
        if let resumen = item.summary, !resumen.isEmpty { contenido.subtitle = resumen }
        contenido.sound = Sonido.aviso
        // Una noticia no interrumpe: no es una jugada en directo.
        contenido.interruptionLevel = .active
        await add(contenido, id: "news-\(item.id.hashValue)")
    }

    // MARK: - Cambio de liderato

    static func leadChange(tookLead: Bool, difference: Double, opponent: String) async {
        guard await authorized() else { return }

        let contenido = UNMutableNotificationContent()
        contenido.title = tookLead
            ? String(localized: "Vuelves a ir ganando")
            : String(localized: "Te acaban de pasar")
        contenido.body = tookLead
            ? String(localized: "Vas por delante de \(opponent) por \(abs(difference).fantasyPoints).")
            : String(localized: "\(opponent) se pone por delante por \(abs(difference).fantasyPoints).")
        contenido.sound = Sonido.alerta
        contenido.interruptionLevel = .timeSensitive
        await add(contenido, id: "lead-\(Int(Date().timeIntervalSince1970))")
    }

    // MARK: - Lesión

    static func injury(_ change: InjuryChange) async {
        guard await authorized() else { return }

        let contenido = UNMutableNotificationContent()
        contenido.title = change.isWorse
            ? String(localized: "Parte de lesión")
            : String(localized: "Buenas noticias")
        contenido.body = change.headline
        let posicion = [change.position, change.team].compactMap { $0 }.joined(separator: " ")
        if !posicion.isEmpty { contenido.subtitle = posicion }
        contenido.sound = Sonido.aviso
        // Un cambio a peor el domingo por la mañana sí interrumpe.
        contenido.interruptionLevel = change.isWorse ? .timeSensitive : .active

        if let adjunto = await attachment(
            playerID: change.playerID, position: change.position, team: change.team
        ) {
            contenido.attachments = [adjunto]
        }
        await add(contenido, id: change.id)
    }

    // MARK: - Interno

    private static func add(_ content: UNNotificationContent, id: String) async {
        let peticion = UNNotificationRequest(identifier: id, content: content, trigger: nil)
        try? await UNUserNotificationCenter.current().add(peticion)
    }

    /// Las notificaciones exigen un archivo con extensión reconocible, así que
    /// la foto cacheada se copia a temporales como .jpg.
    private static func attachment(
        playerID: String, position: String?, team: String?
    ) async -> UNNotificationAttachment? {
        guard
            let datos = await HeadshotCache.prefetch(
                playerID: playerID, position: position, team: team
            )
        else { return nil }

        let destino = FileManager.default.temporaryDirectory
            .appendingPathComponent("aviso-\(playerID).jpg")
        do {
            try datos.write(to: destino, options: .atomic)
            return try UNNotificationAttachment(identifier: playerID, url: destino)
        } catch {
            return nil
        }
    }
}
