"""Servidor MCP que expone herramientas de estadisticas de futbol.

Responsabilidad del Dev 3: agregar/mantener herramientas aqui. Los agentes
(Dev 2) las consumen como cliente MCP via stdio, sin conocer esta
implementacion.

Ejecutar de forma standalone para probar:
    python -m src.mcp_server.server
"""

from typing import Dict

from mcp.server.fastmcp import FastMCP

from src.mcp_server.data import (
    HEAD_TO_HEAD,
    INJURIES_AND_SQUAD_STATUS,
    PLAYER_STATS,
    TEAM_STATS,
    resolve_player_key,
    resolve_team_key,
)

mcp = FastMCP("football-stats")


@mcp.tool()
def get_team_stats(team: str) -> dict:
    """Obtiene estadisticas generales, palmares y rendimiento actual de un equipo.

    Args:
        team: Nombre del equipo, ej. 'barcelona', 'real_madrid', 'Barca' o 'Real Madrid'.

    Returns:
        Diccionario con titulos de liga, champions, copas del rey, estadio,
        entrenador y datos de la temporada actual. Si no se encuentra, retorna un dict con 'error'.
    """
    key = resolve_team_key(team)
    if not key or key not in TEAM_STATS:
        return {
            "error": f"Equipo '{team}' no encontrado. Equipos disponibles: 'barcelona', 'real_madrid'."
        }
    return TEAM_STATS[key]


@mcp.tool()
def get_player_stats(player_name: str) -> dict:
    """Obtiene estadisticas de rendimiento y datos clave de un jugador por nombre o apodo.

    Args:
        player_name: Nombre o alias del jugador, ej. 'Lamine Yamal', 'Lewandowski',
                     'Vinicius Jr', 'Vini', 'Mbappe', 'Bellingham', 'Pedri', 'Raphinha'.

    Returns:
        Diccionario con equipo, posicion, goles_temporada, asistencias_temporada,
        dorsal, edad, nacionalidad y datos clave. Si no se encuentra, retorna dict con 'error'.
    """
    key = resolve_player_key(player_name)
    if not key or key not in PLAYER_STATS:
        return {
            "error": (
                f"Jugador '{player_name}' no encontrado. "
                f"Algunos disponibles: Lamine Yamal, Lewandowski, Raphinha, Pedri, "
                f"Mbappe, Vinicius Jr, Bellingham, Valverde, Courtois, Cubarsi."
            )
        }
    return PLAYER_STATS[key]


@mcp.tool()
def compare_players(player_a: str, player_b: str) -> dict:
    """Compara estadisticas individuales de dos jugadores frente a frente.

    Args:
        player_a: Nombre o apodo del primer jugador (ej. 'Lamine Yamal' o 'Mbappe').
        player_b: Nombre o apodo del segundo jugador (ej. 'Vinicius Jr' o 'Lewandowski').

    Returns:
        Diccionario comparativo con los datos de ambos jugadores, o dict con 'error'
        si alguno no fue encontrado.
    """
    key_a = resolve_player_key(player_a)
    key_b = resolve_player_key(player_b)

    data_a = PLAYER_STATS.get(key_a) if key_a else None
    data_b = PLAYER_STATS.get(key_b) if key_b else None

    if not data_a and not data_b:
        return {"error": f"Ninguno de los dos jugadores fue encontrado ('{player_a}', '{player_b}')."}
    if not data_a:
        return {"error": f"Jugador '{player_a}' no encontrado en la base de datos."}
    if not data_b:
        return {"error": f"Jugador '{player_b}' no encontrado en la base de datos."}

    # Conservamos los nombres provistos por el usuario como claves para retrocompatibilidad
    return {player_a: data_a, player_b: data_b}


@mcp.tool()
def get_head_to_head() -> dict:
    """Obtiene el historial de clasicos Barcelona vs Real Madrid (ultimos partidos y balance).

    Returns:
        Diccionario con ultimos clasicos jugados, balance historico oficial y mayores goleadas.
    """
    return HEAD_TO_HEAD


@mcp.tool()
def get_head_to_head_summary() -> dict:
    """Obtiene un resumen cuantitativo del historial oficial entre Real Madrid y FC Barcelona.

    Returns:
        Diccionario con total de clasicos disputados, victorias de cada club,
        empates, goles anotados por cada uno y desglose por competicion.
    """
    return HEAD_TO_HEAD.get("balance_historico_oficial", {})


@mcp.tool()
def get_trophies_comparison() -> dict:
    """Compara el palmares historico de titulos oficiales entre FC Barcelona y Real Madrid.

    Returns:
        Diccionario con la comparativa directa en Champions League, Ligas, Copas del Rey,
        Supercopas de Espana, Mundiales de Clubes y titulos totales oficiales.
    """
    barca = TEAM_STATS["barcelona"]
    madrid = TEAM_STATS["real_madrid"]

    return {
        "titulos_champions": {
            "real_madrid": madrid["titulos_champions"],
            "barcelona": barca["titulos_champions"],
            "lider": "Real Madrid",
        },
        "titulos_liga": {
            "real_madrid": madrid["titulos_liga"],
            "barcelona": barca["titulos_liga"],
            "lider": "Real Madrid",
        },
        "copas_del_rey": {
            "barcelona": barca["copas_del_rey"],
            "real_madrid": madrid["copas_del_rey"],
            "lider": "FC Barcelona",
        },
        "supercopas_espana": {
            "barcelona": barca["supercopas_espana"],
            "real_madrid": madrid["supercopas_espana"],
            "lider": "FC Barcelona",
        },
        "mundiales_clubes": {
            "real_madrid": madrid["mundiales_clubes"],
            "barcelona": barca["mundiales_clubes"],
            "lider": "Real Madrid",
        },
        "titulos_totales_oficiales": {
            "real_madrid": madrid["titulos_totales_oficiales"],
            "barcelona": barca["titulos_totales_oficiales"],
        },
        "destacados_barcelona": barca.get("palmares_destacado", []),
        "destacados_real_madrid": madrid.get("palmares_destacado", []),
    }


@mcp.tool()
def get_injuries_or_squad_status(team: str) -> dict:
    """Consulta el estado de la enfermeria, jugadores lesionados o bajas de un equipo.

    Args:
        team: Nombre del equipo ('barcelona' o 'real_madrid').

    Returns:
        Diccionario con la lista de jugadores lesionados, tipo de lesion, tiempo estimado
        de recuperacion y diagnostico general de disponibilidad de la plantilla.
    """
    key = resolve_team_key(team)
    if not key or key not in INJURIES_AND_SQUAD_STATUS:
        return {
            "error": f"Equipo '{team}' no encontrado. Use 'barcelona' o 'real_madrid'."
        }
    return INJURIES_AND_SQUAD_STATUS[key]


if __name__ == "__main__":
    mcp.run(transport="stdio")
