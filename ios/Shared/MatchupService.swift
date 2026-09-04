//  MatchupService.swift
//  Monta el marcador a partir de cinco llamadas a Sleeper.
//
//  Es el mismo camino que hacía el widget de Scriptable: estado -> jornada,
//  liga, managers, rosters y enfrentamientos de esa jornada. Lo usan igual la
//  app y el widget, así que los dos enseñan exactamente lo mismo.

import Foundation

struct MatchupService {
    var api: SleeperAPI = .shared

    func snapshot(for config: LeagueConfig) async throws -> MatchupSnapshot {
        guard config.isComplete else { throw SleeperError.leagueNotSet }
        let leagueID = config.leagueID.trimmingCharacters(in: .whitespaces)

        let state = try await api.state()
        let week = state.currentWeek

        // Las cuatro llamadas de liga no dependen entre sí: van a la vez.
        async let leagueTask = api.league(leagueID)
        async let usersTask = api.users(leagueID: leagueID)
        async let rostersTask = api.rosters(leagueID: leagueID)
        async let matchupsTask = api.matchups(leagueID: leagueID, week: week)

        let league = try await leagueTask
        let users = try await usersTask
        let rosters = try await rostersTask
        let matchups = try await matchupsTask

        guard let mineMatchup = matchups.first(where: { $0.rosterID == config.rosterID }) else {
            throw SleeperError.rosterNotFound(config.rosterID)
        }

        // El rival es el otro equipo con el mismo `matchup_id`. En semana de
        // descanso no hay ninguno, y eso es válido.
        let theirsMatchup = matchups.first { other in
            other.rosterID != mineMatchup.rosterID
                && other.matchupID != nil
                && other.matchupID == mineMatchup.matchupID
        }

        let rosterByID = Dictionary(rosters.map { ($0.rosterID, $0) }, uniquingKeysWith: { first, _ in first })
        let userByID = Dictionary(users.map { ($0.userID, $0) }, uniquingKeysWith: { first, _ in first })

        let myUser = user(for: mineMatchup.rosterID, rosters: rosterByID, users: userByID)
        let theirUser = theirsMatchup.flatMap {
            user(for: $0.rosterID, rosters: rosterByID, users: userByID)
        }

        // Los avatares se piden a la vez y no interrumpen nada si fallan.
        async let myAvatarTask = AvatarLoader.data(for: myUser?.avatarURL)
        async let theirAvatarTask = AvatarLoader.data(for: theirUser?.avatarURL)
        let myAvatar = await myAvatarTask
        let theirAvatar = await theirAvatarTask

        let me = TeamSide(
            rosterID: mineMatchup.rosterID,
            name: config.teamName ?? myUser?.preferredName ?? "Tu equipo",
            avatarURL: myUser?.avatarURL,
            avatarData: myAvatar,
            points: mineMatchup.points ?? 0,
            startersCount: mineMatchup.filledStarters.count,
            record: rosterByID[mineMatchup.rosterID]?.record
        )

        var opponent: TeamSide?
        if let theirsMatchup {
            opponent = TeamSide(
                rosterID: theirsMatchup.rosterID,
                name: theirUser?.preferredName ?? "Rival",
                avatarURL: theirUser?.avatarURL,
                avatarData: theirAvatar,
                points: theirsMatchup.points ?? 0,
                startersCount: theirsMatchup.filledStarters.count,
                record: rosterByID[theirsMatchup.rosterID]?.record
            )
        }

        let catalog = await PlayerCatalog.shared.cached()
        let lineup = buildLineup(
            slots: league.starterSlots,
            mine: mineMatchup,
            theirs: theirsMatchup,
            catalog: catalog
        )

        return MatchupSnapshot(
            leagueName: league.name ?? "Liga de Sleeper",
            week: week,
            me: me,
            opponent: opponent,
            lineup: lineup,
            updatedAt: Date(),
            isStale: false
        )
    }

    // MARK: - Piezas

    private func user(
        for rosterID: Int,
        rosters: [Int: Roster],
        users: [String: LeagueUser]
    ) -> LeagueUser? {
        guard let ownerID = rosters[rosterID]?.ownerID else { return nil }
        return users[ownerID]
    }

    /// Empareja hueco a hueco las dos alineaciones. Sleeper ordena `starters`
    /// igual que `roster_positions`, así que el índice ya es el hueco.
    private func buildLineup(
        slots: [String],
        mine: Matchup,
        theirs: Matchup?,
        catalog: [String: CatalogPlayer]
    ) -> [LineupRow] {
        let count = max(
            slots.count,
            max(mine.starters?.count ?? 0, theirs?.starters?.count ?? 0)
        )
        guard count > 0 else { return [] }

        var rows: [LineupRow] = []
        rows.reserveCapacity(count)
        for index in 0..<count {
            let slot = index < slots.count ? slots[index] : "FLEX"
            let row = LineupRow(
                index: index,
                slot: slot,
                mine: line(from: mine, at: index, catalog: catalog),
                theirs: theirs.flatMap { line(from: $0, at: index, catalog: catalog) }
            )
            if row.mine == nil && row.theirs == nil { continue }
            rows.append(row)
        }
        return rows
    }

    private func line(
        from matchup: Matchup,
        at index: Int,
        catalog: [String: CatalogPlayer]
    ) -> PlayerLine? {
        guard let starters = matchup.starters, index < starters.count else { return nil }
        let playerID = starters[index]
        guard playerID != "0", !playerID.isEmpty else { return nil }
        let entry = catalog[playerID]
        return PlayerLine(
            playerID: playerID,
            points: matchup.pointsForSlot(index),
            name: entry?.name,
            position: entry?.position,
            team: entry?.team
        )
    }
}

// MARK: - Equipos de una liga (para la pantalla de ajustes)

struct LeagueTeam: Identifiable, Hashable {
    let rosterID: Int
    let name: String
    let avatarURL: URL?
    let record: String?

    var id: Int { rosterID }
}

extension MatchupService {
    /// Los equipos de una liga, para elegir el tuyo sin saberte el número de roster.
    func teams(in leagueID: String) async throws -> (leagueName: String, teams: [LeagueTeam]) {
        let clean = leagueID.trimmingCharacters(in: .whitespaces)
        guard !clean.isEmpty else { throw SleeperError.leagueNotSet }

        async let leagueTask = api.league(clean)
        async let usersTask = api.users(leagueID: clean)
        async let rostersTask = api.rosters(leagueID: clean)

        let league = try await leagueTask
        let users = try await usersTask
        let rosters = try await rostersTask

        let userByID = Dictionary(users.map { ($0.userID, $0) }, uniquingKeysWith: { first, _ in first })
        let teams = rosters
            .sorted { $0.rosterID < $1.rosterID }
            .map { roster -> LeagueTeam in
                let owner = roster.ownerID.flatMap { userByID[$0] }
                return LeagueTeam(
                    rosterID: roster.rosterID,
                    name: owner?.preferredName ?? "Equipo \(roster.rosterID)",
                    avatarURL: owner?.avatarURL,
                    record: roster.record
                )
            }
        return (league.name ?? "Liga de Sleeper", teams)
    }
}
