//  AvatarLoader.swift
//  Avatares de Sleeper, guardados en disco para que el widget no dependa de la red.

import Foundation

enum AvatarLoader {
    private static let folderName = "Avatars"
    private static let maxAge: TimeInterval = 60 * 60 * 24 * 7  // una semana

    private static var folderURL: URL {
        let url = SharedStore.containerURL.appendingPathComponent(folderName, isDirectory: true)
        if !FileManager.default.fileExists(atPath: url.path) {
            try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        }
        return url
    }

    /// Bytes del avatar: de disco si están frescos, si no del CDN de Sleeper.
    /// Nunca lanza: un avatar que falta no puede tumbar el marcador.
    static func data(for url: URL?) async -> Data? {
        guard let url else { return nil }
        let cached = folderURL.appendingPathComponent("\(stableHash(url.absoluteString)).img")

        if let attributes = try? FileManager.default.attributesOfItem(atPath: cached.path),
           let modified = attributes[.modificationDate] as? Date,
           Date().timeIntervalSince(modified) < maxAge,
           let data = try? Data(contentsOf: cached) {
            return data
        }

        guard let downloaded = try? await SleeperAPI.shared.download(url) else {
            // Sin red vale hasta un avatar caducado.
            return try? Data(contentsOf: cached)
        }
        try? downloaded.write(to: cached, options: .atomic)
        return downloaded
    }
}
