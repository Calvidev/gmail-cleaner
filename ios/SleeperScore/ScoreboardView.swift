//  ScoreboardView.swift
//  El marcador del widget, en grande y con la alineación debajo.

import SwiftUI

struct ScoreboardView: View {
    @EnvironmentObject private var model: ScoreboardModel

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                if let snapshot = model.snapshot {
                    ScoreCard(snapshot: snapshot)
                    if !snapshot.lineup.isEmpty {
                        LineupSection(rows: snapshot.lineup)
                    } else {
                        Hint(text: "Cuando arranque la jornada aparecerá aquí la alineación titular con los puntos de cada jugador.")
                    }
                } else if model.isLoading {
                    ProgressView()
                        .padding(.top, 60)
                } else {
                    Hint(text: model.lastError ?? "Todavía no hay datos de esta jornada.")
                }

                if let error = model.lastError, model.snapshot != nil {
                    ErrorNote(text: error)
                }
            }
            .padding(16)
        }
        .scrollIndicators(.hidden)
        .refreshable {
            await model.refresh(showSpinner: false)
        }
    }
}

// MARK: - Tarjeta del marcador

struct ScoreCard: View {
    var snapshot: MatchupSnapshot

    var body: some View {
        VStack(spacing: 14) {
            LeagueHeader(leagueName: snapshot.leagueName, week: snapshot.week)

            HStack(alignment: .top, spacing: 10) {
                TeamColumn(
                    team: snapshot.me, alignment: .leading,
                    avatarSize: 34, scoreSize: 40
                )
                VStack(spacing: 6) {
                    Text("vs")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(.white.opacity(0.4))
                    DifferencePill(difference: snapshot.difference)
                }
                .padding(.top, 8)
                TeamColumn(
                    team: snapshot.opponent, alignment: .trailing,
                    avatarSize: 34, scoreSize: 40,
                    placeholder: "Jornada de descanso"
                )
            }

            ScoreBar(share: snapshot.myShare, height: 10)

            HStack {
                Label(
                    "Titulares \(snapshot.me.startersCount):\(snapshot.opponent?.startersCount ?? 0)",
                    systemImage: "person.3.fill"
                )
                Spacer()
                if snapshot.isStale {
                    Label("Datos guardados", systemImage: "wifi.slash")
                } else {
                    Text("Actualizado \(snapshot.updatedAt.hourAndMinute)")
                }
            }
            .font(.system(size: 11))
            .foregroundStyle(.white.opacity(0.55))
        }
        .padding(16)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            "\(snapshot.me.name) \(snapshot.me.points.fantasyPoints) puntos, "
            + "\(snapshot.opponent?.name ?? "sin rival") \(snapshot.opponentPoints.fantasyPoints) puntos"
        )
    }
}

// MARK: - Alineación

struct LineupSection: View {
    var rows: [LineupRow]

    private var myTotal: Double { rows.compactMap { $0.mine?.points }.reduce(0, +) }
    private var theirTotal: Double { rows.compactMap { $0.theirs?.points }.reduce(0, +) }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Alineación")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.white)
                Spacer()
                Text("\(myTotal.fantasyPoints) · \(theirTotal.fantasyPoints)")
                    .font(.system(size: 11))
                    .monospacedDigit()
                    .foregroundStyle(.white.opacity(0.5))
            }
            .padding(.bottom, 10)

            ForEach(rows) { row in
                LineupRowView(row: row)
                if row.id != rows.last?.id {
                    Divider().overlay(Color.white.opacity(0.06))
                }
            }
        }
        .padding(16)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

struct LineupRowView: View {
    var row: LineupRow

    private var myPoints: Double { row.mine?.points ?? 0 }
    private var theirPoints: Double { row.theirs?.points ?? 0 }

    var body: some View {
        HStack(spacing: 8) {
            PlayerCell(line: row.mine, alignment: .leading, winning: myPoints > theirPoints)

            Text(row.slotLabel)
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(.white.opacity(0.55))
                .frame(width: 46)
                .padding(.vertical, 3)
                .background(Theme.pill, in: Capsule())

            PlayerCell(line: row.theirs, alignment: .trailing, winning: theirPoints > myPoints)
        }
        .padding(.vertical, 7)
    }
}

struct PlayerCell: View {
    var line: PlayerLine?
    var alignment: HorizontalAlignment
    var winning: Bool

    var body: some View {
        HStack(spacing: 6) {
            if alignment == .trailing { points }
            VStack(alignment: alignment, spacing: 1) {
                Text(line?.displayName ?? "—")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(Color.white.opacity(line == nil ? 0.3 : 1))
                    .lineLimit(1)
                    .truncationMode(.tail)
                if !subtitle.isEmpty {
                    Text(subtitle)
                        .font(.system(size: 10))
                        .foregroundStyle(.white.opacity(0.45))
                        .lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity, alignment: alignment == .trailing ? .trailing : .leading)
            if alignment == .leading { points }
        }
    }

    private var subtitle: String { line?.subtitle ?? "" }

    private var points: some View {
        Text((line?.points ?? 0).fantasyPoints)
            .font(.system(size: 13, weight: .semibold, design: .rounded))
            .monospacedDigit()
            .foregroundStyle(winning ? Theme.accent : Color.white.opacity(0.8))
            .frame(width: 44, alignment: alignment == .trailing ? .leading : .trailing)
    }
}

// MARK: - Avisos

struct Hint: View {
    var text: String

    var body: some View {
        Text(text)
            .font(.callout)
            .foregroundStyle(.white.opacity(0.65))
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .padding(20)
            .background(Theme.card, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

struct ErrorNote: View {
    var text: String

    var body: some View {
        Label(text, systemImage: "exclamationmark.triangle.fill")
            .font(.footnote)
            .foregroundStyle(.orange)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(Color.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
    }
}
