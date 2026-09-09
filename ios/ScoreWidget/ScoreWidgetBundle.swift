//  ScoreWidgetBundle.swift

import AppIntents
import SwiftUI
import WidgetKit

@main
struct ScoreWidgetBundle: WidgetBundle {
    var body: some Widget {
        ScoreWidget()
        MatchupLiveActivity()
    }
}

struct ScoreWidget: Widget {
    private let kind = "ScoreWidget"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(
            kind: kind,
            intent: SelectLeagueIntent.self,
            provider: ScoreProvider()
        ) { entry in
            ScoreWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Marcador")
        .description("Tu enfrentamiento de la jornada, en vivo. Mantén pulsado para elegir liga.")
        .supportedFamilies([
            .systemSmall,
            .systemMedium,
            .systemLarge,
            .accessoryRectangular,
            .accessoryInline,
        ])
    }
}
