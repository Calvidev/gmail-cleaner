//  ShareCard.swift
//  La imagen del marcador para mandar al grupo de la liga.
//
//  Además de una feature, es el canal de crecimiento más barato que tiene la
//  app: cada resultado compartido la enseña a doce personas que juegan a esto.

import SwiftUI
import UIKit

/// La tarjeta que se convierte en imagen. Se dibuja aparte de la pantalla
/// porque tiene que verse bien fuera de la app, sin depender del tema.
struct MatchupShareCard: View {
    var snapshot: MatchupSnapshot

    var body: some View {
        VStack(spacing: 16) {
            HStack(spacing: 6) {
                Image(systemName: "trophy.fill")
                    .foregroundStyle(Theme.accent)
                Text(snapshot.leagueName)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.white)
                    .lineLimit(1)
                Spacer(minLength: 0)
                Text("Semana \(snapshot.week)")
                    .font(.system(size: 12))
                    .foregroundStyle(.white.opacity(0.5))
            }

            HStack(alignment: .top, spacing: 12) {
                side(snapshot.me, points: snapshot.me.points, alignment: .leading)
                VStack(spacing: 4) {
                    Text("vs")
                        .font(.system(size: 11))
                        .foregroundStyle(.white.opacity(0.35))
                    Text(snapshot.difference.signedFantasyPoints)
                        .font(.system(size: 13, weight: .bold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(snapshot.isLeading ? Theme.accent : Color.red)
                }
                .padding(.top, 14)
                side(snapshot.opponent, points: snapshot.opponentPoints, alignment: .trailing)
            }

            ScoreBar(share: snapshot.barShare, height: 8)

            if let projection = snapshot.projection {
                HStack(spacing: 8) {
                    WinChanceBadge(projection: projection)
                    Text("de ganar · proyección \(projection.mine.fantasyPoints) – \(projection.theirs.fantasyPoints)")
                        .font(.system(size: 11))
                        .foregroundStyle(.white.opacity(0.5))
                        .lineLimit(1)
                }
            }

            if let play = snapshot.plays.first {
                HStack(spacing: 8) {
                    PlayerHeadshot(
                        line: PlayerLine(
                            playerID: play.playerID, points: play.total,
                            name: play.name, position: play.position, team: play.team
                        ),
                        size: 26
                    )
                    VStack(alignment: .leading, spacing: 0) {
                        Text(play.name)
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(.white)
                        if let stats = play.stats {
                            Text(stats)
                                .font(.system(size: 10))
                                .foregroundStyle(.white.opacity(0.5))
                        }
                    }
                    Spacer(minLength: 0)
                    Text("+\(play.delta.fantasyPoints)")
                        .font(.system(size: 13, weight: .bold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(play.isMine ? Theme.accent : Color.red)
                }
                .padding(10)
                .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 12))
            }

            Text("Marcador Fantasy")
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.white.opacity(0.28))
        }
        .padding(20)
        .frame(width: 360)
        .background(Theme.background)
    }

    private func side(_ team: TeamSide?, points: Double, alignment: HorizontalAlignment) -> some View {
        VStack(alignment: alignment, spacing: 4) {
            AvatarBadge(data: team?.avatarData, size: 34)
            Text(team?.name ?? "Sin rival")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.white)
                .lineLimit(1)
            Text(points.fantasyPoints)
                .font(.system(size: 34, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(.white)
        }
        .frame(maxWidth: .infinity, alignment: alignment == .leading ? .leading : .trailing)
    }
}

/// Botón de compartir: dibuja la tarjeta a imagen y abre la hoja del sistema.
struct ShareScoreButton: View {
    var snapshot: MatchupSnapshot
    @State private var image: Image?

    var body: some View {
        Group {
            if let image {
                ShareLink(
                    item: image,
                    preview: SharePreview("Marcador de la semana \(snapshot.week)", image: image)
                ) {
                    label
                }
            } else {
                label.opacity(0.5)
            }
        }
        .task(id: snapshot.updatedAt) { render() }
    }

    private var label: some View {
        ActionTile(title: "Compartir", icon: "square.and.arrow.up")
    }

    @MainActor
    private func render() {
        let renderer = ImageRenderer(content: MatchupShareCard(snapshot: snapshot))
        // 3x para que se vea nítida en cualquier pantalla donde acabe.
        renderer.scale = 3
        guard let uiImage = renderer.uiImage else { return }
        image = Image(uiImage: uiImage)
    }
}
