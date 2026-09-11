"""Grafo de orquestacion (LangGraph) del debate Barcelona vs Real Madrid.

Responsabilidad del Dev 1: logica de enrutamiento entre agentes, respeto
de turnos y condiciones de fin del debate. Los agentes en si (prompts,
personalidad) los define el Dev 2 en src/agents/*.
"""

from typing import Any, Dict, List, TypedDict

from langchain_core.messages import ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, StateGraph

from src.agents.barcelona_agent import TEAM_NAME as BARCELONA
from src.agents.barcelona_agent import get_agent as get_barcelona_agent
from src.agents.real_madrid_agent import TEAM_NAME as REAL_MADRID
from src.agents.real_madrid_agent import get_agent as get_real_madrid_agent
from src.config.settings import MCP_SERVER_PARAMS, MODE_MCP, STYLE_ANSWER, STYLE_DEBATE


class DebateState(TypedDict):
    question: str
    turn_order: List[str]
    turns_taken: int
    max_turns: int
    style: str
    messages: List[Dict[str, Any]]


def _extract_text(content) -> str:
    """Normaliza el content de un AIMessage a texto plano.

    Algunos proveedores (p.ej. Gemini) devuelven una lista de bloques
    estructurados (`[{"type": "text", "text": "..."}, ...]`) en vez de un
    string simple; el resto del pipeline (CLI, export) espera texto plano.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def _extract_tool_calls(messages: list) -> List[Dict[str, Any]]:
    """Reconstruye la traza de llamadas a tools (nombre, args, resultado) de un
    turno de agente, cruzando los `tool_calls` de los AIMessage con los
    ToolMessage de respuesta correspondientes (misma `tool_call_id`).
    """
    pending: Dict[str, Dict[str, Any]] = {}
    calls: List[Dict[str, Any]] = []
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            pending[tc["id"]] = {"tool": tc["name"], "args": tc.get("args", {})}
        if isinstance(msg, ToolMessage):
            entry = pending.pop(msg.tool_call_id, {"tool": msg.name, "args": {}})
            entry["result"] = _extract_text(msg.content)
            calls.append(entry)
    return calls


def _format_context(question: str, messages: List[Dict[str, Any]], style: str) -> str:
    if style == STYLE_ANSWER or not messages:
        return f"Pregunta del usuario: {question}"

    lines = [f"Pregunta del usuario: {question}", "\nDebate hasta ahora:"]
    for m in messages:
        equipo = "FC Barcelona" if m["team"] == BARCELONA else "Real Madrid"
        lines.append(f"- {equipo}: {m['content']}")
    lines.append("\nResponde ahora, considerando lo dicho por el rival si corresponde.")
    return "\n".join(lines)


def _make_node(team_key: str, agent):
    async def node(state: DebateState):
        context = _format_context(state["question"], state["messages"], state["style"])
        result = await agent.ainvoke({"messages": [{"role": "user", "content": context}]})
        reply = _extract_text(result["messages"][-1].content)
        tool_calls = _extract_tool_calls(result["messages"])
        return {
            "messages": state["messages"]
            + [{"team": team_key, "content": reply, "tool_calls": tool_calls}],
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


async def build_debate_graph(mode: str = MODE_MCP, style: str = STYLE_DEBATE):
    """Conecta al servidor MCP de herramientas (si el modo lo requiere), arma
    los agentes y compila el grafo.
    """
    if mode == MODE_MCP:
        mcp_client = MultiServerMCPClient({"football": MCP_SERVER_PARAMS})
        tools = await mcp_client.get_tools()
    else:
        tools = []

    barcelona_agent = get_barcelona_agent(tools, mode=mode, style=style)
    real_madrid_agent = get_real_madrid_agent(tools, mode=mode, style=style)

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
