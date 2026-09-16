"""Forma estable del debate que consumen los publishers.

Se desacopla a proposito del `DebateState`/resultado crudo de
`src/orchestrator/graph.py`: si el orquestador cambia su representacion
interna, solo hay que ajustar `debate_from_result`, no cada publisher.
"""

from dataclasses import dataclass, field

TEAM_LABELS = {
    "barcelona": "FC Barcelona",
    "real_madrid": "Real Madrid",
}


@dataclass(frozen=True)
class DebateTurn:
    team: str
    content: str

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
    turns = [DebateTurn(team=m["team"], content=m["content"]) for m in result["messages"]]
    return Debate(question=question, mode=mode, style=style, turns=turns)
