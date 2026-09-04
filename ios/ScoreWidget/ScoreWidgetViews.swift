//  ScoreWidgetViews.swift
//  Las cinco caras del widget: pequeño, mediano, grande y las dos de bloqueo.

import SwiftUI
import WidgetKit

struct ScoreWidgetEntryView: View {
    var entry: ScoreEntry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        switch family {
        case .accessoryInline:
            InlineScore(snapshot: entry.snapshot)
                .containerBackground(.clear, for: .widget)
        case .accessoryRectangular:
            RectangularScore(snapshot: entry.snapshot)
                .containerBackground(.clear, for: .widget)
        case .systemSmall:
            content { SmallScore(snapshot: $0) }
        case .systemLarge:
            content { LargeScore(snapshot: $0) }
        default:
            content { MediumScore(snapshot: $0) }
        }
    }

    /// Las tres caras de pantalla de inicio comparten fondo y el aviso de
    /// "sin datos todavía".
    @ViewBuilder
    private func content<V: View>(_ build: (MatchupSnapshot) -> V) -> some View {
        Group {
            if let snapshot = entry.snapshot {
                build(snapshot)
            } else {
                EmptyState(message: entry.message)
            }
        }
        .containerBackground(for: .widget) { Theme.background }
    }
}

// MARK: - Pequeño

struct SmallScore: View {
    var snapshot: MatchupSnapshot

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(snapshot.leagueName)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.white.opacity(0.6))
                .lineLimit(1)

            side(snapshot.me, points: snapshot.me.points)
            ScoreBar(share: snapshot.myShare, height: 6)
                .padding(.vertical, 2)
            side(snapshot.opponent, points: snapshot.opponentPoints)

            Spacer(minLength: 0)

            HStack(spacing: 4) {
                Text("Sem. \(snapshot.week)")
                Spacer(minLength: 0)
                Text(snapshot.isStale ? "guardado" : snapshot.updatedAt.hourAndMinute)
            }
            .font(.system(size: 9))
            .foregroundStyle(.white.opacity(0.45))
        }
    }

    private func side(_ team: TeamSide?, points: Double) -> some View {
        HStack(spacing: 6) {
            AvatarBadge(data: team?.avatarData, size: 16)
            Text(team?.name ?? "Sin rival")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.white)
                .lineLimit(1)
            Spacer(minLength: 2)
            Text(points.fantasyPoints)
                .font(.system(size: 17, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(.white)
        }
    }
}

// MARK: - Mediano

struct MediumScore: View {
    var snapshot: MatchupSnapshot

    var body: some View {
        VStack(spacing: 8) {
            LeagueHeader(leagueName: snapshot.leagueName, week: snapshot.week)

            HStack(alignment: .top, spacing: 8) {
                TeamColumn(team: snapshot.me, alignment: .leading, avatarSize: 20, scoreSize: 28)
                DifferencePill(difference: snapshot.difference, compact: true)
                    .padding(.top, 10)
                TeamColumn(
                    team: snapshot.opponent, alignment: .trailing,
                    avatarSize: 20, scoreSize: 28, placeholder: "Descansa"
                )
            }

            ScoreBar(share: snapshot.myShare)

            HStack {
                Text("Titulares \(snapshot.me.startersCount):\(snapshot.opponent?.startersCount ?? 0)")
                Spacer()
                Text(snapshot.isStale ? "Datos guardados" : "Actualizado \(snapshot.updatedAt.hourAndMinute)")
            }
            .font(.system(size: 10))
            .foregroundStyle(.white.opacity(0.5))
        }
    }
}

// MARK: - Grande

struct LargeScore: View {
    var snapshot: MatchupSnapshot

    /// Solo caben unos cuantos huecos; se enseñan los primeros de la alineación.
    private var rows: [LineupRow] { Array(snapshot.lineup.prefix(8)) }

    var body: some View {
        VStack(spacing: 10) {
            MediumScore(snapshot: snapshot)
            if !rows.isEmpty {
                Divider().overlay(Color.white.opacity(0.08))
                VStack(spacing: 5) {
                    ForEach(rows) { row in
                        LargeLineupRow(row: row)
                    }
                }
            }
            Spacer(minLength: 0)
        }
    }
}

struct LargeLineupRow: View {
    var row: LineupRow

    var body: some View {
        HStack(spacing: 6) {
            Text(shortName(row.mine))
                .frame(maxWidth: .infinity, alignment: .leading)
            Text((row.mine?.points ?? 0).fantasyPoints)
                .monospacedDigit()
                .foregroundStyle(.white)
            Text(row.slotLabel)
                .font(.system(size: 9, weight: .bold))
                .frame(width: 38)
                .foregroundStyle(.white.opacity(0.5))
            Text((row.theirs?.points ?? 0).fantasyPoints)
                .monospacedDigit()
                .foregroundStyle(.white)
            Text(shortName(row.theirs))
                .frame(maxWidth: .infinity, alignment: .trailing)
        }
        .font(.system(size: 11))
        .foregroundStyle(.white.opacity(0.75))
        .lineLimit(1)
    }

    /// "Tyreek Hill" -> "T. Hill", que es lo que cabe en un widget.
    private func shortName(_ line: PlayerLine?) -> String {
        guard let line else { return "—" }
        guard let name = line.name else { return line.playerID }
        let parts = name.split(separator: " ")
        guard parts.count >= 2, let initial = parts[0].first else { return name }
        return "\(initial). \(parts.dropFirst().joined(separator: " "))"
    }
}

// MARK: - Pantalla de bloqueo

struct RectangularScore: View {
    var snapshot: MatchupSnapshot?

    var body: some View {
        VStack(alignment: .leading, spacing: 1) {
            if let snapshot {
                Text("Semana \(snapshot.week)")
                    .font(.system(size: 11, weight: .semibold))
                    .widgetAccentable()
                Text("\(snapshot.me.points.fantasyPoints) – \(snapshot.opponentPoints.fantasyPoints)")
                    .font(.system(size: 16, weight: .bold, design: .rounded))
                    .monospacedDigit()
                Text(snapshot.opponent?.name ?? "Jornada de descanso")
                    .font(.system(size: 10))
                    .lineLimit(1)
            } else {
                Text("Marcador")
                Text("Sin datos")
            }
        }
    }
}

struct InlineScore: View {
    var snapshot: MatchupSnapshot?

    var body: some View {
        if let snapshot {
            Text("🏈 \(snapshot.me.points.fantasyPoints)–\(snapshot.opponentPoints.fantasyPoints)")
        } else {
            Text("🏈 sin datos")
        }
    }
}

// MARK: - Sin datos

struct EmptyState: View {
    var message: String?

    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: "sportscourt")
                .font(.system(size: 20))
                .foregroundStyle(Theme.accent)
            Text(message ?? "Abre la app y elige tu liga")
                .font(.system(size: 11))
                .multilineTextAlignment(.center)
                .foregroundStyle(.white.opacity(0.7))
        }
    }
}
