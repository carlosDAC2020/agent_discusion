"""Servidor MCP que expone herramientas de estadisticas de futbol.

Responsabilidad del Dev 3: agregar/mantener herramientas aqui. Los agentes
(Dev 2) las consumen como cliente MCP via stdio, sin conocer esta
implementacion.

Ejecutar de forma standalone para probar:
    python -m src.mcp_server.server
"""

from mcp.server.fastmcp import FastMCP

from src.mcp_server.data import HEAD_TO_HEAD, PLAYER_STATS, TEAM_STATS

mcp = FastMCP("football-stats")


@mcp.tool()
def get_team_stats(team: str) -> dict:
    """Obtiene estadisticas generales de un equipo.

    Args:
        team: "barcelona" o "real_madrid".
    """
    key = team.strip().lower().replace(" ", "_")
    return TEAM_STATS.get(key, {"error": f"Equipo '{team}' no encontrado"})


@mcp.tool()
def get_player_stats(player_name: str) -> dict:
    """Obtiene estadisticas de un jugador por nombre.

    Args:
        player_name: nombre del jugador, ej. "Lamine Yamal".
    """
    key = player_name.strip().lower()
    return PLAYER_STATS.get(key, {"error": f"Jugador '{player_name}' no encontrado"})


@mcp.tool()
def compare_players(player_a: str, player_b: str) -> dict:
    """Compara estadisticas de dos jugadores.

    Args:
        player_a: nombre del primer jugador.
        player_b: nombre del segundo jugador.
    """
    a = PLAYER_STATS.get(player_a.strip().lower())
    b = PLAYER_STATS.get(player_b.strip().lower())
    if not a or not b:
        return {"error": "Uno o ambos jugadores no fueron encontrados"}
    return {player_a: a, player_b: b}


@mcp.tool()
def get_head_to_head() -> dict:
    """Obtiene el historial reciente de clasicos Barcelona vs Real Madrid."""
    return HEAD_TO_HEAD


if __name__ == "__main__":
    mcp.run(transport="stdio")
