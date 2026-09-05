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
                    .accessibilityLabel("Ajustes")
                }
            }
            .toolbarBackground(Color(hex: "161618"), for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .sheet(isPresented: $showingSettings) {
            SettingsView()
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
            Text("Escribe tu nombre de usuario de Sleeper y elige la liga de la lista. No hace falta contraseña ni buscar el id de la liga.")
                .font(.callout)
                .multilineTextAlignment(.center)
                .foregroundStyle(.white.opacity(0.7))
                .padding(.horizontal, 32)
            Button("Abrir ajustes", action: onOpenSettings)
                .buttonStyle(.borderedProminent)
        }
    }
}
