//  FreeAgentsView.swift
//  Los agentes libres que merecen la pena, con filtro por posición.

import SwiftUI

@MainActor
final class FreeAgentsModel: ObservableObject {
    @Published private(set) var agents: [FreeAgent] = []
    @Published private(set) var isLoading = false
    @Published private(set) var error: String?
    @Published var position: String = "TODOS"

    private let service = MatchupService()

    var filtered: [FreeAgent] {
        guard position != "TODOS" else { return agents }
        return agents.filter { ($0.position ?? "").uppercased() == position }
    }

    func load(league: LeagueConfig) async {
        isLoading = agents.isEmpty
        error = nil
        defer { isLoading = false }
        do {
            agents = try await service.freeAgents(league: league)
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct FreeAgentsView: View {
    var league: LeagueConfig

    @StateObject private var model = FreeAgentsModel()
    private let posiciones = ["TODOS", "QB", "RB", "WR", "TE", "K", "DEF"]

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                filtro
                if model.isLoading {
                    ProgressView().padding(.top, 40)
                } else if let error = model.error {
                    ErrorNote(text: error)
                } else if model.filtered.isEmpty {
                    Hint(text: "No hay agentes libres con proyección en esa posición.")
                } else {
                    VStack(spacing: 0) {
                        ForEach(Array(model.filtered.enumerated()), id: \.element.id) { indice, agente in
                            FreeAgentRow(rank: indice + 1, agent: agente)
                            if agente.id != model.filtered.last?.id {
                                Divider().overlay(Color.white.opacity(0.06))
                            }
                        }
                    }
                    .padding(16)
                    .background(Theme.card, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                }
            }
            .padding(16)
        }
        .scrollIndicators(.hidden)
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle("Agentes libres")
        .navigationBarTitleDisplayMode(.inline)
        .task { await model.load(league: league) }
        .refreshable { await model.load(league: league) }
    }

    private var filtro: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(posiciones, id: \.self) { posicion in
                    Button {
                        model.position = posicion
                    } label: {
                        Text(posicion == "TODOS" ? "Todos" : posicion)
                            .font(.system(size: 12, weight: .semibold))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 7)
                            .background(
                                model.position == posicion ? Theme.accent.opacity(0.18) : Theme.card,
                                in: Capsule()
                            )
                            .foregroundStyle(
                                model.position == posicion ? Theme.accent : Color.white.opacity(0.6)
                            )
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

struct FreeAgentRow: View {
    var rank: Int
    var agent: FreeAgent

    var body: some View {
        HStack(spacing: 10) {
            Text("\(rank)")
                .font(.system(size: 12, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(.white.opacity(0.35))
                .frame(width: 20, alignment: .leading)

            PlayerHeadshot(
                line: PlayerLine(
                    playerID: agent.playerID, points: 0,
                    name: agent.name, position: agent.position, team: agent.team
                ),
                size: 32
            )

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Text(agent.name)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(.white)
                        .lineLimit(1)
                    if let lesion = agent.injuryLabel {
                        InjuryTag(label: lesion, severe: agent.injuryIsSevere)
                    }
                }
                HStack(spacing: 6) {
                    Text(agent.subtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(.white.opacity(0.45))
                    if agent.adds > 0 {
                        Label(compacto(agent.adds), systemImage: "arrow.up.right")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(Theme.accent.opacity(0.9))
                    }
                }
            }

            Spacer(minLength: 4)

            VStack(alignment: .trailing, spacing: 0) {
                Text(agent.projected.fantasyPoints)
                    .font(.system(size: 14, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(.white)
                Text("proyección")
                    .font(.system(size: 9))
                    .foregroundStyle(.white.opacity(0.35))
            }
        }
        .padding(.vertical, 8)
    }

    /// 12.400 fichajes se lee mejor como "12,4 k".
    private func compacto(_ numero: Int) -> String {
        if numero >= 1000 {
            return String(format: "%.1f k", Double(numero) / 1000)
        }
        return "\(numero)"
    }
}
