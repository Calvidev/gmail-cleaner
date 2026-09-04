//  Theme.swift
//  Los colores del widget original, en un solo sitio.

import SwiftUI

enum Theme {
    static let accent = Color(hex: AppConfig.accentHex)
    static let track = Color(hex: "3A3A3C")
    static let card = Color(hex: "1C1C1E")
    static let pill = Color(hex: "2A2A2B")

    static let background = LinearGradient(
        colors: [Color(hex: "161618"), Color(hex: "0D0D0F")],
        startPoint: .top,
        endPoint: .bottom
    )
}

extension Color {
    /// "6EE7B7" o "#6EE7B7". Si el texto no vale, sale gris en vez de reventar.
    init(hex: String) {
        var cleaned = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        if cleaned.hasPrefix("#") { cleaned.removeFirst() }
        guard cleaned.count == 6, let value = UInt32(cleaned, radix: 16) else {
            self = .gray
            return
        }
        self.init(
            .sRGB,
            red: Double((value >> 16) & 0xFF) / 255,
            green: Double((value >> 8) & 0xFF) / 255,
            blue: Double(value & 0xFF) / 255,
            opacity: 1
        )
    }
}
