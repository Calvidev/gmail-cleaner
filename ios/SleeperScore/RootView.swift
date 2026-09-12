//  RootView.swift

import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: ScoreboardModel
    @State private var showingSettings = false

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.background.ignoresSafeArea()
                if model.needsSetup {
                    SetupPrompt { showingSettings = true }
                } else {
                    ScoreboardView()
                }
            }
            .overlay {
                // Encima de todo y sin capturar toques.
                CelebrationOverlay(trigger: model.celebrationID)
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    LeaguePicker()
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showingSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                    .accessibilityLabel("Cuentas y ajustes")
                }
            }
            .toolbarBackground(Color(hex: "161618"), for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .sheet(isPresented: $showingSettings) {
            AccountsView()
                .environmentObject(model)
                .preferredColorScheme(.dark)
        }
        .task {
            model.startAutoRefresh()
        }
    }
}

/// El título de la barra: el nombre de la liga y, si hay varias, un menú para
/// saltar entre ellas sin pasar por ajustes.
struct LeaguePicker: View {
    @EnvironmentObject private var model: ScoreboardModel

    var body: some View {
        if model.hasMultipleLeagues {
            Menu {
                ForEach(model.book.leagues) { liga in
                    Button {
                        model.activate(liga)
                    } label: {
                        if liga.id == model.book.activeID {
                            Label(liga.displayName, systemImage: "checkmark")
                        } else {
                            Text(liga.displayName)
                        }
                    }
                }
            } label: {
                HStack(spacing: 4) {
                    Text(model.config.displayName)
                        .font(.headline)
                        .foregroundStyle(.white)
                        .lineLimit(1)
                    Image(systemName: "chevron.down")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(Theme.accent)
                }
            }
        } else {
            Text(model.needsSetup ? "Marcador" : model.config.displayName)
                .font(.headline)
                .foregroundStyle(.white)
                .lineLimit(1)
        }
    }
}

/// Primera pantalla cuando todavía no hay liga elegida.
struct SetupPrompt: View {
    var onOpenSettings: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "sportscourt")
                .font(.system(size: 44))
                .foregroundStyle(Theme.accent)
            Text("Entra con tu Sleeper")
                .font(.title2.bold())
                .foregroundStyle(.white)
            Text("Conecta tu cuenta y elige la liga. Con Sleeper basta tu nombre de usuario: no hace falta contraseña.")
                .font(.callout)
                .multilineTextAlignment(.center)
                .foregroundStyle(.white.opacity(0.7))
                .padding(.horizontal, 32)
            Button("Elegir plataforma", action: onOpenSettings)
                .buttonStyle(.borderedProminent)
        }
    }
}
