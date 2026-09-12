//  Celebration.swift
//  La explosión cuando anota uno de los tuyos.
//
//  Se dibuja en un Canvas y no con decenas de vistas: son 30 partículas a 60
//  fotogramas por segundo, y con vistas de SwiftUI eso se nota en la batería.
//
//  Respeta "Reducir movimiento" de Ajustes: quien lo tenga activado ve un
//  destello y nada más.

import SwiftUI
import UIKit

/// Una partícula de la explosión. Se calcula al vuelo con física de bachillerato:
/// posición = origen + velocidad·t + gravedad·t²/2.
private struct Particle {
    var angle: Double
    var speed: Double
    var size: Double
    var color: Color
    var spin: Double
}

struct CelebrationOverlay: View {
    /// Cambiar este identificador dispara una explosión nueva.
    var trigger: String?

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var startedAt: Date?
    @State private var particles: [Particle] = []

    private let duration: TimeInterval = 1.6

    var body: some View {
        GeometryReader { geometry in
            TimelineView(.animation(paused: startedAt == nil)) { timeline in
                Canvas { context, size in
                    guard let startedAt else { return }
                    let t = timeline.date.timeIntervalSince(startedAt)
                    guard t >= 0, t < duration else { return }

                    // El destello inicial: un círculo verde que se abre y se va.
                    let flash = max(0, 1 - t / 0.35)
                    if flash > 0 {
                        let radio = size.width * (0.1 + (1 - flash) * 0.6)
                        let centro = CGPoint(x: size.width / 2, y: size.height * 0.3)
                        context.opacity = flash * 0.35
                        context.fill(
                            Path(ellipseIn: CGRect(
                                x: centro.x - radio, y: centro.y - radio,
                                width: radio * 2, height: radio * 2
                            )),
                            with: .color(Theme.accent)
                        )
                    }

                    guard !reduceMotion else { return }

                    let origen = CGPoint(x: size.width / 2, y: size.height * 0.3)
                    let gravedad = 1400.0

                    for particula in particles {
                        let vx = cos(particula.angle) * particula.speed
                        let vy = sin(particula.angle) * particula.speed
                        let x = origen.x + vx * t
                        let y = origen.y + vy * t + gravedad * t * t / 2

                        // Se desvanecen en el último tercio.
                        let vida = t / duration
                        context.opacity = vida > 0.6 ? (1 - (vida - 0.6) / 0.4) : 1

                        let lado = particula.size
                        var trozo = Path(roundedRect: CGRect(
                            x: -lado / 2, y: -lado / 2, width: lado, height: lado * 0.6
                        ), cornerRadius: 1)
                        trozo = trozo.applying(
                            CGAffineTransform(rotationAngle: particula.spin * t)
                        )
                        trozo = trozo.applying(CGAffineTransform(translationX: x, y: y))
                        context.fill(trozo, with: .color(particula.color))
                    }
                }
            }
            .allowsHitTesting(false)
            .ignoresSafeArea()
        }
        .onChange(of: trigger) { _, nuevo in
            guard nuevo != nil else { return }
            celebrate()
        }
    }

    private func celebrate() {
        particles = (0..<30).map { _ in
            Particle(
                // Hacia arriba y a los lados: un cono, no una esfera.
                angle: Double.random(in: -Double.pi * 0.95 ... -Double.pi * 0.05),
                speed: Double.random(in: 180...520),
                size: Double.random(in: 6...12),
                color: [Theme.accent, .white, Theme.accent.opacity(0.7), .mint]
                    .randomElement() ?? Theme.accent,
                spin: Double.random(in: -12...12)
            )
        }
        startedAt = Date()

        // El golpe en la mano es la mitad del efecto.
        UINotificationFeedbackGenerator().notificationOccurred(.success)

        Task {
            try? await Task.sleep(nanoseconds: UInt64(duration * 1_000_000_000))
            startedAt = nil
        }
    }
}
