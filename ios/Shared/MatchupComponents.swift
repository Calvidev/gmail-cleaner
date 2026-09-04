//  MatchupComponents.swift
//  Las piezas visuales que comparten la app y el widget.

import SwiftUI
import UIKit

/// Avatar redondo del manager; si no hay imagen, la silueta del sistema.
struct AvatarBadge: View {
    var data: Data?
    var size: CGFloat

    var body: some View {
        Group {
            if let data, let image = UIImage(data: data) {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
            } else {
                Image(systemName: "person.crop.circle.fill")
                    .resizable()
                    .scaledToFit()
                    .foregroundStyle(.secondary)
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
    }
}

/// La barra de reparto de puntos: cuánto del total llevo yo.
struct ScoreBar: View {
    var share: Double
    var height: CGFloat = 8

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.track)
                Capsule()
                    .fill(Theme.accent)
                    .frame(width: geometry.size.width * CGFloat(min(max(share, 0), 1)))
            }
        }
        .frame(height: height)
        .accessibilityHidden(true)
    }
}

/// La diferencia, en verde si voy ganando y en rojo si voy perdiendo.
struct DifferencePill: View {
    var difference: Double
    var compact: Bool = false

    var body: some View {
        Text(difference.signedFantasyPoints)
            .font(.system(size: compact ? 11 : 13, weight: .semibold, design: .rounded))
            .monospacedDigit()
            .foregroundStyle(difference >= 0 ? Theme.accent : Color.red)
            .padding(.horizontal, compact ? 6 : 9)
            .padding(.vertical, compact ? 2 : 4)
            .background(Theme.pill, in: Capsule())
    }
}

/// Un equipo: avatar, nombre, récord y puntos.
struct TeamColumn: View {
    var team: TeamSide?
    var alignment: HorizontalAlignment
    var avatarSize: CGFloat = 22
    var scoreSize: CGFloat = 30
    var placeholder: String = "Sin rival"

    var body: some View {
        VStack(alignment: alignment, spacing: 4) {
            HStack(spacing: 6) {
                if alignment == .trailing { Spacer(minLength: 0) }
                AvatarBadge(data: team?.avatarData, size: avatarSize)
                VStack(alignment: alignment == .trailing ? .trailing : .leading, spacing: 0) {
                    Text(team?.name ?? placeholder)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.white)
                        .lineLimit(1)
                    if let record = team?.record {
                        Text(record)
                            .font(.system(size: 10))
                            .foregroundStyle(.white.opacity(0.5))
                    }
                }
                if alignment == .leading { Spacer(minLength: 0) }
            }
            Text((team?.points ?? 0).fantasyPoints)
                .font(.system(size: scoreSize, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
    }
}

/// Cabecera con el trofeo y el nombre de la liga.
struct LeagueHeader: View {
    var leagueName: String
    var week: Int

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "trophy.fill")
                .font(.system(size: 12))
                .foregroundStyle(Theme.accent)
            Text(leagueName)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(.white)
                .lineLimit(1)
            Spacer(minLength: 0)
            Text("Semana \(week)")
                .font(.system(size: 11))
                .foregroundStyle(.white.opacity(0.6))
        }
    }
}

extension Date {
    /// "18:42" — la hora del último refresco, como en el widget original.
    var hourAndMinute: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "es_ES")
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: self)
    }
}
