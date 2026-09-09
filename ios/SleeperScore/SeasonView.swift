//  SeasonView.swift
//  Tu temporada de un vistazo: puntos por jornada, récord y rachas.

import Charts
import SwiftUI

@MainActor
final class SeasonModel: ObservableObject {
    @Published private(set) var history: SeasonHistory?
    @Published private(set) var isLoading = false
    @Published private(set) var error: String?

    private let service = MatchupService()

    func load(league: LeagueConfig, week: Int) async {
        history = await SeasonHistoryStore.shared.cached(for: league)
        isLoading = history == nil
        defer { isLoading = false }
        guard let season = try? await service.currentSeason(), !season.isEmpty else {
            error = "No se pudo saber la temporada en curso."
            return
        }
        history = await SeasonHistoryStore.shared.refresh(
            league: league, season: season, upTo: week
        )
    }
}

struct SeasonView: View {
    var league: LeagueConfig
    var week: Int

    @StateObject private var model = SeasonModel()

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                if let historia = model.history, !historia.played.isEmpty {
                    resumen(historia)
                    grafica(historia)
                    jornadas(historia)
                } else if model.isLoading {
                    ProgressView().padding(.top, 40)
                } else {
                    Hint(text: model.error ?? "Todavía no hay jornadas jugadas esta temporada.")
                }
            }
            .padding(16)
        }
        .scrollIndicators(.hidden)
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle("Mi temporada")
        .navigationBarTitleDisplayMode(.inline)
        .task { await model.load(league: league, week: week) }
    }

    private func resumen(_ historia: SeasonHistory) -> some View {
        let record = historia.record
        return HStack(spacing: 10) {
            StatTile(title: "Récord", value: "\(record.wins)-\(record.losses)")
            StatTile(title: "Media", value: historia.average.fantasyPoints)
            StatTile(title: "Mejor", value: historia.best?.points.fantasyPoints ?? "—")
            StatTile(title: "Peor", value: historia.worst?.points.fantasyPoints ?? "—")
        }
    }

    private func grafica(_ historia: SeasonHistory) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Puntos por jornada")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.white)

            Chart {
                ForEach(historia.played) { jornada in
                    BarMark(
                        x: .value("Jornada", jornada.week),
                        y: .value("Puntos", jornada.points)
                    )
                    .foregroundStyle(color(for: jornada))
                    .cornerRadius(4)
                }
                if historia.average > 0 {
                    RuleMark(y: .value("Media", historia.average))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
                        .foregroundStyle(.white.opacity(0.25))
                }
            }
            .chartYAxis {
                AxisMarks { _ in
                    AxisGridLine().foregroundStyle(.white.opacity(0.08))
                    AxisValueLabel().foregroundStyle(.white.opacity(0.4))
                }
            }
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 6)) { _ in
                    AxisValueLabel().foregroundStyle(.white.opacity(0.4))
                }
            }
            .frame(height: 180)
        }
        .padding(16)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private func jornadas(_ historia: SeasonHistory) -> some View {
        VStack(spacing: 0) {
            ForEach(historia.played.reversed()) { jornada in
                HStack {
                    Text("Semana \(jornada.week)")
                        .font(.system(size: 13))
                        .foregroundStyle(.white.opacity(0.7))
                    Spacer()
                    if let rival = jornada.opponentPoints {
                        Text("\(jornada.points.fantasyPoints) – \(rival.fantasyPoints)")
                            .font(.system(size: 13, weight: .medium))
                            .monospacedDigit()
                            .foregroundStyle(.white)
                    } else {
                        Text(jornada.points.fantasyPoints)
                            .font(.system(size: 13, weight: .medium))
                            .monospacedDigit()
                            .foregroundStyle(.white)
                    }
                    Text(resultado(jornada))
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(color(for: jornada))
                        .frame(width: 22)
                }
                .padding(.vertical, 9)
                if jornada.week != historia.played.first?.week {
                    Divider().overlay(Color.white.opacity(0.06))
                }
            }
        }
        .padding(16)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private func color(for jornada: WeekResult) -> Color {
        switch jornada.won {
        case true?: return Theme.accent
        case false?: return .red.opacity(0.75)
        default: return .white.opacity(0.35)
        }
    }

    private func resultado(_ jornada: WeekResult) -> String {
        switch jornada.won {
        case true?: return "V"
        case false?: return "D"
        default: return "—"
        }
    }
}

struct StatTile: View {
    var title: String
    var value: String

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 17, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(title)
                .font(.system(size: 10))
                .foregroundStyle(.white.opacity(0.45))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}
