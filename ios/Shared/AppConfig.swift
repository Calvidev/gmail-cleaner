//  AppConfig.swift
//  Valores que la app y el widget comparten desde el primer arranque.

import Foundation

enum AppConfig {
    /// Grupo de apps: es lo que permite que el widget lea la liga que elegiste
    /// en la app. Si lo cambias aquí, cámbialo también en los dos archivos
    /// `.entitlements` (App > Signing & Capabilities > App Groups).
    static let appGroupID = "group.dev.calvi.sleeperscore"

    /// Liga de arranque. **Vacía a propósito**: una app publicada no puede
    /// traer la liga de su autor escrita dentro, o el primero que la instale
    /// vería un marcador ajeno. Para desarrollo se puede poner una aquí.
    static let defaultLeagueID = ""
    static let defaultRosterID = 1

    /// Verde menta del widget original.
    static let accentHex = "6EE7B7"

    /// Cada cuánto se refresca el marcador con la app abierta.
    static let foregroundRefreshSeconds: UInt64 = 60
}
