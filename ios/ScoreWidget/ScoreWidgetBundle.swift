//  ScoreWidgetBundle.swift

import SwiftUI
import WidgetKit

@main
struct ScoreWidgetBundle: WidgetBundle {
    var body: some Widget {
        ScoreWidget()
    }
}

struct ScoreWidget: Widget {
    private let kind = "ScoreWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: ScoreProvider()) { entry in
            ScoreWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Marcador Sleeper")
        .description("Tu enfrentamiento de la jornada, en vivo.")
        .supportedFamilies([
            .systemSmall,
            .systemMedium,
            .systemLarge,
            .accessoryRectangular,
            .accessoryInline,
        ])
    }
}
