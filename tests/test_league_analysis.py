"""Análisis de liga: alineación óptima, debilidades e intercambios."""

import pytest

from app.league_analysis import (
    DEFAULT_ROSTER_POSITIONS,
    analyze_league,
    find_trades,
    lineup_value,
    optimal_lineup,
    slot_accepts,
    startable_positions,
    starting_slots,
)
from app.models import Player, RankedPlayer


def jugador(pid: str, nombre: str, posicion: str, nota: float) -> RankedPlayer:
    return RankedPlayer(
        rank=1,
        score=nota,
        player=Player(
            player_id=pid, name=nombre, position=posicion,
            fantasy_positions=[posicion], team="KC",
        ),
    )


class TestStartingSlots:
    def test_quita_banquillo_y_lesionados(self):
        assert starting_slots(["QB", "RB", "BN", "IR", "TAXI"]) == ["QB", "RB"]

    def test_sin_configuracion_usa_la_estandar(self):
        assert starting_slots(None) == DEFAULT_ROSTER_POSITIONS


class TestSlotAccepts:
    def test_un_hueco_fijo_solo_admite_su_posicion(self):
        assert slot_accepts("QB", "QB")
        assert not slot_accepts("QB", "RB")

    def test_el_flex_admite_corredor_receptor_y_ala_cerrada(self):
        assert slot_accepts("FLEX", "RB")
        assert slot_accepts("FLEX", "TE")
        assert not slot_accepts("FLEX", "QB")

    def test_el_superflex_admite_quarterback(self):
        assert slot_accepts("SUPER_FLEX", "QB")


class TestStartablePositions:
    def test_saca_las_posiciones_que_se_alinean(self):
        assert startable_positions(["QB", "RB", "FLEX", "K"]) == {"QB", "RB", "WR", "TE", "K"}

    def test_una_liga_sin_pateador_no_incluye_K(self):
        assert "K" not in startable_positions(["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "DEF"])


class TestOptimalLineup:
    def test_coloca_a_los_mejores(self):
        plantilla = [
            jugador("1", "QB bueno", "QB", 80),
            jugador("2", "QB malo", "QB", 40),
            jugador("3", "RB bueno", "RB", 70),
            jugador("4", "RB malo", "RB", 30),
        ]
        titulares, banquillo, total = optimal_lineup(plantilla, ["QB", "RB"])
        assert {t.player.name for t in titulares} == {"QB bueno", "RB bueno"}
        assert total == 150.0
        assert len(banquillo) == 2

    def test_no_gasta_al_mejor_receptor_en_el_flex(self):
        plantilla = [
            jugador("1", "WR1", "WR", 90),
            jugador("2", "WR2", "WR", 60),
            jugador("3", "RB1", "RB", 55),
        ]
        titulares, _, total = optimal_lineup(plantilla, ["WR", "FLEX"])
        # WR1 al hueco de WR y el mejor de los que quedan al FLEX.
        assert total == 150.0
        assert {t.player.name for t in titulares} == {"WR1", "WR2"}

    def test_un_hueco_sin_candidato_se_queda_vacio(self):
        titulares, _, total = optimal_lineup([jugador("1", "RB", "RB", 50)], ["QB", "RB"])
        assert len(titulares) == 1 and total == 50.0

    def test_plantilla_vacia(self):
        assert optimal_lineup([], ["QB"]) == ([], [], 0.0)

    def test_lineup_value_coincide_con_el_total(self):
        plantilla = [jugador("1", "A", "QB", 80), jugador("2", "B", "RB", 70)]
        assert lineup_value(plantilla, ["QB", "RB"]) == 150.0


class TestAnalyzeLeague:
    @pytest.fixture
    async def analisis(self, league_service):
        ranked = await league_service.get_ranking("ppr")
        info = await league_service.get_league_info()
        return analyze_league(
            info["league"], info["rosters"], info["users"], ranked, my_user_id="100001"
        )

    async def test_analiza_a_todos_los_equipos(self, analisis):
        assert len(analisis.teams) == 4
        assert all(t.total_score > 0 for t in analisis.teams)

    async def test_ordena_por_valor_de_plantilla(self, analisis):
        totales = [t.total_score for t in analisis.teams]
        assert totales == sorted(totales, reverse=True)
        assert analisis.teams[0].rank_in_league == 1

    async def test_encuentra_mi_equipo(self, analisis):
        assert analisis.me is not None
        assert analisis.me.is_me
        assert analisis.me.team_name == "Los Fantasmas"

    async def test_detecta_mis_puntos_debiles(self, analisis):
        # La liga de ejemplo está montada con este equipo flojo de corredores.
        assert "RB" in analisis.me.weaknesses
        assert "WR" in analisis.me.strengths

    async def test_no_juzga_posiciones_que_la_liga_no_alinea(self, analisis):
        # La liga de ejemplo no tiene hueco de pateador.
        assert "K" not in analisis.me.positions

    async def test_cada_posicion_se_compara_con_la_liga(self, analisis):
        bloque = analisis.me.positions["RB"]
        assert bloque.league_avg > 0
        assert bloque.rank_in_league is not None
        assert 0 <= bloque.percentile <= 100
        assert bloque.verdict in ("débil", "medio", "fuerte")

    async def test_propone_intercambios_que_suman_a_los_dos(self, analisis):
        assert analisis.trade_ideas
        for idea in analisis.trade_ideas:
            assert idea.my_gain > 0
            assert idea.their_gain > 0
            assert idea.rationale

    async def test_los_intercambios_tapan_mis_huecos(self, analisis):
        posiciones_pedidas = {
            i.get[0].player.position for i in analisis.trade_ideas
        }
        assert posiciones_pedidas <= set(analisis.me.weaknesses)

    async def test_nunca_cambia_una_posicion_por_la_misma(self, analisis):
        for idea in analisis.trade_ideas:
            assert idea.give[0].player.position != idea.get[0].player.position

    async def test_no_repite_la_misma_pareja(self, analisis):
        parejas = [
            (i.give[0].player.player_id, i.get[0].player.player_id)
            for i in analisis.trade_ideas
        ]
        assert len(parejas) == len(set(parejas))

    async def test_deduce_mi_equipo_por_el_nombre_de_usuario(self, league_service):
        ranked = await league_service.get_ranking("ppr")
        info = await league_service.get_league_info()
        analisis = analyze_league(
            info["league"], info["rosters"], info["users"], ranked, my_username="calvidev"
        )
        assert analisis.me is not None and analisis.me.team_name == "Los Fantasmas"

    async def test_sin_identificarme_avisa(self, league_service):
        ranked = await league_service.get_ranking("ppr")
        info = await league_service.get_league_info()
        analisis = analyze_league(info["league"], info["rosters"], info["users"], ranked)
        assert analisis.me is None
        assert analisis.warnings
        assert analisis.teams  # la liga entera sí se ve

    async def test_un_usuario_que_no_esta_en_la_liga_avisa(self, league_service):
        ranked = await league_service.get_ranking("ppr")
        info = await league_service.get_league_info()
        analisis = analyze_league(
            info["league"], info["rosters"], info["users"], ranked, my_user_id="000000"
        )
        assert analisis.me is None
        assert any("no encontré tu equipo" in w.lower() for w in analisis.warnings)


class TestFindTrades:
    def test_sin_debilidades_no_propone_nada(self):
        from app.models import TeamAnalysis

        equipo = TeamAnalysis(roster_id=1, weaknesses=[], strengths=["WR"])
        assert find_trades(equipo, [equipo], DEFAULT_ROSTER_POSITIONS) == []
