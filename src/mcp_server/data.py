"""Fuente de datos de futbol usada por las herramientas MCP.

Responsabilidad del Dev 3: mantener y ampliar estos datos (o reemplazar
por una integracion con una API real de estadisticas de futbol).
"""

TEAM_STATS = {
    "barcelona": {
        "nombre": "FC Barcelona",
        "titulos_liga": 27,
        "titulos_champions": 5,
        "estadio": "Spotify Camp Nou",
        "entrenador": "Hansi Flick",
    },
    "real_madrid": {
        "nombre": "Real Madrid CF",
        "titulos_liga": 36,
        "titulos_champions": 15,
        "estadio": "Santiago Bernabeu",
        "entrenador": "Carlo Ancelotti",
    },
}

PLAYER_STATS = {
    "lamine yamal": {
        "equipo": "barcelona",
        "posicion": "Extremo derecho",
        "goles_temporada": 9,
        "asistencias_temporada": 12,
    },
    "robert lewandowski": {
        "equipo": "barcelona",
        "posicion": "Delantero centro",
        "goles_temporada": 22,
        "asistencias_temporada": 5,
    },
    "pedri": {
        "equipo": "barcelona",
        "posicion": "Centrocampista",
        "goles_temporada": 4,
        "asistencias_temporada": 8,
    },
    "jude bellingham": {
        "equipo": "real_madrid",
        "posicion": "Centrocampista ofensivo",
        "goles_temporada": 15,
        "asistencias_temporada": 7,
    },
    "kylian mbappe": {
        "equipo": "real_madrid",
        "posicion": "Delantero centro",
        "goles_temporada": 24,
        "asistencias_temporada": 6,
    },
    "vinicius jr": {
        "equipo": "real_madrid",
        "posicion": "Extremo izquierdo",
        "goles_temporada": 18,
        "asistencias_temporada": 10,
    },
}

HEAD_TO_HEAD = {
    "ultimos_5_clasicos": [
        {"resultado": "Barcelona 4-0 Real Madrid", "competicion": "LaLiga"},
        {"resultado": "Real Madrid 0-4 Barcelona", "competicion": "Copa del Rey"},
        {"resultado": "Real Madrid 3-2 Barcelona", "competicion": "Supercopa"},
        {"resultado": "Barcelona 2-1 Real Madrid", "competicion": "LaLiga"},
        {"resultado": "Real Madrid 1-1 Barcelona", "competicion": "LaLiga"},
    ]
}
