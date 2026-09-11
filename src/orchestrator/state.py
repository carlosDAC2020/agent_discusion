"""Construccion del estado inicial del debate.

Responsabilidad del Dev 1: logica de turnos (quien empieza es aleatorio,
luego se respeta el orden) y parametros de la sesion.
"""

import random

from src.config.settings import STYLE_DEBATE


def initial_state(question: str, max_rounds: int = 1, style: str = STYLE_DEBATE) -> dict:
    """Crea el estado inicial para el grafo de debate.

    El primer equipo en responder se elige al azar; a partir de ahi se
    respeta ese orden (turnos alternados) durante toda la sesion.
    """
    teams = ["barcelona", "real_madrid"]
    random.shuffle(teams)
    return {
        "question": question,
        "turn_order": teams,
        "turns_taken": 0,
        "max_turns": max_rounds * 2,
        "style": style,
        "messages": [],
    }
