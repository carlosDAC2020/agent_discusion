"""Fabrica base para agentes reactivos (patron ReAct) usando LangGraph.

Responsabilidad del Dev 2: ajustar prompts/personalidad de cada agente y
la logica de como usan las herramientas MCP. Este modulo solo provee el
armado generico del agente reactivo, comun a ambos equipos.
"""

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from src.config.settings import MODEL_PROVIDER


def build_reactive_agent(system_prompt: str, tools: list):
    """Crea un agente reactivo (ReAct: razona -> usa herramienta -> responde).

    Args:
        system_prompt: personalidad e instrucciones del agente (sesgo de equipo).
        tools: herramientas MCP ya cargadas (ver src/orchestrator/graph.py).
    """
    llm = init_chat_model(MODEL_PROVIDER)
    return create_react_agent(model=llm, tools=tools, prompt=system_prompt)
