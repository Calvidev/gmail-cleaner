//  PlayerDetailView.swift
//  La ficha de un jugador: foto, lo que lleva hecho, lo que se espera de él,
//  su parte médico y las noticias que hablan de él.

import SwiftUI

struct PlayerDetailView: View {
    var line: PlayerLine
    var news: [NewsItem]
    var slot: String?

    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    private var suyas: [NewsItem] {
        news.filter { $0.playerIDs.contains(line.playerID) }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    cabecera
                    numeros
                    if !suyas.isEmpty { noticias }
                }
                .padding(16)
            }
            .scrollIndicators(.hidden)
            .background(Theme.background.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cerrar") { dismiss() }
                }
            }
        }
    }

    private var cabecera: some View {
        VStack(spacing: 10) {
            PlayerHeadshot(line: line, size: 84)
            Text(line.displayName)
                .font(.title3.bold())
                .foregroundStyle(.white)
                .multilineTextAlignment(.center)
            HStack(spacing: 8) {
                if !line.subtitle.isEmpty {
                    Text(line.subtitle)
                        .font(.system(size: 13))
                        .foregroundStyle(.white.opacity(0.55))
                }
                if let slot {
                    Text(slot)
                        .font(.system(size: 11, weight: .bold))
                        .padding(.horizontal, 7)
                        .padding(.vertical, 2)
                        .background(Theme.pill, in: Capsule())
                        .foregroundStyle(.white.opacity(0.6))
                }
                if let lesion = line.injuryLabel {
                    Text(lesion)
                        .font(.system(size: 11, weight: .bold))
                        .padding(.horizontal, 7)
                        .padding(.vertical, 2)
                        .background(
                            (line.injuryIsSevere ? Color.red : Color.orange).opacity(0.18),
                            in: Capsule()
                        )
                        .foregroundStyle(line.injuryIsSevere ? .red : .orange)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 8)
    }

    private var numeros: some View {
        VStack(spacing: 12) {
            HStack(spacing: 10) {
                StatTile(title: "Puntos", value: line.points.fantasyPoints)
                StatTile(
                    title: "Proyección",
                    value: line.projected.map { $0.fantasyPoints } ?? "—"
                )
                StatTile(title: "Diferencia", value: diferencia)
            }
            if let stats = line.stats, !stats.isEmpty {
                Text(stats)
                    .font(.system(size: 13))
                    .foregroundStyle(.white.opacity(0.7))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(14)
                    .background(Theme.card, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
        }
    }

    /// Cuánto va por encima o por debajo de lo que se esperaba de él.
    private var diferencia: String {
        guard let proyectado = line.projected else { return "—" }
        return (line.points - proyectado).signedFantasyPoints
    }

    private var noticias: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Noticias")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.white)
            ForEach(suyas) { noticia in
                Button {
                    if let url = noticia.url { openURL(url) }
                } label: {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(noticia.headline)
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(.white)
                            .multilineTextAlignment(.leading)
                        if let resumen = noticia.summary {
                            Text(resumen)
                                .font(.system(size: 11))
                                .foregroundStyle(.white.opacity(0.5))
                                .multilineTextAlignment(.leading)
                                .lineLimit(3)
                        }
                        Text(noticia.age)
                            .font(.system(size: 10))
                            .foregroundStyle(.white.opacity(0.35))
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(16)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}
