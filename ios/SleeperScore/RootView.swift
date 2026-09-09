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
            .navigationTitle("Marcador")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
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
