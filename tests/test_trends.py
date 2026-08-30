"""Motor de tendencias: series semanales, pendientes y señales."""

import pytest

from app.models import Player, WeekUsage
from app.trends import (
    build_week_usage,
    compute_trends,
    direction_of,
    filter_trends,
    has_usage_data,
    linear_slope,
    metric_trend,
    split_means,
    team_target_totals,
    trend_score,
)


def semanas(valores, metrica="opportunities"):
    """Construye una serie de jornadas con una métrica dada."""
    return [WeekUsage(week=i + 1, **{metrica: v}) for i, v in enumerate(valores)]


class TestLinearSlope:
    def test_serie_creciente_da_pendiente_positiva(self):
        assert linear_slope([1, 2, 3, 4]) == pytest.approx(1.0)

    def test_serie_decreciente_da_pendiente_negativa(self):
        assert linear_slope([4, 3, 2, 1]) == pytest.approx(-1.0)

    def test_serie_plana_da_cero(self):
        assert linear_slope([5, 5, 5]) == 0.0

    def test_serie_demasiado_corta(self):
        assert linear_slope([5]) == 0.0
        assert linear_slope([]) == 0.0


class TestSplitMeans:
    def test_separa_reciente_de_anterior(self):
        reciente, anterior = split_means([2, 2, 2, 8, 10], recent=2)
        assert reciente == pytest.approx(9.0)
        assert anterior == pytest.approx(2.0)

    def test_con_un_solo_valor_no_hay_anterior(self):
        reciente, anterior = split_means([7])
        assert reciente == 7 and anterior is None

    def test_serie_vacia(self):
        assert split_means([]) == (None, None)


class TestTeamTargetTotals:
    def test_suma_los_objetivos_de_cada_equipo(self):
        jugadores = {
            "1": Player(player_id="1", name="A", team="CIN", position="WR", fantasy_positions=["WR"]),
            "2": Player(player_id="2", name="B", team="CIN", position="WR", fantasy_positions=["WR"]),
            "3": Player(player_id="3", name="C", team="KC", position="WR", fantasy_positions=["WR"]),
        }
        stats = {"1": {"rec_tgt": 10}, "2": {"rec_tgt": 6}, "3": {"rec_tgt": 8}}
        assert team_target_totals(stats, jugadores) == {"CIN": 16.0, "KC": 8.0}

    def test_ignora_a_los_agentes_libres(self):
        jugadores = {"1": Player(player_id="1", name="A", position="WR", fantasy_positions=["WR"])}
        assert team_target_totals({"1": {"rec_tgt": 10}}, jugadores) == {}


class TestBuildWeekUsage:
    def test_normaliza_una_jornada(self):
        uso = build_week_usage(
            7,
            {"rec_tgt": 10, "rec": 7, "rec_yd": 95, "rush_att": 2, "off_snp": 55,
             "tm_off_snp": 65, "pts_ppr": 18.5},
            team_targets=30,
        )
        assert uso.week == 7
        assert uso.targets == 10 and uso.carries == 2
        assert uso.opportunities == 12  # objetivos + acarreos
        assert uso.snap_share == pytest.approx(55 / 65, abs=1e-4)
        assert uso.target_share == pytest.approx(10 / 30, abs=1e-4)
        assert uso.points == 18.5

    def test_sin_datos_de_equipo_no_hay_cuotas(self):
        uso = build_week_usage(1, {"rec_tgt": 5, "pts_ppr": 8}, team_targets=None)
        assert uso.target_share is None
        assert uso.snap_share is None

    def test_la_cuota_nunca_pasa_del_cien_por_cien(self):
        uso = build_week_usage(1, {"off_snp": 70, "tm_off_snp": 65}, team_targets=None)
        assert uso.snap_share == 1.0


class TestMetricTrend:
    def test_calcula_delta_y_porcentaje(self):
        t = metric_trend(semanas([4, 4, 4, 8, 8]), "opportunities", "Oportunidades")
        assert t.previous == pytest.approx(4.0)
        assert t.recent == pytest.approx(8.0)
        assert t.delta == pytest.approx(4.0)
        assert t.pct_change == pytest.approx(100.0)

    def test_con_menos_de_dos_jornadas_no_hay_tendencia(self):
        assert metric_trend(semanas([4]), "opportunities", "Oportunidades") is None


class TestTrendScore:
    def test_subir_el_volumen_da_nota_positiva(self):
        metricas = {"opportunities": metric_trend(semanas([4, 4, 4, 9, 10]), "opportunities", "O")}
        assert trend_score(metricas) > 40

    def test_bajar_el_volumen_da_nota_negativa(self):
        metricas = {"opportunities": metric_trend(semanas([12, 12, 10, 4, 3]), "opportunities", "O")}
        assert trend_score(metricas) < -40

    def test_sin_metricas_es_cero(self):
        assert trend_score({}) == 0.0

    def test_sin_datos_de_volumen_la_nota_se_amortigua(self):
        solo_puntos = {"points": metric_trend(semanas([4, 4, 4, 12, 12], "points"), "points", "P")}
        con_volumen = {
            "opportunities": metric_trend(semanas([4, 4, 4, 12, 12]), "opportunities", "O")
        }
        assert abs(trend_score(solo_puntos)) < abs(trend_score(con_volumen))

    def test_detecta_si_hay_datos_de_volumen(self):
        assert has_usage_data({"targets": metric_trend(semanas([1, 2]), "targets", "T")})
        assert not has_usage_data({"points": metric_trend(semanas([1, 2], "points"), "points", "P")})


class TestDirectionOf:
    def test_reparte_las_tres_direcciones(self):
        assert direction_of(40, 6) == "alza"
        assert direction_of(-40, 6) == "baja"
        assert direction_of(2, 6) == "estable"

    def test_con_pocas_jornadas_no_se_moja(self):
        assert direction_of(90, 2) == "sin datos"


class TestComputeTrends:
    @pytest.fixture
    def jugadores(self):
        return {
            "sube": Player(player_id="sube", name="Sube Mucho", first_name="Sube",
                           last_name="Mucho", position="WR", fantasy_positions=["WR"], team="CIN"),
            "baja": Player(player_id="baja", name="Baja Mucho", first_name="Baja",
                           last_name="Mucho", position="RB", fantasy_positions=["RB"], team="KC"),
            "quieto": Player(player_id="quieto", name="Sin Cambios", first_name="Sin",
                             last_name="Cambios", position="TE", fantasy_positions=["TE"], team="SF"),
        }

    @pytest.fixture
    def semanales(self):
        def stats(tgt, snaps, pts):
            return {"rec_tgt": tgt, "off_snp": snaps, "tm_off_snp": 65, "pts_ppr": pts, "gp": 1}

        return {
            1: {"sube": stats(2, 20, 4), "baja": stats(10, 60, 18), "quieto": stats(6, 45, 10)},
            2: {"sube": stats(3, 25, 5), "baja": stats(9, 58, 16), "quieto": stats(6, 45, 10)},
            3: {"sube": stats(4, 32, 7), "baja": stats(7, 45, 12), "quieto": stats(6, 46, 11)},
            4: {"sube": stats(9, 55, 15), "baja": stats(3, 25, 6), "quieto": stats(6, 44, 10)},
            5: {"sube": stats(11, 60, 19), "baja": stats(2, 18, 4), "quieto": stats(6, 45, 10)},
        }

    def test_separa_a_los_que_suben_de_los_que_bajan(self, jugadores, semanales):
        trends = {t.player.player_id: t for t in compute_trends(jugadores, semanales)}
        assert trends["sube"].direction == "alza"
        assert trends["baja"].direction == "baja"
        assert trends["quieto"].direction == "estable"

    def test_ordena_de_mayor_a_menor_tendencia(self, jugadores, semanales):
        trends = compute_trends(jugadores, semanales)
        notas = [t.trend_score for t in trends]
        assert notas == sorted(notas, reverse=True)

    def test_guarda_la_serie_completa(self, jugadores, semanales):
        trends = {t.player.player_id: t for t in compute_trends(jugadores, semanales)}
        assert [w.targets for w in trends["sube"].weeks] == [2, 3, 4, 9, 11]

    def test_genera_señales_legibles(self, jugadores, semanales):
        trends = {t.player.player_id: t for t in compute_trends(jugadores, semanales)}
        texto = " ".join(trends["sube"].signals)
        assert "objetivos" in texto and "snaps" in texto

    def test_avisa_cuando_sube_el_volumen_pero_no_los_puntos(self):
        jugador = {
            "x": Player(player_id="x", name="Volumen Sin Premio", first_name="Volumen",
                        last_name="Premio", position="WR", fantasy_positions=["WR"], team="NYJ")
        }
        # Muchos más objetivos, los mismos puntos.
        semanales = {
            w: {"x": {"rec_tgt": tgt, "off_snp": snp, "tm_off_snp": 65, "pts_ppr": 9.0, "gp": 1}}
            for w, (tgt, snp) in enumerate([(3, 25), (3, 28), (4, 30), (10, 58), (11, 60)], start=1)
        }
        (trend,) = compute_trends(jugador, semanales)
        assert any("todavía no" in s for s in trend.signals)

    def test_las_jornadas_sin_jugar_no_cuentan_como_bajon(self, jugadores, semanales):
        # Se le borra una jornada intermedia: debe seguir con 4, no inventarse un cero.
        del semanales[3]["quieto"]
        trends = {t.player.player_id: t for t in compute_trends(jugadores, semanales)}
        assert trends["quieto"].games_tracked == 4
        assert trends["quieto"].direction == "estable"

    def test_exige_un_minimo_de_jornadas(self, jugadores, semanales):
        recortado = {1: semanales[1], 2: semanales[2]}
        assert compute_trends(jugadores, recortado) == []

    def test_sin_jornadas_no_hay_nada(self, jugadores):
        assert compute_trends(jugadores, {}) == []


class TestFilterTrends:
    @pytest.fixture
    def trends(self, sample_players):
        semanales = {
            w: {
                "1": {"rec_tgt": w * 2, "off_snp": 30 + w * 5, "tm_off_snp": 65, "pts_ppr": w * 3.0, "gp": 1},
                "5": {"rush_att": 12 - w, "off_snp": 60 - w * 6, "tm_off_snp": 65, "pts_ppr": 14.0 - w, "gp": 1},
                "3": {"pass_att": 30, "off_snp": 65, "tm_off_snp": 65, "pts_ppr": 18.0, "gp": 1},
            }
            for w in range(1, 6)
        }
        return compute_trends(sample_players, semanales)

    def test_filtra_por_direccion(self, trends):
        assert all(t.direction == "alza" for t in filter_trends(trends, direction="alza"))

    def test_filtra_por_posicion(self, trends):
        salida = filter_trends(trends, position="WR")
        assert all(t.player.position == "WR" for t in salida)

    def test_filtra_por_equipo(self, trends):
        assert all(t.player.team == "CIN" for t in filter_trends(trends, team="CIN"))

    def test_busca_por_nombre(self, trends):
        salida = filter_trends(trends, search="chase")
        assert len(salida) == 1

    def test_exige_un_minimo_de_jornadas(self, trends):
        assert all(t.games_tracked >= 5 for t in filter_trends(trends, min_games=5))

    def test_excluye_a_los_ya_fichados(self, trends):
        salida = filter_trends(trends, available_only={"1"})
        assert all(t.player.player_id != "1" for t in salida)

    def test_sin_filtros_no_cambia_nada(self, trends):
        assert len(filter_trends(trends)) == len(trends)


class TestTrendsConDatosDeDemo:
    async def test_detecta_al_que_sube_en_los_datos_de_ejemplo(self, service):
        trends = await service.get_trends()
        por_nombre = {t.player.name: t for t in trends}
        # En los datos de demo, a Tyrone Tracy Jr. se le dispara el uso.
        assert por_nombre["Tyrone Tracy Jr."].direction == "alza"
        assert por_nombre["Davante Adams"].direction == "baja"

    async def test_cuelga_el_puesto_del_ranking(self, service):
        trends = await service.get_trends()
        assert any(t.rank is not None and t.score is not None for t in trends)

    async def test_reutiliza_la_cache(self, service):
        primero = await service.get_trends()
        assert (await service.get_trends()) is primero
