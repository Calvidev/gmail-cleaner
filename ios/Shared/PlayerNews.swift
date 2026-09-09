//  PlayerNews.swift
//  Noticias de TUS jugadores, no de la NFL en general.
//
//  ESPN etiqueta cada artículo con los atletas que aparecen en él, y el
//  catálogo de Sleeper trae el id de ESPN de cada jugador. Cruzando las dos
//  cosas el emparejamiento es exacto: nada de buscar nombres dentro del texto
//  y acertar a medias.

import Foundation

struct NewsItem: Codable, Hashable, Identifiable {
    var id: String
    var headline: String
    var summary: String?
    var url: URL?
    var published: Date?
    /// Jugadores tuyos que aparecen, ya traducidos a ids de Sleeper.
    var playerIDs: [String]

    var age: String {
        guard let published else { return "" }
        let segundos = Date().timeIntervalSince(published)
        if segundos < 3600 { return "hace \(max(1, Int(segundos / 60))) min" }
        if segundos < 86_400 { return "hace \(Int(segundos / 3600)) h" }
        return "hace \(Int(segundos / 86_400)) d"
    }
}

actor NewsFeed {
    static let shared = NewsFeed()

    private let endpoint = URL(
        string: "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=50"
    )!
    private let fileName = "player-news.json"
    private let maxAge: TimeInterval = 60 * 15
    private var memory: [NewsItem]?
    private var fetchedAt: Date?

    private var fileURL: URL {
        SharedStore.containerURL.appendingPathComponent(fileName)
    }

    func cached() -> [NewsItem] {
        if let memory { return memory }
        guard
            let data = try? Data(contentsOf: fileURL),
            let guardadas = try? SharedJSON.decoder.decode([NewsItem].self, from: data)
        else {
            return []
        }
        memory = guardadas
        return guardadas
    }

    /// Descarga las noticias y se queda solo con las que hablan de jugadores
    /// que tienes en el marcador.
    @discardableResult
    func refresh(for playerIDs: Set<String>, catalog: [String: CatalogPlayer]) async -> [NewsItem] {
        if let fetchedAt, Date().timeIntervalSince(fetchedAt) < maxAge {
            return cached()
        }
        guard let data = try? await SleeperAPI.shared.download(endpoint) else {
            return cached()
        }

        // espn_id -> player_id, solo de los jugadores que te interesan.
        var porESPN: [String: String] = [:]
        for playerID in playerIDs {
            if let espn = catalog[playerID]?.espnID, !espn.isEmpty {
                porESPN[espn] = playerID
            }
        }

        let noticias = Self.parse(data, matching: porESPN)
        memory = noticias
        fetchedAt = Date()
        if let codificadas = try? SharedJSON.encoder.encode(noticias) {
            try? codificadas.write(to: fileURL, options: .atomic)
        }
        return noticias
    }

    // MARK: - Parseo

    private struct Respuesta: Decodable {
        struct Articulo: Decodable {
            struct Enlaces: Decodable {
                struct Web: Decodable { let href: String? }
                let web: Web?
            }
            struct Categoria: Decodable {
                struct Atleta: Decodable {
                    let id: Int?
                }
                let athlete: Atleta?
            }
            let headline: String?
            let description: String?
            let published: String?
            let links: Enlaces?
            let categories: [Categoria]?
        }
        let articles: [Articulo]?
    }

    static func parse(_ data: Data, matching porESPN: [String: String]) -> [NewsItem] {
        guard let respuesta = try? JSONDecoder().decode(Respuesta.self, from: data) else {
            return []
        }
        let formateador = ISO8601DateFormatter()

        var resultado: [NewsItem] = []
        for articulo in respuesta.articles ?? [] {
            guard let titular = articulo.headline, !titular.isEmpty else { continue }

            // Los atletas etiquetados que además son jugadores tuyos.
            var mios: [String] = []
            for categoria in articulo.categories ?? [] {
                guard let espnID = categoria.athlete?.id else { continue }
                if let playerID = porESPN[String(espnID)] { mios.append(playerID) }
            }
            guard !mios.isEmpty else { continue }

            let enlace = articulo.links?.web?.href
            resultado.append(
                NewsItem(
                    id: enlace ?? titular,
                    headline: titular,
                    summary: articulo.description,
                    url: enlace.flatMap(URL.init(string:)),
                    published: articulo.published.flatMap(formateador.date(from:)),
                    playerIDs: Array(Set(mios))
                )
            )
        }
        return resultado.sorted {
            ($0.published ?? .distantPast) > ($1.published ?? .distantPast)
        }
    }
}

/// Qué noticias ya se avisaron, para no repetir.
enum NewsSeen {
    private static let key = "seenNews"

    static func filterNew(_ items: [NewsItem]) -> [NewsItem] {
        let vistas = Set(SharedStore.defaults.stringArray(forKey: key) ?? [])
        let nuevas = items.filter { !vistas.contains($0.id) }
        // Se recuerdan las últimas 200: suficiente y no crece sin control.
        let actualizadas = Array((items.map(\.id) + vistas).prefix(200))
        SharedStore.defaults.set(actualizadas, forKey: key)
        return nuevas
    }
}
