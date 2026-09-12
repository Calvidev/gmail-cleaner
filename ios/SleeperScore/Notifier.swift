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
        /// Dos notas subiendo una quinta: anotó uno de los tuyos.
        static let anotacion = UNNotificationSound(named: UNNotificationSoundName("anotacion.wav"))
        /// Una nota grave y sola: una lesión, nada que celebrar.
        static let aviso = UNNotificationSound(named: UNNotificationSoundName("aviso.wav"))
        /// Dos notas iguales: te han pasado (o has vuelto a pasar tú).
        static let alerta = UNNotificationSound(named: UNNotificationSoundName("alerta.wav"))
    }

    /// Cuánto tiene que pasar para que un aviso vuelva a sonar. Los demás
    /// llegan igual, pero en silencio.
    ///
    /// Una tarde de domingo puede haber veinte anotaciones. Veinte sonidos
    /// seguidos hacen que la gente apague las notificaciones de la app, y
    /// entonces se pierde también el aviso que sí importaba.
    private static let silencioEntreSonidos: TimeInterval = 90
    private static let claveUltimoSonido = "lastNotificationSound"

    /// El sonido que toca, o nada si acaba de sonar uno.
    private static func sonido(_ propuesto: UNNotificationSound) -> UNNotificationSound? {
        let ahora = Date()
        if let ultimo = SharedStore.defaults.object(forKey: claveUltimoSonido) as? Date,
           ahora.timeIntervalSince(ultimo) < silencioEntreSonidos {
            return nil
        }
        SharedStore.defaults.set(ahora, forKey: claveUltimoSonido)
        return propuesto
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

    /// Un aviso por tanda, no uno por jugador. Si tres de los tuyos anotan
    /// entre dos lecturas, tres notificaciones seguidas son ruido.
    static func plays(_ plays: [ScoringPlay]) async {
        guard !plays.isEmpty else { return }
        if plays.count == 1 {
            await play(plays[0])
        } else {
            await resumen(plays)
        }
    }

    private static func resumen(_ plays: [ScoringPlay]) async {
        guard await authorized() else { return }
        let mias = plays.filter(\.isMine).count

        let contenido = UNMutableNotificationContent()
        contenido.title = String(localized: "\(plays.count) anotaciones")
        contenido.subtitle = mias == plays.count
            ? String(localized: "Todas tuyas")
            : String(localized: "\(mias) tuyas")
        contenido.body = plays
            .prefix(4)
            .map { "\($0.name) +\($0.delta.fantasyPoints)" }
            .joined(separator: " · ")
        contenido.sound = sonido(Sonido.anotacion)
        contenido.interruptionLevel = .active
        contenido.threadIdentifier = "anotaciones"

        // La foto de la jugada más gorda representa a la tanda.
        if let principal = plays.max(by: { $0.delta < $1.delta }),
           let adjunto = await attachment(
               playerID: principal.playerID, position: principal.position, team: principal.team
           ) {
            contenido.attachments = [adjunto]
        }
        await add(contenido, id: "resumen-\(Int(Date().timeIntervalSince1970))")
    }

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
        contenido.sound = sonido(Sonido.anotacion)
        // Solo un touchdown (seis puntos y pico) merece romper un modo de
        // concentración. Una recepción de 1.4 no.
        contenido.interruptionLevel = play.delta >= 5 ? .timeSensitive : .active
        contenido.threadIdentifier = "anotaciones"

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
        contenido.sound = nil
        // Una noticia no interrumpe ni suele merecer sonido: no es una jugada
        // en directo y puede esperar a que mires el teléfono.
        contenido.interruptionLevel = .passive
        contenido.threadIdentifier = "noticias"
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
        contenido.sound = sonido(Sonido.alerta)
        contenido.interruptionLevel = .timeSensitive
        contenido.threadIdentifier = "marcador"
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
        // Un parte a peor es raro y no espera: suena aunque acabe de sonar otro.
        // El alta médica puede llegar callada si hay ruido.
        contenido.sound = change.isWorse ? Sonido.aviso : sonido(Sonido.aviso)
        // Un cambio a peor el domingo por la mañana sí interrumpe.
        contenido.interruptionLevel = change.isWorse ? .timeSensitive : .active
        contenido.threadIdentifier = "lesiones"

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
