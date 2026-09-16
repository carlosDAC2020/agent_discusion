"""Fabrica base para agentes reactivos (patron ReAct) usando LangGraph.

Responsabilidad del Dev 2: ajustar prompts/personalidad de cada agente y
la logica de como usan las herramientas MCP. Este modulo solo provee el
armado generico del agente reactivo, comun a ambos equipos.
"""

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from src.config.settings import (
    MODE_KNOWLEDGE,
    MODE_MCP,
    MODEL_PROVIDER,
    MODEL_TEMPERATURE,
    STYLE_ANSWER,
    STYLE_DEBATE,
)

_MODE_INSTRUCTIONS = {
    MODE_KNOWLEDGE: (
        "\n\nModo de conocimiento: respondes SOLO con tu conocimiento previo, "
        "sin usar ninguna herramienta externa (no tenes tools disponibles ahora). "
        "Si no estas seguro de una cifra exacta, aclaralo en vez de inventarla con "
        "falsa precision."
    ),
    MODE_MCP: (
        "\n\nModo herramientas (MCP): antes de argumentar, usa las herramientas "
        "disponibles (estadisticas internas y, si la pregunta requiere informacion "
        "muy reciente que no tenes en tus datos internos, la tool search_web) para "
        "fundamentar tu respuesta con datos verificables."
    ),
}

_STYLE_INSTRUCTIONS = {
    STYLE_ANSWER: (
        "\n\nModo respuesta directa: contesta unicamente la pregunta del usuario. "
        "No hagas referencia a lo que dijo el otro equipo ni intentes rebatirlo; "
        "no estan debatiendo entre ustedes en este modo."
    ),
    STYLE_DEBATE: (
        "\n\nModo discusion: estas debatiendo en vivo con el otro equipo, que va a "
        "leer tu respuesta y a replicarte igual que vos ves la suya. Cada respuesta "
        "tiene que sentirse como una intervencion de debate real: si el rival ya "
        "hablo, reconoce brevemente su punto y rebatilo con un argumento propio "
        "dificil de discutir; cerra siempre defendiendo tu postura, sabiendo que "
        "el otro va a intentar rebatirte a vos despues."
    ),
}


def build_reactive_agent(
    system_prompt: str,
    tools: list,
    mode: str = MODE_MCP,
    style: str = STYLE_DEBATE,
):
    """Crea un agente reactivo (ReAct: razona -> usa herramienta -> responde).

    Args:
        system_prompt: personalidad e instrucciones del agente (sesgo de equipo).
        tools: herramientas MCP ya cargadas (ver src/orchestrator/graph.py). Se
            ignoran si `mode` es MODE_KNOWLEDGE (el llamador ya deberia pasar
            una lista vacia en ese caso).
        mode: MODE_KNOWLEDGE (solo conocimiento propio) o MODE_MCP (con tools).
        style: STYLE_ANSWER (responde solo) o STYLE_DEBATE (debate consciente).
    """
    full_prompt = system_prompt + _MODE_INSTRUCTIONS[mode] + _STYLE_INSTRUCTIONS[style]
    llm = init_chat_model(MODEL_PROVIDER, temperature=MODEL_TEMPERATURE)
    return create_react_agent(model=llm, tools=tools, prompt=full_prompt)
