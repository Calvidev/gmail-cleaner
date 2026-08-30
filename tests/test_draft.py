"""Tablero de draft: orden de picks, huecos, escasez y recomendación."""

import pytest

from app.draft import (
    build_board,
    compute_needs,
    my_pick_numbers,
    needed_positions,
    parse_picks,
    pick_number,
    position_runs,
    roster_positions_from_draft,
    slot_on_the_clock,
    suggest_picks,
    tier_summaries,
)
from app.models import DraftNeed, DraftPick, Player, RankedPlayer


def jugador(pid, nombre, posicion, nota, rank=1, tier=1, pos_rank=1):
    return RankedPlayer(
        rank=rank, position_rank=pos_rank, tier=tier, score=nota,
        player=Player(player_id=pid, name=nombre, position=posicion,
                      fantasy_positions=[posicion], team="KC"),
    )


class TestOrdenDePicks:
    def test_la_primera_ronda_va_en_orden(self):
        assert pick_number(1, 1, 12) == 1
        assert pick_number(12, 1, 12) == 12

    def test_en_serpiente_la_segunda_ronda_va_al_reves(self):
        # Quien elige el primero en la ronda 1, elige el último en la ronda 2.
        assert pick_number(1, 2, 12) == 24
        assert pick_number(12, 2, 12) == 13

    def test_en_formato_lineal_no_se_invierte(self):
        assert pick_number(1, 2, 12, snake=False) == 13
        assert pick_number(12, 2, 12, snake=False) == 24

    def test_todos_mis_picks_de_un_draft(self):
        assert my_pick_numbers(3, 10, 4) == [3, 18, 23, 38]

    def test_sin_datos_no_hay_picks(self):
        assert my_pick_numbers(0, 10, 4) == []
        assert my_pick_numbers(3, 0, 4) == []

    def test_a_quien_le_toca_elegir(self):
        assert slot_on_the_clock(1, 12) == 1
        assert slot_on_the_clock(12, 12) == 12
        assert slot_on_the_clock(13, 12) == 12  # empieza la vuelta
        assert slot_on_the_clock(24, 12) == 1

    def test_el_turno_y_el_numero_de_pick_son_coherentes(self):
        # Lo que dice una función tiene que casar con lo que dice la otra.
        for slot in range(1, 13):
            for ronda in range(1, 6):
                numero = pick_number(slot, ronda, 12)
                assert slot_on_the_clock(numero, 12) == slot

    def test_pick_invalido(self):
        assert slot_on_the_clock(0, 12) is None
        assert slot_on_the_clock(5, 0) is None


class TestRosterPositionsFromDraft:
    def test_deduce_la_alineacion_de_los_ajustes(self):
        positions = roster_positions_from_draft({
            "slots_qb": 1, "slots_rb": 2, "slots_wr": 3, "slots_te": 1,
            "slots_flex": 1, "slots_k": 1, "slots_def": 1,
        })
        assert positions.count("RB") == 2
        assert positions.count("WR") == 3
        assert "FLEX" in positions

    def test_ajustes_vacios(self):
        assert roster_positions_from_draft({}) == []
        assert roster_positions_from_draft(None) == []

    def test_valores_basura_no_rompen(self):
        assert roster_positions_from_draft({"slots_qb": "x", "slots_rb": None}) == []


class TestParsePicks:
    def test_normaliza_los_picks(self):
        ranked = {"p1": jugador("p1", "Estrella", "WR", 90)}
        users = {"u1": {"user_id": "u1", "display_name": "Marcos"}}
        picks = parse_picks(
            [{"pick_no": 1, "round": 1, "draft_slot": 1, "roster_id": 3,
              "player_id": "p1", "picked_by": "u1"}],
            ranked, users, my_user_id="u1",
        )
        (pick,) = picks
        assert pick.player.name == "Estrella"
        assert pick.picked_by_name == "Marcos"
        assert pick.is_mine is True
        assert pick.score == 90

    def test_un_jugador_fuera_del_catalogo_se_reconstruye(self):
        picks = parse_picks(
            [{"pick_no": 1, "round": 1, "player_id": "nuevo",
              "metadata": {"first_name": "Rookie", "last_name": "Nuevo",
                           "position": "RB", "team": "SF"}}],
            {}, {},
        )
        assert picks[0].player.name == "Rookie Nuevo"
        assert picks[0].player.position == "RB"

    def test_los_picks_salen_ordenados(self):
        picks = parse_picks(
            [{"pick_no": 3, "round": 1, "player_id": "a"},
             {"pick_no": 1, "round": 1, "player_id": "b"}], {}, {},
        )
        assert [p.pick_no for p in picks] == [1, 3]

    def test_sin_picks(self):
        assert parse_picks([], {}, {}) == []
        assert parse_picks(None, {}, {}) == []


class TestPositionRuns:
    def test_cuenta_lo_que_sale_en_los_ultimos_picks(self):
        picks = [
            DraftPick(pick_no=i, round=1,
                      player=Player(player_id=str(i), name=f"J{i}", position=pos,
                                    fantasy_positions=[pos]))
            for i, pos in enumerate(["QB", "RB", "RB", "WR", "RB"], start=1)
        ]
        assert position_runs(picks) == {"QB": 1, "RB": 3, "WR": 1}

    def test_solo_mira_la_ventana_reciente(self):
        picks = [
            DraftPick(pick_no=i, round=1,
                      player=Player(player_id=str(i), name=f"J{i}", position="RB",
                                    fantasy_positions=["RB"]))
            for i in range(1, 21)
        ]
        assert position_runs(picks, window=5) == {"RB": 5}

    def test_sin_picks(self):
        assert position_runs([]) == {}


class TestComputeNeeds:
    ALINEACION = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "DEF", "BN", "BN"]

    def test_con_la_plantilla_vacia_falta_todo(self):
        needs = {n.position: n for n in compute_needs(self.ALINEACION, [])}
        assert needs["RB"].missing == 2
        assert needs["QB"].missing == 1
        assert needs["FLEX"].missing == 1
        assert needs["RB"].urgency == "alta"

    def test_lo_cubierto_deja_de_urgir(self):
        plantilla = [
            Player(player_id="1", name="QB", position="QB", fantasy_positions=["QB"]),
            Player(player_id="2", name="RB1", position="RB", fantasy_positions=["RB"]),
            Player(player_id="3", name="RB2", position="RB", fantasy_positions=["RB"]),
        ]
        needs = {n.position: n for n in compute_needs(self.ALINEACION, plantilla)}
        assert needs["QB"].missing == 0 and needs["QB"].urgency == "baja"
        assert needs["RB"].missing == 0

    def test_el_excedente_cubre_el_flex(self):
        # Tres corredores para dos huecos: el tercero tapa el FLEX.
        plantilla = [
            Player(player_id=str(i), name=f"RB{i}", position="RB", fantasy_positions=["RB"])
            for i in range(3)
        ]
        needs = {n.position: n for n in compute_needs(self.ALINEACION, plantilla)}
        assert needs["FLEX"].missing == 0

    def test_tener_de_mas_no_da_numeros_negativos(self):
        plantilla = [
            Player(player_id=str(i), name=f"QB{i}", position="QB", fantasy_positions=["QB"])
            for i in range(4)
        ]
        needs = {n.position: n for n in compute_needs(self.ALINEACION, plantilla)}
        assert needs["QB"].missing == 0
        assert needs["QB"].filled == 1  # solo cuenta el hueco que hay

    def test_con_pocas_rondas_todo_urge(self):
        needs = {n.position: n for n in compute_needs(self.ALINEACION, [], rounds_left=1)}
        assert needs["QB"].urgency == "alta"

    def test_el_flex_reparte_urgencia_entre_los_que_lo_ocupan(self):
        needs = [DraftNeed(position="FLEX", required=1, filled=0, missing=1, urgency="alta")]
        mapa = needed_positions(needs)
        assert mapa["RB"] == "alta" and mapa["WR"] == "alta" and mapa["TE"] == "alta"


class TestTierSummaries:
    def test_cuenta_los_que_quedan_por_tier(self):
        disponibles = [
            jugador("1", "A", "WR", 90, rank=1, tier=1),
            jugador("2", "B", "WR", 88, rank=2, tier=1),
            jugador("3", "C", "RB", 70, rank=3, tier=2),
        ]
        resumen = {(t.position, t.tier): t for t in tier_summaries(disponibles, 5)}
        assert resumen[("WR", 1)].remaining == 2
        assert resumen[("RB", 2)].best_available_rank == 3

    def test_un_tier_casi_vacio_es_un_precipicio(self):
        disponibles = [jugador("1", "A", "WR", 90, tier=1)]
        (resumen,) = tier_summaries(disponibles, picks_until_turn=20)
        assert resumen.cliff is True

    def test_con_muchos_disponibles_no_hay_precipicio(self):
        disponibles = [jugador(str(i), f"J{i}", "WR", 90 - i, rank=i, tier=1) for i in range(12)]
        (resumen,) = tier_summaries(disponibles, picks_until_turn=4)
        assert resumen.cliff is False


class TestSuggestPicks:
    def test_una_posicion_que_necesitas_sube(self):
        disponibles = [
            jugador("wr", "Receptor", "WR", 80, rank=1, tier=1),
            jugador("rb", "Corredor", "RB", 78, rank=2, tier=1),
        ]
        needs = [
            DraftNeed(position="RB", required=2, filled=0, missing=2, urgency="alta"),
            DraftNeed(position="WR", required=2, filled=2, missing=0, urgency="baja"),
        ]
        sugerencias = suggest_picks(disponibles, needs, {}, [], 10)
        assert sugerencias[0].player.name == "Corredor"

    def test_faltar_dos_pesa_mas_que_faltar_uno(self):
        disponibles = [jugador("rb", "Corredor", "RB", 70, rank=1, tier=1)]
        una = suggest_picks(
            disponibles,
            [DraftNeed(position="RB", required=2, filled=1, missing=1, urgency="media")],
            {}, [], 5,
        )
        dos = suggest_picks(
            disponibles,
            [DraftNeed(position="RB", required=2, filled=0, missing=2, urgency="alta")],
            {}, [], 5,
        )
        assert dos[0].value > una[0].value

    def test_una_racha_empuja_hacia_arriba(self):
        disponibles = [jugador("rb", "Corredor", "RB", 70, rank=1, tier=1)]
        needs = [DraftNeed(position="RB", required=2, filled=1, missing=1, urgency="media")]
        sin_racha = suggest_picks(disponibles, needs, {}, [], 5)
        con_racha = suggest_picks(disponibles, needs, {"RB": 6}, [], 5)
        assert con_racha[0].value > sin_racha[0].value
        assert any("Racha" in r for r in con_racha[0].reasons)

    def test_siempre_explica_el_porque(self):
        disponibles = [jugador("wr", "Receptor", "WR", 80, rank=1, tier=1)]
        (sugerencia,) = suggest_picks(disponibles, [], {}, [], 5, limit=1)
        assert sugerencia.reasons

    def test_sin_disponibles_no_sugiere_nada(self):
        assert suggest_picks([], [], {}, [], 5) == []


class TestBuildBoard:
    DRAFT = {
        "draft_id": "d1", "type": "snake", "status": "drafting", "season": "2026",
        "draft_order": {"yo": 2, "otro": 1},
        "slot_to_roster_id": {"1": 5, "2": 9},
        "settings": {"teams": 2, "rounds": 3, "slots_qb": 1, "slots_rb": 1, "slots_bn": 1},
    }

    @pytest.fixture
    def ranked(self):
        return [
            jugador("p1", "QB Bueno", "QB", 90, rank=1, tier=1),
            jugador("p2", "RB Bueno", "RB", 85, rank=2, tier=1),
            jugador("p3", "RB Normal", "RB", 60, rank=3, tier=2),
            jugador("p4", "QB Normal", "QB", 55, rank=4, tier=2),
        ]

    def test_tacha_del_tablero_a_los_ya_elegidos(self, ranked):
        picks = [{"pick_no": 1, "round": 1, "player_id": "p1", "picked_by": "otro"}]
        board = build_board(self.DRAFT, picks, ranked, [], my_user_id="yo")
        disponibles = {e.player.player_id for e in board.best_available}
        assert "p1" not in disponibles
        assert board.picks_made == 1

    def test_sabe_cuando_me_toca(self, ranked):
        picks = [{"pick_no": 1, "round": 1, "player_id": "p1", "picked_by": "otro"}]
        board = build_board(self.DRAFT, picks, ranked, [], my_user_id="yo")
        assert board.my_slot == 2
        assert board.on_the_clock_slot == 2
        assert board.is_my_turn is True
        assert board.picks_until_my_turn == 0

    def test_calcula_cuanto_falta_para_mi_turno(self, ranked):
        # Pick 3 abre la ronda 2, que en serpiente empieza por el puesto 2.
        picks = [
            {"pick_no": 1, "round": 1, "player_id": "p1", "picked_by": "otro"},
            {"pick_no": 2, "round": 1, "player_id": "p2", "picked_by": "yo"},
        ]
        board = build_board(self.DRAFT, picks, ranked, [], my_user_id="yo")
        assert board.my_next_pick_no == 3
        assert board.picks_until_my_turn == 0

    def test_separa_mi_plantilla(self, ranked):
        picks = [
            {"pick_no": 1, "round": 1, "player_id": "p1", "picked_by": "otro"},
            {"pick_no": 2, "round": 1, "player_id": "p2", "picked_by": "yo"},
        ]
        board = build_board(self.DRAFT, picks, ranked, [], my_user_id="yo")
        assert [p.player.name for p in board.my_roster] == ["RB Bueno"]

    def test_los_huecos_reflejan_lo_que_ya_tengo(self, ranked):
        picks = [{"pick_no": 2, "round": 1, "player_id": "p2", "picked_by": "yo"}]
        board = build_board(self.DRAFT, picks, ranked, [], my_user_id="yo")
        needs = {n.position: n for n in board.needs}
        assert needs["RB"].missing == 0  # ya cogí uno
        assert needs["QB"].missing == 1

    def test_antes_del_draft_es_una_chuleta(self, ranked):
        draft = {**self.DRAFT, "status": "pre_draft"}
        board = build_board(draft, [], ranked, [], my_user_id="yo")
        assert board.status == "pre_draft"
        assert board.picks_made == 0
        assert len(board.best_available) == len(ranked)
        assert board.my_roster == []
        assert any("no ha empezado" in w for w in board.warnings)
        assert board.suggestions  # aun así recomienda por dónde empezar

    def test_si_no_se_quien_soy_lo_avisa(self, ranked):
        board = build_board(self.DRAFT, [], ranked, [])
        assert board.my_slot is None
        assert any("puesto del orden" in w for w in board.warnings)

    def test_draft_terminado(self, ranked):
        draft = {**self.DRAFT, "status": "complete"}
        board = build_board(draft, [], ranked, [], my_user_id="yo")
        assert any("terminado" in w for w in board.warnings)

    def test_deduce_la_alineacion_del_propio_draft(self, ranked):
        board = build_board(self.DRAFT, [], ranked, [], my_user_id="yo")
        posiciones = {n.position for n in board.needs}
        assert posiciones == {"QB", "RB"}  # los del draft, sin banquillo


class TestDraftConDatosDeDemo:
    async def test_monta_el_tablero_de_la_liga(self, league_service):
        board = await league_service.get_draft_board()
        assert board.status == "drafting"
        assert board.teams == 4 and board.rounds == 12
        assert board.my_slot == 2
        assert board.picks_made == 14
        assert board.best_available
        assert board.suggestions

    async def test_no_recomienda_a_nadie_ya_elegido(self, league_service):
        board = await league_service.get_draft_board()
        elegidos = {p.player.player_id for p in board.recent_picks if p.player}
        sugeridos = {s.player.player_id for s in board.suggestions}
        assert not (elegidos & sugeridos)

    async def test_prioriza_la_posicion_que_mas_falta(self, league_service):
        board = await league_service.get_draft_board()
        # En la liga de ejemplo faltan dos corredores y hay racha de corredores.
        assert board.suggestions[0].player.position == "RB"

    async def test_detecta_la_racha(self, league_service):
        board = await league_service.get_draft_board()
        assert board.position_run.get("RB", 0) >= 4

    async def test_sin_liga_configurada_avisa(self, service):
        from app.service import LeagueNotConfigured

        with pytest.raises(LeagueNotConfigured):
            await service.get_draft_board()
