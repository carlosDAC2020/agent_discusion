"""Tests del enrutamiento del debate (orchestrator), sin invocar LLM real.

Los agentes se mockean: solo nos interesa que el grafo alterne turnos en el
orden correcto y termine al llegar a max_turns.
"""

import asyncio
from types import SimpleNamespace

from langchain_core.messages import ToolMessage
from langgraph.graph import END, START, StateGraph

from src.config.settings import STYLE_ANSWER, STYLE_DEBATE
from src.orchestrator.graph import (
    BARCELONA,
    REAL_MADRID,
    DebateState,
    _entry_router,
    _extract_tool_calls,
    _format_context,
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
    assert state["style"] == STYLE_DEBATE


def test_format_context_in_debate_style_includes_rival_messages():
    messages = [{"team": BARCELONA, "content": "Vamos Barca"}]
    context = _format_context("¿Quien gana?", messages, STYLE_DEBATE)
    assert "Vamos Barca" in context
    assert "Debate hasta ahora" in context


def test_format_context_in_debate_style_calls_out_last_rival_message():
    messages = [
        {"team": BARCELONA, "content": "Primer punto del Barca"},
        {"team": REAL_MADRID, "content": "Respuesta del Madrid"},
    ]
    context = _format_context("¿Quien gana?", messages, STYLE_DEBATE)
    assert "Lo ULTIMO que dijo Paco" in context
    assert '"Respuesta del Madrid"' in context
    assert "refutas" in context or "refuta" in context


def test_format_context_in_answer_style_hides_rival_messages():
    messages = [{"team": BARCELONA, "content": "Vamos Barca"}]
    context = _format_context("¿Quien gana?", messages, STYLE_ANSWER)
    assert "Vamos Barca" not in context
    assert "Debate hasta ahora" not in context


def test_extract_tool_calls_pairs_ai_tool_calls_with_tool_messages():
    ai_msg = SimpleNamespace(
        tool_calls=[{"id": "call_1", "name": "get_team_stats", "args": {"team": "barcelona"}}]
    )
    tool_msg = ToolMessage(content="{'titulos_liga': 27}", name="get_team_stats", tool_call_id="call_1")
    final_msg = SimpleNamespace(content="Respuesta final", tool_calls=None)

    trace = _extract_tool_calls([ai_msg, tool_msg, final_msg])

    assert trace == [
        {
            "tool": "get_team_stats",
            "args": {"team": "barcelona"},
            "result": "{'titulos_liga': 27}",
        }
    ]


def test_make_node_attaches_tool_trace_to_message():
    ai_msg = SimpleNamespace(
        tool_calls=[{"id": "call_1", "name": "get_team_stats", "args": {"team": "barcelona"}}]
    )
    tool_msg = ToolMessage(content="datos", name="get_team_stats", tool_call_id="call_1")
    final_msg = SimpleNamespace(content="Respuesta final", tool_calls=None)

    class TracedAgent:
        async def ainvoke(self, _input):
            return {"messages": [ai_msg, tool_msg, final_msg]}

    node = _make_node(BARCELONA, TracedAgent())
    state = {
        "question": "¿Quien gana?",
        "turn_order": [BARCELONA, REAL_MADRID],
        "turns_taken": 0,
        "max_turns": 2,
        "style": STYLE_DEBATE,
        "messages": [],
    }

    update = asyncio.run(node(state))

    new_msg = update["messages"][-1]
    assert new_msg["content"] == "Respuesta final"
    assert new_msg["tool_calls"] == [
        {"tool": "get_team_stats", "args": {"team": "barcelona"}, "result": "datos"}
    ]


def _base_state():
    return {
        "question": "¿Quien gana?",
        "turn_order": [BARCELONA, REAL_MADRID],
        "turns_taken": 0,
        "max_turns": 2,
        "style": STYLE_DEBATE,
        "messages": [],
    }


def test_make_node_retries_once_on_empty_reply():
    class FlakyAgent:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, _input):
            self.calls += 1
            content = "" if self.calls == 1 else "Respuesta despues de reintentar"
            return {"messages": [SimpleNamespace(content=content, tool_calls=None)]}

    agent = FlakyAgent()
    node = _make_node(BARCELONA, agent)

    update = asyncio.run(node(_base_state()))

    assert agent.calls == 2
    assert update["messages"][-1]["content"] == "Respuesta despues de reintentar"


def test_make_node_falls_back_to_notice_when_still_empty_after_retry():
    class AlwaysEmptyAgent:
        async def ainvoke(self, _input):
            return {"messages": [SimpleNamespace(content="", tool_calls=None)]}

    node = _make_node(BARCELONA, AlwaysEmptyAgent())

    update = asyncio.run(node(_base_state()))

    assert "no genero una respuesta" in update["messages"][-1]["content"]
