//  PaywallView.swift
//  Lo que se ofrece al pasar a Pro.
//
//  Todavía no hay compra: falta dar de alta la suscripción en App Store
//  Connect y enchufar StoreKit. La pantalla existe para poder enseñar el
//  valor y para que el interruptor de pruebas permita probar el límite.

import SwiftUI

struct PaywallView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var plan = EntitlementStore.current.plan

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 22) {
                    VStack(spacing: 10) {
                        Image(systemName: "trophy.fill")
                            .font(.system(size: 42))
                            .foregroundStyle(Theme.accent)
                        Text("Todas tus ligas en una app")
                            .font(.title2.bold())
                            .foregroundStyle(.white)
                            .multilineTextAlignment(.center)
                        Text("El plan gratis sigue un equipo. Con Pro sigues todos, aunque estén en plataformas distintas.")
                            .font(.callout)
                            .multilineTextAlignment(.center)
                            .foregroundStyle(.white.opacity(0.7))
                    }
                    .padding(.top, 20)

                    VStack(spacing: 12) {
                        Benefit(icon: "square.stack.3d.up.fill", title: "Ligas ilimitadas",
                                detail: "Cambia de liga desde el marcador, sin volver a configurar nada.")
                        Benefit(icon: "rectangle.on.rectangle", title: "Un widget por liga",
                                detail: "Cada widget puede seguir un equipo distinto.")
                        Benefit(icon: "bell.badge.fill", title: "Avisos de todas",
                                detail: "Anotaciones y cambios de lesión de cualquiera de tus equipos.")
                        Benefit(icon: "person.2.fill", title: "Varias plataformas",
                                detail: "Sleeper hoy; Yahoo, ESPN y NFL.com según se vayan integrando.")
                    }

                    Text("La suscripción todavía no está activa: falta darla de alta en App Store Connect.")
                        .font(.footnote)
                        .multilineTextAlignment(.center)
                        .foregroundStyle(.white.opacity(0.45))
                        .padding(.horizontal)

                    #if DEBUG
                    Picker("Plan (pruebas)", selection: $plan) {
                        ForEach(Plan.allCases, id: \.self) { Text($0.title).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: plan) { _, nuevo in
                        EntitlementStore.set(plan: nuevo)
                    }
                    #endif
                }
                .padding(20)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Pro")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cerrar") { dismiss() }
                }
            }
        }
    }
}

private struct Benefit: View {
    var icon: String
    var title: String
    var detail: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundStyle(Theme.accent)
                .frame(width: 26)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.white)
                Text(detail)
                    .font(.system(size: 13))
                    .foregroundStyle(.white.opacity(0.6))
            }
            Spacer(minLength: 0)
        }
        .padding(14)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}
