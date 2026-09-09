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
                    IslandTeam(name: context.attributes.myTeam, points: context.state.myPoints, mine: true)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    IslandTeam(name: context.attributes.opponentTeam, points: context.state.opponentPoints, mine: false)
                }
                DynamicIslandExpandedRegion(.center) {
                    if let play = context.state.lastPlay {
                        PlayBanner(play: play, compact: true)
                    } else {
                        Text("Semana \(context.attributes.week)")
                            .font(.system(size: 11))
                            .foregroundStyle(.white.opacity(0.5))
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    ScoreBar(share: context.state.share, height: 6)
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

    var body: some View {
        VStack(spacing: 10) {
            HStack(spacing: 6) {
                Image(systemName: "trophy.fill")
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.accent)
                Text(attributes.leagueName)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.white.opacity(0.8))
                    .lineLimit(1)
                Spacer(minLength: 0)
                Text("Semana \(attributes.week)")
                    .font(.system(size: 10))
                    .foregroundStyle(.white.opacity(0.5))
            }

            HStack(alignment: .center, spacing: 10) {
                sideColumn(name: attributes.myTeam, points: state.myPoints, alignment: .leading)
                Text(state.difference.signedFantasyPoints)
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(state.difference >= 0 ? Theme.accent : Color.red)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Color.white.opacity(0.08), in: Capsule())
                sideColumn(name: attributes.opponentTeam, points: state.opponentPoints, alignment: .trailing)
            }

            ScoreBar(share: state.share, height: 6)

            if let play = state.lastPlay {
                PlayBanner(play: play, compact: false)
            }
        }
        .padding(14)
    }

    private func sideColumn(name: String, points: Double, alignment: HorizontalAlignment) -> some View {
        VStack(alignment: alignment, spacing: 1) {
            Text(name)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.white.opacity(0.65))
                .lineLimit(1)
            Text(points.fantasyPoints)
                .font(.system(size: 24, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(.white)
        }
        .frame(maxWidth: .infinity, alignment: alignment == .leading ? .leading : .trailing)
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
            VStack(alignment: .leading, spacing: 1) {
                Text(play.name)
                    .font(.system(size: compact ? 11 : 12, weight: .semibold))
                    .foregroundStyle(.white)
                    .lineLimit(1)
                Text(play.isMine ? "Tu equipo" : "Rival")
                    .font(.system(size: 9))
                    .foregroundStyle(.white.opacity(0.45))
            }
            Spacer(minLength: 4)
            Text("+\(play.delta.fantasyPoints)")
                .font(.system(size: compact ? 13 : 15, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(play.isMine ? Theme.accent : Color.red)
        }
        .padding(.horizontal, compact ? 0 : 10)
        .padding(.vertical, compact ? 0 : 7)
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
        .frame(width: compact ? 22 : 28, height: compact ? 22 : 28)
        .background(Color.white.opacity(0.08), in: Circle())
        .clipShape(Circle())
    }
}

struct IslandTeam: View {
    var name: String
    var points: Double
    var mine: Bool

    var body: some View {
        VStack(alignment: mine ? .leading : .trailing, spacing: 1) {
            Text(name)
                .font(.system(size: 10))
                .foregroundStyle(.white.opacity(0.6))
                .lineLimit(1)
            Text(points.fantasyPoints)
                .font(.system(size: 18, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(mine ? Theme.accent : .white)
        }
    }
}
