"""Tests del enrutamiento del debate (orchestrator), sin invocar LLM real.

Los agentes se mockean: solo nos interesa que el grafo alterne turnos en el
orden correcto y termine al llegar a max_turns.
"""

import asyncio
from types import SimpleNamespace

from langgraph.graph import END, START, StateGraph

from src.orchestrator.graph import (
    BARCELONA,
    REAL_MADRID,
    DebateState,
    _entry_router,
    _make_node,
    _next_router,
)
from src.orchestrator.state import initial_state


class FakeAgent:
    """Reemplaza a un agente ReAct real: siempre responde lo mismo, sin LLM."""

    def __init__(self, reply: str):
        self.reply = reply

    async def ainvoke(self, _input):
        return {"messages": [SimpleNamespace(content=self.reply)]}


def _build_fake_graph():
    graph = StateGraph(DebateState)
    graph.add_node(BARCELONA, _make_node(BARCELONA, FakeAgent("Vamos Barca")))
    graph.add_node(REAL_MADRID, _make_node(REAL_MADRID, FakeAgent("Hala Madrid")))

    graph.add_conditional_edges(
        START, _entry_router, {BARCELONA: BARCELONA, REAL_MADRID: REAL_MADRID}
    )
    graph.add_conditional_edges(
        BARCELONA, _next_router, {BARCELONA: BARCELONA, REAL_MADRID: REAL_MADRID, END: END}
    )
    graph.add_conditional_edges(
        REAL_MADRID, _next_router, {BARCELONA: BARCELONA, REAL_MADRID: REAL_MADRID, END: END}
    )
    return graph.compile()


def test_entry_router_respects_turn_order():
    state = {"turn_order": [REAL_MADRID, BARCELONA]}
    assert _entry_router(state) == REAL_MADRID


def test_next_router_alternates_to_the_other_team():
    state = {
        "turn_order": [BARCELONA, REAL_MADRID],
        "turns_taken": 1,
        "max_turns": 4,
        "messages": [{"team": BARCELONA, "content": "..."}],
    }
    assert _next_router(state) == REAL_MADRID


def test_next_router_ends_when_max_turns_reached():
    state = {
        "turn_order": [BARCELONA, REAL_MADRID],
        "turns_taken": 4,
        "max_turns": 4,
        "messages": [{"team": REAL_MADRID, "content": "..."}],
    }
    assert _next_router(state) == END


def test_debate_alternates_strictly_and_stops_at_max_turns():
    graph = _build_fake_graph()
    state = initial_state("¿Quien gana el clasico?", max_rounds=2)

    result = asyncio.run(graph.ainvoke(state))

    assert result["turns_taken"] == state["max_turns"] == 4
    assert len(result["messages"]) == 4

    spoken_order = [m["team"] for m in result["messages"]]
    expected_order = state["turn_order"] * 2
    assert spoken_order == expected_order


def test_initial_state_turn_order_is_a_permutation_of_both_teams():
    state = initial_state("pregunta", max_rounds=3)
    assert sorted(state["turn_order"]) == sorted([BARCELONA, REAL_MADRID])
    assert state["max_turns"] == 6
    assert state["turns_taken"] == 0
    assert state["messages"] == []
