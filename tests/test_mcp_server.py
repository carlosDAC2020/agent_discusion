"""Pruebas unitarias para las herramientas del servidor MCP (Dev 3).

Ejecutar con Python puro:
    .venv/bin/python -m unittest tests/test_mcp_server.py
"""

import unittest

from src.mcp_server.server import (
    compare_players,
    get_head_to_head,
    get_head_to_head_summary,
    get_injuries_or_squad_status,
    get_player_stats,
    get_team_stats,
    get_trophies_comparison,
)


class TestMCPServerTools(unittest.TestCase):

    def test_get_team_stats_success(self):
        # Caso canonico
        stats_bcn = get_team_stats("barcelona")
        self.assertEqual(stats_bcn["nombre"], "FC Barcelona")
        self.assertEqual(stats_bcn["titulos_liga"], 27)
        self.assertEqual(stats_bcn["titulos_champions"], 5)
        self.assertIn("temporada_actual", stats_bcn)

        # Busqueda flexible (alias y mayusculas)
        stats_rm = get_team_stats("Real Madrid CF")
        self.assertEqual(stats_rm["nombre"], "Real Madrid CF")
        self.assertEqual(stats_rm["titulos_champions"], 15)

    def test_get_team_stats_not_found(self):
        res = get_team_stats("equipo_desconocido")
        self.assertIn("error", res)
        self.assertIn("no encontrado", res["error"])

    def test_get_player_stats_exact_and_alias(self):
        # Nombre canonico
        lamine = get_player_stats("Lamine Yamal")
        self.assertEqual(lamine["equipo"], "barcelona")
        self.assertEqual(lamine["posicion"], "Extremo derecho")
        self.assertIn("goles_temporada", lamine)
        self.assertIn("asistencias_temporada", lamine)

        # Alias "Vini"
        vini = get_player_stats("Vini")
        self.assertEqual(vini["equipo"], "real_madrid")
        self.assertEqual(vini["posicion"], "Extremo izquierdo")

        # Apodo "Lewy"
        lewy = get_player_stats("lewy")
        self.assertEqual(lewy["equipo"], "barcelona")
        self.assertEqual(lewy["goles_temporada"], 24)

    def test_get_player_stats_not_found(self):
        res = get_player_stats("jugador_ficticio")
        self.assertIn("error", res)
        self.assertIn("no encontrado", res["error"])

    def test_compare_players_success(self):
        res = compare_players("Yamal", "Mbappé")
        self.assertIn("Yamal", res)
        self.assertIn("Mbappé", res)
        self.assertEqual(res["Yamal"]["equipo"], "barcelona")
        self.assertEqual(res["Mbappé"]["equipo"], "real_madrid")

    def test_compare_players_partial_or_full_error(self):
        res1 = compare_players("Lamine", "desconocido_xyz")
        self.assertIn("error", res1)

        res2 = compare_players("nadie_1", "nadie_2")
        self.assertIn("error", res2)

    def test_get_head_to_head_contract(self):
        h2h = get_head_to_head()
        # Verificacion de contrato original
        self.assertIn("ultimos_5_clasicos", h2h)
        self.assertGreaterEqual(len(h2h["ultimos_5_clasicos"]), 5)
        # Verificacion de ampliacion
        self.assertIn("ultimos_10_clasicos", h2h)
        self.assertIn("balance_historico_oficial", h2h)

    def test_get_head_to_head_summary(self):
        summary = get_head_to_head_summary()
        self.assertIn("partidos_totales", summary)
        self.assertEqual(summary["partidos_totales"], 257)
        self.assertIn("victorias_real_madrid", summary)
        self.assertIn("victorias_barcelona", summary)

    def test_get_trophies_comparison(self):
        trophies = get_trophies_comparison()
        self.assertEqual(trophies["titulos_champions"]["real_madrid"], 15)
        self.assertEqual(trophies["titulos_champions"]["barcelona"], 5)
        self.assertEqual(trophies["titulos_champions"]["lider"], "Real Madrid")

        self.assertEqual(trophies["copas_del_rey"]["barcelona"], 31)
        self.assertEqual(trophies["copas_del_rey"]["real_madrid"], 20)
        self.assertEqual(trophies["copas_del_rey"]["lider"], "FC Barcelona")

    def test_get_injuries_or_squad_status(self):
        bcn_injuries = get_injuries_or_squad_status("barcelona")
        self.assertIn("lesionados", bcn_injuries)
        self.assertGreaterEqual(len(bcn_injuries["lesionados"]), 1)

        rm_injuries = get_injuries_or_squad_status("real_madrid")
        self.assertIn("lesionados", rm_injuries)
        self.assertGreaterEqual(len(rm_injuries["lesionados"]), 1)


if __name__ == "__main__":
    unittest.main()
