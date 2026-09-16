"""Forma estable del debate que consumen los publishers.

Se desacopla a proposito del `DebateState`/resultado crudo de
`src/orchestrator/graph.py`: si el orquestador cambia su representacion
interna, solo hay que ajustar `debate_from_result`, no cada publisher.
"""

from dataclasses import dataclass, field

from src.agents.barcelona_agent import DISPLAY_NAME as BARCELONA_DISPLAY_NAME
from src.agents.barcelona_agent import TEAM_NAME as BARCELONA
from src.agents.real_madrid_agent import DISPLAY_NAME as REAL_MADRID_DISPLAY_NAME
from src.agents.real_madrid_agent import TEAM_NAME as REAL_MADRID

# Se lee el nombre de presentacion directamente de cada modulo de agente
# (misma fuente que usa src/cli/main.py) en vez de hardcodearlo aca: si Dev 2
# vuelve a cambiar el nombre de presentacion, no hay que tocar este archivo.
TEAM_LABELS = {
    BARCELONA: BARCELONA_DISPLAY_NAME,
    REAL_MADRID: REAL_MADRID_DISPLAY_NAME,
}


@dataclass(frozen=True)
class DebateTurn:
    team: str
    content: str
    tool_calls: list[dict] = field(default_factory=list)

    @property
    def team_label(self) -> str:
        return TEAM_LABELS.get(self.team, self.team)


@dataclass(frozen=True)
class Debate:
    question: str
    mode: str
    style: str
    turns: list[DebateTurn] = field(default_factory=list)


def debate_from_result(question: str, mode: str, style: str, result: dict) -> Debate:
    """Adapta el dict que devuelve `graph.ainvoke(...)` a `Debate`."""
    turns = [
        DebateTurn(team=m["team"], content=m["content"], tool_calls=m.get("tool_calls", []))
        for m in result["messages"]
    ]
    return Debate(question=question, mode=mode, style=style, turns=turns)
