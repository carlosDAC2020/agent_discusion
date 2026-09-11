"""Grafo de orquestacion (LangGraph) del debate Barcelona vs Real Madrid.

Responsabilidad del Dev 1: logica de enrutamiento entre agentes, respeto
de turnos y condiciones de fin del debate. Los agentes en si (prompts,
personalidad) los define el Dev 2 en src/agents/*.
"""

from typing import Dict, List, TypedDict

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, StateGraph

from src.agents.barcelona_agent import TEAM_NAME as BARCELONA
from src.agents.barcelona_agent import get_agent as get_barcelona_agent
from src.agents.real_madrid_agent import TEAM_NAME as REAL_MADRID
from src.agents.real_madrid_agent import get_agent as get_real_madrid_agent
from src.config.settings import MCP_SERVER_PARAMS


class DebateState(TypedDict):
    question: str
    turn_order: List[str]
    turns_taken: int
    max_turns: int
    messages: List[Dict[str, str]]


def _format_context(question: str, messages: List[Dict[str, str]]) -> str:
    lines = [f"Pregunta del usuario: {question}"]
    if messages:
        lines.append("\nDebate hasta ahora:")
        for m in messages:
            equipo = "FC Barcelona" if m["team"] == BARCELONA else "Real Madrid"
            lines.append(f"- {equipo}: {m['content']}")
        lines.append("\nResponde ahora, considerando lo dicho por el rival si corresponde.")
    return "\n".join(lines)


def _make_node(team_key: str, agent):
    def node(state: DebateState):
        context = _format_context(state["question"], state["messages"])
        result = agent.invoke({"messages": [{"role": "user", "content": context}]})
        reply = result["messages"][-1].content
        return {
            "messages": state["messages"] + [{"team": team_key, "content": reply}],
            "turns_taken": state["turns_taken"] + 1,
        }

    return node


def _entry_router(state: DebateState) -> str:
    return state["turn_order"][0]


def _next_router(state: DebateState) -> str:
    if state["turns_taken"] >= state["max_turns"]:
        return END
    last_team = state["messages"][-1]["team"]
    other = [t for t in state["turn_order"] if t != last_team][0]
    return other


async def build_debate_graph():
    """Conecta al servidor MCP de herramientas, arma los agentes y compila el grafo."""
    mcp_client = MultiServerMCPClient({"football": MCP_SERVER_PARAMS})
    tools = await mcp_client.get_tools()

    barcelona_agent = get_barcelona_agent(tools)
    real_madrid_agent = get_real_madrid_agent(tools)

    graph = StateGraph(DebateState)
    graph.add_node(BARCELONA, _make_node(BARCELONA, barcelona_agent))
    graph.add_node(REAL_MADRID, _make_node(REAL_MADRID, real_madrid_agent))

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
