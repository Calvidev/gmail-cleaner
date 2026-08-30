"""El motor de ranking: notas, orden, tiers y filtros."""

import pytest

from app.ranking import (
    assign_tiers,
    availability_score,
    age_score,
    consensus_score,
    fantasy_points,
    filter_ranked,
    games_played,
    momentum_score,
    opportunity_score,
    position_multiplier,
    primary_position,
    production_score,
    rank_players,
)
from app.models import Player


class TestFantasyPoints:
    def test_usa_los_puntos_ya_calculados_por_sleeper(self):
        assert fantasy_points({"pts_ppr": 231.4}, "ppr") == 231.4
        assert fantasy_points({"pts_std": 180.0, "pts_ppr": 231.4}, "standard") == 180.0

    def test_calcula_desde_las_estadisticas_si_faltan_los_puntos(self):
        stats = {"rec": 100, "rec_yd": 1200, "rec_td": 10}
        # 100 recepciones + 120 yardas + 60 de TD
        assert fantasy_points(stats, "ppr") == pytest.approx(280.0)
        assert fantasy_points(stats, "standard") == pytest.approx(180.0)

    def test_sin_datos_devuelve_cero(self):
        assert fantasy_points(None) == 0.0
        assert fantasy_points({}) == 0.0


class TestGamesPlayed:
    def test_lee_gp(self):
        assert games_played({"gp": 12}) == 12

    def test_sin_datos(self):
        assert games_played(None) == 0
        assert games_played({"pts_ppr": 10}) == 0


class TestConsensusScore:
    def test_mejor_rank_da_mejor_nota(self):
        mejor = Player(player_id="a", name="A", search_rank=1)
        peor = Player(player_id="b", name="B", search_rank=300)
        assert consensus_score(mejor) > consensus_score(peor)

    def test_sin_rank_da_nota_baja_pero_no_cero(self):
        nota = consensus_score(Player(player_id="a", name="A"))
        assert 0 < nota < 30


class TestOpportunityScore:
    def test_titular_por_encima_de_suplente(self):
        titular = Player(player_id="a", name="A", position="RB", team="KC", depth_chart_order=1)
        suplente = Player(player_id="b", name="B", position="RB", team="KC", depth_chart_order=3)
        assert opportunity_score(titular) > opportunity_score(suplente)

    def test_sin_equipo_es_casi_cero(self):
        assert opportunity_score(Player(player_id="a", name="A", position="WR")) < 10

    def test_el_wr3_conserva_valor_pero_el_rb3_no(self):
        wr3 = Player(player_id="a", name="A", position="WR", team="KC", depth_chart_order=3)
        rb3 = Player(player_id="b", name="B", position="RB", team="KC", depth_chart_order=3)
        assert opportunity_score(wr3) > opportunity_score(rb3)


class TestMomentumScore:
    def test_muchas_altas_suben_la_nota(self):
        assert momentum_score(40000, 0, 40000) > 90

    def test_mas_bajas_que_altas_baja_de_la_media(self):
        assert momentum_score(0, 30000, 40000) < 50

    def test_sin_tendencias_es_neutro(self):
        assert momentum_score(0, 0, 0) == 50.0


class TestAvailabilityScore:
    def test_sano_es_cien(self):
        assert availability_score(Player(player_id="a", name="A", team="KC", status="Active")) == 100

    def test_la_lesion_grave_castiga_mas_que_la_leve(self):
        ir = Player(player_id="a", name="A", team="KC", injury_status="IR")
        duda = Player(player_id="b", name="B", team="KC", injury_status="Questionable")
        assert availability_score(ir) < availability_score(duda) < 100


class TestAgeScore:
    def test_el_corredor_veterano_pierde_mas_que_el_quarterback(self):
        rb = Player(player_id="a", name="A", position="RB", age=32)
        qb = Player(player_id="b", name="B", position="QB", age=32)
        assert age_score(rb) < age_score(qb)

    def test_en_su_pico_la_nota_es_maxima(self):
        assert age_score(Player(player_id="a", name="A", position="RB", age=25)) == 100.0


class TestProductionScore:
    def test_con_temporada_avanzada_manda_lo_real(self):
        # 20 pts/partido sobre una referencia de 20 => 100
        assert production_score(20.0, 10, 5.0, 20.0) == pytest.approx(100.0)

    def test_sin_partidos_manda_la_proyeccion(self):
        assert production_score(0.0, 0, 10.0, 20.0) == pytest.approx(50.0)

    def test_con_pocos_partidos_se_mezcla(self):
        mezcla = production_score(20.0, 2, 0.0, 20.0)
        assert 0 < mezcla < 100


class TestPositionMultiplier:
    def test_en_ppr_el_receptor_vale_mas_que_en_estandar(self):
        assert position_multiplier("WR", "ppr") > position_multiplier("WR", "standard")

    def test_superflex_dispara_el_valor_del_quarterback(self):
        assert position_multiplier("QB", "ppr", superflex=True) > position_multiplier("QB", "ppr")


class TestPrimaryPosition:
    def test_usa_la_posicion_principal(self, sample_players):
        assert primary_position(sample_players["1"]) == "WR"

    def test_recurre_a_las_posiciones_de_fantasy(self):
        p = Player(player_id="a", name="A", position="FB", fantasy_positions=["RB"])
        assert primary_position(p) == "RB"


class TestRankPlayers:
    def test_ordena_del_mejor_al_peor(self, sample_players):
        ranked = rank_players(sample_players)
        notas = [r.score for r in ranked]
        assert notas == sorted(notas, reverse=True)
        assert [r.rank for r in ranked] == list(range(1, len(ranked) + 1))

    def test_la_estrella_manda_y_el_agente_libre_cierra(self, sample_players):
        ranked = rank_players(sample_players)
        assert ranked[0].player.name == "Ja'Marr Chase"
        assert ranked[-1].player.name == "Sin Equipo"

    def test_la_lesion_grave_hunde_al_jugador(self, sample_players):
        ranked = rank_players(sample_players)
        posiciones = {r.player.player_id: r.rank for r in ranked}
        # El lesionado tiene mejor consenso (8) que Mahomes (22) y aun así cae.
        assert posiciones["4"] > posiciones["3"]

    def test_numera_por_posicion(self, sample_players):
        ranked = rank_players(sample_players)
        receptores = [r for r in ranked if primary_position(r.player) == "WR"]
        assert [r.position_rank for r in receptores] == [1, 2, 3]

    def test_la_produccion_real_pesa(self, sample_players):
        sin_stats = rank_players(sample_players)
        con_stats = rank_players(
            sample_players, stats={"5": {"gp": 10, "pts_ppr": 250.0}}
        )
        antes = next(r for r in sin_stats if r.player.player_id == "5").score
        despues = next(r for r in con_stats if r.player.player_id == "5").score
        assert despues > antes

    def test_las_tendencias_pesan(self, sample_players):
        base = rank_players(sample_players)
        con_tendencia = rank_players(sample_players, trending_add={"5": 50000})
        antes = next(r for r in base if r.player.player_id == "5").score
        despues = next(r for r in con_tendencia if r.player.player_id == "5").score
        assert despues > antes

    def test_todos_generan_explicaciones(self, sample_players):
        for entry in rank_players(sample_players):
            assert entry.reasons, f"{entry.player.name} se quedó sin explicación"

    def test_la_nota_esta_entre_cero_y_cien(self, sample_players):
        for entry in rank_players(sample_players):
            assert 0 <= entry.score <= 100

    def test_superflex_sube_al_quarterback(self, sample_players):
        normal = rank_players(sample_players, superflex=False)
        flex = rank_players(sample_players, superflex=True)
        antes = next(r for r in normal if r.player.player_id == "3").score
        despues = next(r for r in flex if r.player.player_id == "3").score
        assert despues > antes

    def test_catalogo_vacio(self):
        assert rank_players({}) == []


class TestAssignTiers:
    def test_un_salto_grande_abre_un_tier_nuevo(self, sample_players):
        ranked = rank_players(sample_players)
        assign_tiers(ranked, gap=2.0)
        tiers = [r.tier for r in ranked]
        assert tiers[0] == 1
        assert tiers == sorted(tiers)  # nunca retrocede

    def test_sin_saltos_todos_comparten_tier(self, sample_players):
        ranked = rank_players(sample_players)
        assign_tiers(ranked, gap=1000.0)
        assert {r.tier for r in ranked} == {1}


class TestFilterRanked:
    @pytest.fixture
    def ranked(self, sample_players):
        return rank_players(sample_players)

    def test_filtra_por_posicion(self, ranked):
        assert all(primary_position(r.player) == "RB" for r in filter_ranked(ranked, position="RB"))

    def test_acepta_varias_posiciones(self, ranked):
        salida = filter_ranked(ranked, position="RB,QB")
        assert {primary_position(r.player) for r in salida} == {"RB", "QB"}

    def test_filtra_por_equipo(self, ranked):
        assert all(r.player.team == "KC" for r in filter_ranked(ranked, team="KC"))

    def test_busca_por_nombre(self, ranked):
        salida = filter_ranked(ranked, search="mahomes")
        assert len(salida) == 1 and salida[0].player.name == "Patrick Mahomes"

    def test_oculta_lesionados_graves(self, ranked):
        salida = filter_ranked(ranked, hide_injured=True)
        assert all(r.player.injury_status != "IR" for r in salida)

    def test_solo_lesionados(self, ranked):
        assert all(r.player.injury_status for r in filter_ranked(ranked, injured_only=True))

    def test_filtra_por_edad(self, ranked):
        assert all(
            r.player.age is None or r.player.age <= 26
            for r in filter_ranked(ranked, max_age=26)
        )

    def test_excluye_a_los_ya_fichados(self, ranked):
        salida = filter_ranked(ranked, available_only={"1", "3"})
        assert {r.player.player_id for r in salida} == {"2", "4", "5", "6"}

    def test_sin_filtros_no_cambia_nada(self, ranked):
        assert len(filter_ranked(ranked)) == len(ranked)

    def test_los_filtros_se_acumulan(self, ranked):
        salida = filter_ranked(ranked, position="WR", team="CIN")
        assert len(salida) == 1 and salida[0].player.player_id == "1"
