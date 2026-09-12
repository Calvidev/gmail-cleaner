//  MatchupLiveActivity.swift
//  La Live Activity: marcador en la pantalla de bloqueo y en la Dynamic Island,
//  con la última anotación —foto, nombre y puntos— destacada.

import ActivityKit
import SwiftUI
import UIKit
import WidgetKit

struct MatchupLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: MatchupActivityAttributes.self) { context in
            LockScreenLiveView(
                attributes: context.attributes, state: context.state
            )
            .activityBackgroundTint(Color(hex: "111113"))
            .activitySystemActionForegroundColor(Theme.accent)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    IslandTeam(
                        name: context.attributes.myTeam,
                        points: context.state.myPoints,
                        projection: context.state.myProjection,
                        mine: true
                    )
                }
                DynamicIslandExpandedRegion(.trailing) {
                    IslandTeam(
                        name: context.attributes.opponentTeam,
                        points: context.state.opponentPoints,
                        projection: context.state.opponentProjection,
                        mine: false
                    )
                }
                // Nada en el centro: compite por el ancho con las columnas de
                // los equipos y las deja sin sitio. La jugada va abajo, que es
                // la única región que ocupa todo el ancho.
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(spacing: 8) {
                        ScoreBar(share: context.state.share, height: 5)
                        if let play = context.state.lastPlay {
                            PlayBanner(play: play, compact: false)
                        } else {
                            HStack {
                                Text("Semana \(context.attributes.week)")
                                Spacer()
                                Text("Titulares \(context.state.myStarters):\(context.state.opponentStarters)")
                            }
                            .font(.system(size: 10))
                            .foregroundStyle(.white.opacity(0.5))
                        }
                    }
                }
            } compactLeading: {
                Text(context.state.myPoints.fantasyPoints)
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(Theme.accent)
            } compactTrailing: {
                Text(context.state.opponentPoints.fantasyPoints)
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(.white)
            } minimal: {
                Text(context.state.difference.signedFantasyPoints)
                    .font(.system(size: 11, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(context.state.difference >= 0 ? Theme.accent : Color.red)
            }
            .keylineTint(Theme.accent)
        }
    }
}

// MARK: - Pantalla de bloqueo

struct LockScreenLiveView: View {
    var attributes: MatchupActivityAttributes
    var state: MatchupActivityAttributes.ContentState

    // La pantalla de bloqueo da unos 160 puntos de alto y recorta lo que
    // sobre, así que aquí se cuenta cada punto: cuatro filas y ninguna más.
    var body: some View {
        VStack(spacing: 7) {
            cabecera
            marcador
            ScoreBar(share: state.share, height: 5)
            if let play = state.lastPlay {
                PlayBanner(play: play, compact: false)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
    }

    private var cabecera: some View {
        HStack(spacing: 5) {
            Image(systemName: "trophy.fill")
                .font(.system(size: 10))
                .foregroundStyle(Theme.accent)
            Text(attributes.leagueName)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.white.opacity(0.8))
                .lineLimit(1)
            Spacer(minLength: 4)
            Text("Sem. \(attributes.week)")
        }
        .font(.system(size: 10))
        .foregroundStyle(.white.opacity(0.45))
        .lineLimit(1)
    }

    /// Cada equipo con su foto, sus puntos y —más pequeña— su proyección,
    /// como en Sleeper. En el centro, la diferencia y la probabilidad.
    private var marcador: some View {
        HStack(alignment: .center, spacing: 8) {
            TeamLine(
                avatarURL: attributes.myAvatarURL,
                name: attributes.myTeam,
                points: state.myPoints,
                projection: state.myProjection,
                alignment: .leading
            )

            VStack(spacing: 2) {
                Text(state.difference.signedFantasyPoints)
                    .font(.system(size: 11, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(state.difference >= 0 ? Theme.accent : Color.red)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.white.opacity(0.08), in: Capsule())
                if let winChance = state.winChanceText {
                    Text(winChance)
                        .font(.system(size: 10, weight: .bold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle((state.isFavorite ?? true) ? Theme.accent : Color.red)
                }
            }
            .fixedSize()

            TeamLine(
                avatarURL: attributes.opponentAvatarURL,
                name: attributes.opponentTeam,
                points: state.opponentPoints,
                projection: state.opponentProjection,
                alignment: .trailing
            )
        }
    }
}

/// Foto, puntos y proyección de un equipo, en una fila.
struct TeamLine: View {
    var avatarURL: String?
    var name: String
    var points: Double
    var projection: Double?
    var alignment: HorizontalAlignment

    private var esIzquierda: Bool { alignment == .leading }

    var body: some View {
        HStack(spacing: 6) {
            if esIzquierda { avatar }
            VStack(alignment: alignment, spacing: 0) {
                Text(name)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(.white.opacity(0.6))
                    .lineLimit(1)
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    if !esIzquierda, let projection {
                        proyeccion(projection)
                    }
                    Text(points.fantasyPoints)
                        .font(.system(size: 21, weight: .bold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(.white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                    if esIzquierda, let projection {
                        proyeccion(projection)
                    }
                }
            }
            if !esIzquierda { avatar }
        }
        .frame(maxWidth: .infinity, alignment: esIzquierda ? .leading : .trailing)
    }

    /// La foto sale del archivo que la app dejó en el grupo de apps: aquí no
    /// hay red que valga.
    private var avatar: some View {
        Group {
            if let datos = AvatarLoader.cachedData(for: avatarURL.flatMap(URL.init(string:))),
               let imagen = UIImage(data: datos) {
                Image(uiImage: imagen).resizable().scaledToFill()
            } else {
                Image(systemName: "person.crop.circle.fill")
                    .resizable()
                    .scaledToFit()
                    .foregroundStyle(.white.opacity(0.3))
            }
        }
        .frame(width: 26, height: 26)
        .clipShape(Circle())
    }

    private func proyeccion(_ valor: Double) -> some View {
        Text(valor.fantasyPoints)
            .font(.system(size: 11, weight: .medium, design: .rounded))
            .monospacedDigit()
            .foregroundStyle(.white.opacity(0.4))
    }
}

// MARK: - La anotación

/// Foto, nombre y puntos de quien acaba de anotar. La foto sale del archivo
/// que la app dejó en el grupo de apps: aquí no hay red.
struct PlayBanner: View {
    var play: ScoringPlay
    var compact: Bool

    var body: some View {
        HStack(spacing: 8) {
            headshot
            VStack(alignment: .leading, spacing: 0) {
                Text(play.name)
                    .font(.system(size: compact ? 11 : 12, weight: .semibold))
                    .foregroundStyle(.white)
                    .lineLimit(1)
                // Lo que lleva hecho: "6 rec · 88 yds · 1 TD".
                Text(play.stats ?? play.subtitle)
                    .font(.system(size: 10))
                    .foregroundStyle(.white.opacity(0.6))
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                // Quién es se sabe por el color de los puntos: en verde los
                // tuyos, en rojo los del rival. Una línea menos.
            }
            Spacer(minLength: 4)
            VStack(alignment: .trailing, spacing: 0) {
                Text("+\(play.delta.fantasyPoints)")
                    .font(.system(size: compact ? 13 : 15, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(play.isMine ? Theme.accent : Color.red)
                Text("\(play.total.fantasyPoints) pts")
                    .font(.system(size: 9))
                    .monospacedDigit()
                    .foregroundStyle(.white.opacity(0.45))
            }
        }
        .padding(.horizontal, compact ? 0 : 8)
        .padding(.vertical, compact ? 0 : 5)
        .background(
            compact ? Color.clear : Color.white.opacity(0.06),
            in: RoundedRectangle(cornerRadius: 10, style: .continuous)
        )
    }

    private var headshot: some View {
        Group {
            if let data = HeadshotCache.cachedData(playerID: play.playerID),
               let image = UIImage(data: data) {
                Image(uiImage: image).resizable().scaledToFill()
            } else {
                Image(systemName: "person.fill")
                    .resizable()
                    .scaledToFit()
                    .padding(6)
                    .foregroundStyle(.white.opacity(0.35))
            }
        }
        .frame(width: compact ? 22 : 26, height: compact ? 22 : 26)
        .background(Color.white.opacity(0.08), in: Circle())
        .clipShape(Circle())
    }
}

struct IslandTeam: View {
    var name: String
    var points: Double
    var projection: Double?
    var mine: Bool

    var body: some View {
        VStack(alignment: mine ? .leading : .trailing, spacing: 1) {
            Text(name)
                .font(.system(size: 10))
                .foregroundStyle(.white.opacity(0.6))
                .lineLimit(1)
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(points.fantasyPoints)
                    .font(.system(size: 18, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(mine ? Theme.accent : .white)
                if let projection {
                    Text(projection.fantasyPoints)
                        .font(.system(size: 10, weight: .medium, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(.white.opacity(0.4))
                }
            }
        }
    }
}
