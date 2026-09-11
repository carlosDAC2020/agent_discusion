"""Fuente de datos de futbol enriquecida para las herramientas MCP.

Responsabilidad del Dev 3: mantener y ampliar estos datos.
Compatible 100% con los contratos existentes para Dev 1 y Dev 2.
"""

import unicodedata
from typing import Optional


def normalize_text(text: str) -> str:
    """Normaliza texto: minusculas, sin espacios extra y sin tildes."""
    if not text:
        return ""
    text = text.strip().lower()
    # Eliminar diacriticos/tildes
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


TEAM_STATS = {
    "barcelona": {
        "nombre": "FC Barcelona",
        "fundacion": 1899,
        "estadio": "Spotify Camp Nou",
        "entrenador": "Hansi Flick",
        "titulos_liga": 27,
        "titulos_champions": 5,
        "copas_del_rey": 31,
        "supercopas_espana": 14,
        "mundiales_clubes": 3,
        "titulos_totales_oficiales": 99,
        "palmares_destacado": [
            "Sextete historico en 2009 (unico club espanol con todos los titulos de un ano natural)",
            "2 Tripletes (2008-09 y 2014-15)",
            "Rey de Copas en Espana (31 Copas del Rey)",
        ],
        "temporada_actual": {
            "competicion": "LaLiga 2024-2025",
            "posicion": 1,
            "partidos_jugados": 24,
            "victorias": 17,
            "empates": 3,
            "derrotas": 4,
            "goles_a_favor": 64,
            "goles_en_contra": 24,
            "diferencia_goles": 40,
            "puntos": 54,
            "estado_champions": "Clasificado directamente a octavos de final (Top 8 fase liga)",
        },
    },
    "real_madrid": {
        "nombre": "Real Madrid CF",
        "fundacion": 1902,
        "estadio": "Santiago Bernabeu",
        "entrenador": "Carlo Ancelotti",
        "titulos_liga": 36,
        "titulos_champions": 15,
        "copas_del_rey": 20,
        "supercopas_espana": 13,
        "mundiales_clubes": 8,
        "titulos_totales_oficiales": 104,
        "palmares_destacado": [
            "Rey indiscutible de Europa con 15 Copas de Europa / UEFA Champions League",
            "3 Champions consecutivas en era moderna (2016, 2017, 2018)",
            "Maximo campeon historico de LaLiga (36 titulos)",
        ],
        "temporada_actual": {
            "competicion": "LaLiga 2024-2025",
            "posicion": 2,
            "partidos_jugados": 24,
            "victorias": 16,
            "empates": 4,
            "derrotas": 4,
            "goles_a_favor": 52,
            "goles_en_contra": 22,
            "diferencia_goles": 30,
            "puntos": 52,
            "estado_champions": "En eliminatorias de Champions League",
        },
    },
}

PLAYER_STATS = {
    # --- FC BARCELONA ---
    "lamine yamal": {
        "equipo": "barcelona",
        "dorsal": 19,
        "posicion": "Extremo derecho",
        "edad": 17,
        "nacionalidad": "Espanola",
        "partidos_temporada": 26,
        "goles_temporada": 9,
        "asistencias_temporada": 12,
        "regates_completados": 78,
        "dato_clave": "Ganador del Trofeo Kopa y campeon de la Eurocopa 2024 como titular indiscutible",
    },
    "robert lewandowski": {
        "equipo": "barcelona",
        "dorsal": 9,
        "posicion": "Delantero centro",
        "edad": 36,
        "nacionalidad": "Polaca",
        "partidos_temporada": 28,
        "goles_temporada": 24,
        "asistencias_temporada": 5,
        "tiros_a_puerta": 55,
        "dato_clave": "Pichichi de LaLiga con promedio de casi un gol por partido bajo las ordenes de Flick",
    },
    "pedri": {
        "equipo": "barcelona",
        "dorsal": 8,
        "posicion": "Centrocampista",
        "edad": 22,
        "nacionalidad": "Espanola",
        "partidos_temporada": 27,
        "goles_temporada": 4,
        "asistencias_temporada": 8,
        "precision_pases_porcentaje": 91.2,
        "dato_clave": "Brujula del centro del campo con mayor vision de pase progresivo de Europa",
    },
    "raphinha": {
        "equipo": "barcelona",
        "dorsal": 11,
        "posicion": "Extremo izquierdo",
        "edad": 28,
        "nacionalidad": "Brasilena",
        "partidos_temporada": 29,
        "goles_temporada": 18,
        "asistencias_temporada": 13,
        "regates_completados": 49,
        "dato_clave": "Capitan y lider ofensivo de la temporada, incluyendo un hat-trick ante el Bayern",
    },
    "dani olmo": {
        "equipo": "barcelona",
        "dorsal": 20,
        "posicion": "Centrocampista ofensivo",
        "edad": 26,
        "nacionalidad": "Espanola",
        "partidos_temporada": 18,
        "goles_temporada": 7,
        "asistencias_temporada": 4,
        "precision_pases_porcentaje": 88.5,
        "dato_clave": "Co-goleador de la Eurocopa 2024 con impacto inmediato en el ataque cule",
    },
    "gavi": {
        "equipo": "barcelona",
        "dorsal": 6,
        "posicion": "Centrocampista",
        "edad": 20,
        "nacionalidad": "Espanola",
        "partidos_temporada": 16,
        "goles_temporada": 2,
        "asistencias_temporada": 2,
        "recuperaciones": 44,
        "dato_clave": "Corazon e intensidad competitiva del equipo tras recuperarse de su lesion",
    },
    "pau cubarsi": {
        "equipo": "barcelona",
        "dorsal": 2,
        "posicion": "Defensa central",
        "edad": 18,
        "nacionalidad": "Espanola",
        "partidos_temporada": 26,
        "goles_temporada": 0,
        "asistencias_temporada": 2,
        "precision_pases_porcentaje": 93.4,
        "duelos_ganados_porcentaje": 68.0,
        "dato_clave": "Central prodigio con la mejor salida limpia de balon desde campo propio",
    },
    "jules kounde": {
        "equipo": "barcelona",
        "dorsal": 23,
        "posicion": "Lateral derecho",
        "edad": 26,
        "nacionalidad": "Francesa",
        "partidos_temporada": 28,
        "goles_temporada": 1,
        "asistencias_temporada": 5,
        "intercepciones": 38,
        "dato_clave": "El defensor con mas minutos disputados del equipo y gran solidez en 1 vs 1",
    },
    "inaki pena": {
        "equipo": "barcelona",
        "dorsal": 13,
        "posicion": "Portero",
        "edad": 25,
        "nacionalidad": "Espanola",
        "partidos_temporada": 17,
        "goles_temporada": 0,
        "asistencias_temporada": 0,
        "porterias_a_cero": 6,
        "paradas": 42,
        "dato_clave": "Portero titular durante gran parte de la temporada tras la lesion de Ter Stegen",
    },
    "marc-andre ter stegen": {
        "equipo": "barcelona",
        "dorsal": 1,
        "posicion": "Portero",
        "edad": 32,
        "nacionalidad": "Alemana",
        "partidos_temporada": 7,
        "goles_temporada": 0,
        "asistencias_temporada": 0,
        "porterias_a_cero": 2,
        "paradas": 19,
        "dato_clave": "Primer capitan del equipo, baja prolongada por lesion en el tendon rotuliano",
    },

    # --- REAL MADRID ---
    "kylian mbappe": {
        "equipo": "real_madrid",
        "dorsal": 9,
        "posicion": "Delantero centro",
        "edad": 26,
        "nacionalidad": "Francesa",
        "partidos_temporada": 29,
        "goles_temporada": 24,
        "asistencias_temporada": 6,
        "tiros_a_puerta": 62,
        "dato_clave": "Maximo goleador blanco de la temporada y estrella mundial en su primer ano",
    },
    "vinicius jr": {
        "equipo": "real_madrid",
        "dorsal": 7,
        "posicion": "Extremo izquierdo",
        "edad": 24,
        "nacionalidad": "Brasilena",
        "partidos_temporada": 27,
        "goles_temporada": 18,
        "asistencias_temporada": 10,
        "regates_completados": 82,
        "dato_clave": "Balon de Plata 2024, decisivo en finales de Champions y lider de desequilibrio",
    },
    "jude bellingham": {
        "equipo": "real_madrid",
        "dorsal": 5,
        "posicion": "Centrocampista ofensivo",
        "edad": 21,
        "nacionalidad": "Inglesa",
        "partidos_temporada": 26,
        "goles_temporada": 15,
        "asistencias_temporada": 7,
        "precision_pases_porcentaje": 89.0,
        "dato_clave": "Motor todoterreno con llegada al area y ganador de Champions y Liga en su debut",
    },
    "rodrygo": {
        "equipo": "real_madrid",
        "dorsal": 11,
        "posicion": "Extremo derecho",
        "edad": 24,
        "nacionalidad": "Brasilena",
        "partidos_temporada": 25,
        "goles_temporada": 10,
        "asistencias_temporada": 8,
        "regates_completados": 45,
        "dato_clave": "Especialista en noches de Champions con capacidad para jugar en todo el frente de ataque",
    },
    "federico valverde": {
        "equipo": "real_madrid",
        "dorsal": 8,
        "posicion": "Centrocampista",
        "edad": 26,
        "nacionalidad": "Uruguaya",
        "partidos_temporada": 30,
        "goles_temporada": 6,
        "asistencias_temporada": 5,
        "recuperaciones": 65,
        "dato_clave": "El pulmon inagotable del Madrid, heredero del dorsal 8 de Toni Kroos",
    },
    "luka modric": {
        "equipo": "real_madrid",
        "dorsal": 10,
        "posicion": "Centrocampista",
        "edad": 39,
        "nacionalidad": "Croata",
        "partidos_temporada": 28,
        "goles_temporada": 3,
        "asistencias_temporada": 6,
        "precision_pases_porcentaje": 92.8,
        "dato_clave": "Jugador mas laureado en la historia del Real Madrid con 27 titulos oficiales",
    },
    "antonio rudiger": {
        "equipo": "real_madrid",
        "dorsal": 22,
        "posicion": "Defensa central",
        "edad": 31,
        "nacionalidad": "Alemana",
        "partidos_temporada": 28,
        "goles_temporada": 2,
        "asistencias_temporada": 0,
        "duelos_ganados_porcentaje": 71.5,
        "intercepciones": 41,
        "dato_clave": "Lider indiscutible de la zaga madridista, conocido por su potencia y juego aereo",
    },
    "thibaut courtois": {
        "equipo": "real_madrid",
        "dorsal": 1,
        "posicion": "Portero",
        "edad": 32,
        "nacionalidad": "Belga",
        "partidos_temporada": 20,
        "goles_temporada": 0,
        "asistencias_temporada": 0,
        "porterias_a_cero": 8,
        "paradas": 58,
        "dato_clave": "Considerado uno de los mejores arqueros del mundo y figura en las ultimas Champions",
    },
    "arda guler": {
        "equipo": "real_madrid",
        "dorsal": 15,
        "posicion": "Centrocampista ofensivo",
        "edad": 20,
        "nacionalidad": "Turca",
        "partidos_temporada": 19,
        "goles_temporada": 5,
        "asistencias_temporada": 4,
        "regates_completados": 28,
        "dato_clave": "Joven perla turca con zurda privilegiada y excelente efectividad de tiro",
    },
    "eduardo camavinga": {
        "equipo": "real_madrid",
        "dorsal": 6,
        "posicion": "Centrocampista defensivo",
        "edad": 22,
        "nacionalidad": "Francesa",
        "partidos_temporada": 18,
        "goles_temporada": 1,
        "asistencias_temporada": 2,
        "recuperaciones": 48,
        "dato_clave": "Polivalencia absoluta capaz de rendir como pivote, interior o lateral",
    },
}

# Diccionario de alias / apodos para busqueda flexible sin importar como lo escriba el agente
PLAYER_ALIASES = {
    # Real Madrid
    "vini": "vinicius jr",
    "vini jr": "vinicius jr",
    "vinicius": "vinicius jr",
    "vinicius junior": "vinicius jr",
    "mbappe": "kylian mbappe",
    "kylian mbappe": "kylian mbappe",
    "bellingham": "jude bellingham",
    "jude": "jude bellingham",
    "fede valverde": "federico valverde",
    "valverde": "federico valverde",
    "pajarito valverde": "federico valverde",
    "modric": "luka modric",
    "rudiger": "antonio rudiger",
    "courtois": "thibaut courtois",
    "thibaut": "thibaut courtois",
    "guler": "arda guler",
    "arda": "arda guler",
    "camavinga": "eduardo camavinga",
    # Barcelona
    "yamal": "lamine yamal",
    "lamine": "lamine yamal",
    "lewandowski": "robert lewandowski",
    "lewy": "robert lewandowski",
    "pedri gonzalez": "pedri",
    "olmo": "dani olmo",
    "cubarsi": "pau cubarsi",
    "kounde": "jules kounde",
    "pena": "inaki pena",
    "ter stegen": "marc-andre ter stegen",
    "stegen": "marc-andre ter stegen",
}

HEAD_TO_HEAD = {
    "balance_historico_oficial": {
        "partidos_totales": 257,
        "victorias_real_madrid": 105,
        "victorias_barcelona": 100,
        "empates": 52,
        "goles_real_madrid": 433,
        "goles_barcelona": 419,
        "competiciones": {
            "laliga": {"madrid": 79, "barcelona": 75, "empates": 35},
            "copa_del_rey": {"madrid": 13, "barcelona": 16, "empates": 8},
            "champions_league": {"madrid": 3, "barcelona": 2, "empates": 3},
            "supercopa_espana": {"madrid": 10, "barcelona": 5, "empates": 2},
        },
    },
    "ultimos_5_clasicos": [
        {"fecha": "2024-10-26", "resultado": "Real Madrid 0-4 Barcelona", "competicion": "LaLiga (Bernabeu)"},
        {"fecha": "2024-04-21", "resultado": "Real Madrid 3-2 Barcelona", "competicion": "LaLiga (Bernabeu)"},
        {"fecha": "2024-01-14", "resultado": "Real Madrid 4-1 Barcelona", "competicion": "Supercopa de Espana"},
        {"fecha": "2023-10-28", "resultado": "Barcelona 1-2 Real Madrid", "competicion": "LaLiga (Montjuic)"},
        {"fecha": "2023-04-05", "resultado": "Barcelona 0-4 Real Madrid", "competicion": "Copa del Rey (Camp Nou)"},
    ],
    "ultimos_10_clasicos": [
        {"fecha": "2024-10-26", "resultado": "Real Madrid 0-4 Barcelona", "competicion": "LaLiga"},
        {"fecha": "2024-04-21", "resultado": "Real Madrid 3-2 Barcelona", "competicion": "LaLiga"},
        {"fecha": "2024-01-14", "resultado": "Real Madrid 4-1 Barcelona", "competicion": "Supercopa"},
        {"fecha": "2023-10-28", "resultado": "Barcelona 1-2 Real Madrid", "competicion": "LaLiga"},
        {"fecha": "2023-04-05", "resultado": "Barcelona 0-4 Real Madrid", "competicion": "Copa del Rey"},
        {"fecha": "2023-03-19", "resultado": "Barcelona 2-1 Real Madrid", "competicion": "LaLiga"},
        {"fecha": "2023-03-02", "resultado": "Real Madrid 0-1 Barcelona", "competicion": "Copa del Rey"},
        {"fecha": "2023-01-15", "resultado": "Real Madrid 1-3 Barcelona", "competicion": "Supercopa"},
        {"fecha": "2022-10-16", "resultado": "Real Madrid 3-1 Barcelona", "competicion": "LaLiga"},
        {"fecha": "2022-03-20", "resultado": "Real Madrid 0-4 Barcelona", "competicion": "LaLiga"},
    ],
    "hitos_destacados": {
        "mayores_goleadas_barcelona": [
            "Real Madrid 0-5 Barcelona (1974 - Con Johan Cruyff)",
            "Real Madrid 2-6 Barcelona (2009 - Con Guardiola y Messi)",
            "Barcelona 5-0 Real Madrid (2010 - Era Mourinho)",
            "Real Madrid 0-4 Barcelona (2024 - Con Hansi Flick)",
        ],
        "mayores_goleadas_real_madrid": [
            "Real Madrid 11-1 Barcelona (1943 - Copa)",
            "Real Madrid 5-0 Barcelona (1995 - Era Valdano)",
            "Real Madrid 4-1 Barcelona (2008 - Paseo del campeon)",
            "Barcelona 0-4 Real Madrid (2023 - Copa del Rey)",
        ],
    },
}

INJURIES_AND_SQUAD_STATUS = {
    "barcelona": {
        "equipo": "FC Barcelona",
        "lesionados": [
            {"jugador": "Marc-Andre ter Stegen", "lesion": "Rotura de tendon rotuliano", "retorno_estimado": "Finales de temporada"},
            {"jugador": "Marc Bernal", "lesion": "Rotura de ligamento cruzado anterior", "retorno_estimado": "Proxima temporada"},
            {"jugador": "Andreas Christensen", "lesion": "Tendinopatia aquilea", "retorno_estimado": "En recuperacion progresiva"},
        ],
        "disponibilidad": "Plantilla principal disponible y en gran forma fisica bajo Hansi Flick.",
    },
    "real_madrid": {
        "equipo": "Real Madrid CF",
        "lesionados": [
            {"jugador": "Dani Carvajal", "lesion": "Triple rotura de rodilla", "retorno_estimado": "Proxima temporada"},
            {"jugador": "Eder Militao", "lesion": "Rotura de ligamento cruzado anterior", "retorno_estimado": "Proxima temporada"},
            {"jugador": "David Alaba", "lesion": "Rotura de ligamento cruzado en fase final de readaptacion", "retorno_estimado": "Proximo mes"},
        ],
        "disponibilidad": "Defensa afectada por lesiones graves de cruzado; resto de plantilla disponible.",
    },
}


def resolve_player_key(name: str) -> Optional[str]:
    """Resuelve el nombre o apodo de un jugador a la clave canonica en PLAYER_STATS."""
    clean = normalize_text(name)
    if clean in PLAYER_STATS:
        return clean
    if clean in PLAYER_ALIASES:
        return PLAYER_ALIASES[clean]
    # Intento de coincidencia parcial
    for canonical in PLAYER_STATS:
        if clean in canonical or canonical in clean:
            return canonical
    for alias, canonical in PLAYER_ALIASES.items():
        if clean in alias or alias in clean:
            return canonical
    return None


def resolve_team_key(team: str) -> Optional[str]:
    """Resuelve el nombre del equipo a 'barcelona' o 'real_madrid'."""
    clean = normalize_text(team).replace(" ", "_")
    if "barca" in clean or "barcelona" in clean or "cule" in clean:
        return "barcelona"
    if "madrid" in clean or "merengue" in clean or "blanco" in clean:
        return "real_madrid"
    return None
