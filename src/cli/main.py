"""Cliente CLI: recibe preguntas de futbol y muestra el debate entre agentes.

Responsabilidad del Dev 1: UX de la CLI y orquestacion end-to-end.
"""

import asyncio
import enum
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import questionary
import typer
from rich.console import Console
from rich.panel import Panel

from src.config.settings import MODE_KNOWLEDGE, MODE_MCP, STYLE_ANSWER, STYLE_DEBATE
from src.orchestrator.graph import build_debate_graph
from src.orchestrator.state import initial_state

if sys.platform == "win32":
    # La consola de Windows suele usar un codepage (ej. 850) que rompe los
    # acentos/enies al imprimir UTF-8. Forzamos UTF-8 para que se vean bien.
    os.system("chcp 65001 > NUL")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(add_completion=False, help="Debate de agentes Barcelona vs Real Madrid.")
console = Console()

TEAM_LABELS = {
    "barcelona": "FC Barcelona",
    "real_madrid": "Real Madrid",
}
TEAM_STYLES = {
    "barcelona": "blue",
    "real_madrid": "white",
}

EXPORT_HELP = "Exporta el debate a un archivo (.txt o .json). Se agrega al final si ya existe."


class ModeOption(str, enum.Enum):
    """Con que fundamenta el agente su respuesta."""

    knowledge = MODE_KNOWLEDGE
    mcp = MODE_MCP


class StyleOption(str, enum.Enum):
    """Como interactuan los dos agentes entre si."""

    answer = STYLE_ANSWER
    debate = STYLE_DEBATE


MODE_HELP = "Con que responden los agentes: 'knowledge' (solo su conocimiento) o 'mcp' (usan tools: stats + busqueda web)."
STYLE_HELP = "Como interactuan: 'answer' (responden la pregunta solos) o 'debate' (se ven y se rebaten entre si)."
ROUNDS_HELP = (
    "Rondas de intervencion por cada equipo. Si no se especifica: 2 (4 turnos) "
    "en estilo debate, 1 (2 turnos) en estilo answer."
)

MODE_CHOICES = [
    (MODE_MCP, "Con herramientas MCP (stats internas + busqueda web si hace falta)"),
    (MODE_KNOWLEDGE, "Solo con su conocimiento propio (sin tools)"),
]
STYLE_CHOICES = [
    (STYLE_DEBATE, "Discusion: se ven entre si, se rebaten y defienden su postura"),
    (STYLE_ANSWER, "Respuesta directa: cada uno contesta la pregunta sin ver al rival"),
]
DEFAULT_ROUNDS_BY_STYLE = {STYLE_DEBATE: 2, STYLE_ANSWER: 1}


def _prompt_choice(label: str, choices: List[tuple], default: str) -> str:
    """Menu de seleccion directa (flechas + Enter) via questionary.

    Si no hay una terminal real (stdin no es tty) o el menu falla por
    cualquier motivo, usamos el default en silencio en vez de romper la CLI.
    """
    if not sys.stdin.isatty():
        return default
    qchoices = [questionary.Choice(title=desc, value=value) for value, desc in choices]
    default_choice = next((c for c in qchoices if c.value == default), qchoices[0])
    try:
        answer = questionary.select(label, choices=qchoices, default=default_choice).ask()
    except Exception:
        return default
    return answer if answer is not None else default


def _resolve_config(mode: Optional[ModeOption], style: Optional[StyleOption], interactive: bool):
    """Devuelve (mode, style) como strings. Si faltan y `interactive` es True,
    los pregunta con un menu de seleccion directa; si no, usa los defaults.
    """
    if mode is not None:
        mode_value = mode.value
    elif interactive:
        mode_value = _prompt_choice("¿Como quieres que respondan los agentes?", MODE_CHOICES, MODE_MCP)
    else:
        mode_value = MODE_MCP

    if style is not None:
        style_value = style.value
    elif interactive:
        style_value = _prompt_choice("¿Modo de interaccion entre los agentes?", STYLE_CHOICES, STYLE_DEBATE)
    else:
        style_value = STYLE_DEBATE

    return mode_value, style_value


def _resolve_rounds(rounds: Optional[int], style: str) -> int:
    return rounds if rounds is not None else DEFAULT_ROUNDS_BY_STYLE.get(style, 1)


def _print_tool_trace(team: str, tool_calls: List[dict]) -> None:
    equipo = TEAM_LABELS.get(team, team)
    for call in tool_calls:
        args_str = ", ".join(f"{k}={v!r}" for k, v in call.get("args", {}).items())
        console.print(f"[dim]  ↳ {equipo} llamó a [italic]{call['tool']}({args_str})[/italic][/dim]")


def _export_debate(question: str, result: dict, path: Path) -> None:
    """Guarda el debate en disco, en texto plano o JSON segun la extension."""
    if path.suffix.lower() == ".json":
        entries = []
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                entries = existing if isinstance(existing, list) else [existing]
            except (json.JSONDecodeError, OSError):
                entries = []
        entries.append(
            {
                "question": question,
                "mode": result.get("mode"),
                "style": result.get("style"),
                "turn_order": result.get("turn_order"),
                "messages": result["messages"],
            }
        )
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(f"Pregunta: {question} (modo={result.get('mode')}, estilo={result.get('style')})\n")
            for msg in result["messages"]:
                equipo = TEAM_LABELS.get(msg["team"], msg["team"])
                for call in msg.get("tool_calls", []):
                    args_str = ", ".join(f"{k}={v!r}" for k, v in call.get("args", {}).items())
                    f.write(f"  [tool] {equipo} -> {call['tool']}({args_str})\n")
                f.write(f"[{equipo}] {msg['content']}\n")
            f.write("\n" + "-" * 40 + "\n\n")

    console.print(f"[dim]Debate exportado a {path}[/dim]")


async def _run_debate(
    question: str,
    rounds: int,
    mode: str,
    style: str,
    export: Optional[Path] = None,
) -> None:
    try:
        graph = await build_debate_graph(mode=mode, style=style)
    except Exception as exc:
        console.print(
            Panel(
                "No se pudo preparar el debate: puede ser que el servidor MCP "
                "de herramientas no haya arrancado, o que el modelo (MODEL_PROVIDER "
                "y su API key en .env) no este bien configurado.\n\n"
                "Verifica que las dependencias esten instaladas "
                "(pip install -r requirements.txt), que MCP_SERVER_COMMAND / "
                "MCP_SERVER_ARGS sean correctos, y que la API key del proveedor "
                "elegido este presente en tu .env.\n\n"
                f"Detalle: {exc}",
                title="Error inicializando el debate",
                border_style="red",
            )
        )
        return

    state = initial_state(question, max_rounds=rounds, style=style)
    orden = " -> ".join(TEAM_LABELS[t] for t in state["turn_order"])
    console.print(f"[dim]Orden de turnos (elegido al azar): {orden} | modo={mode} | estilo={style}[/dim]\n")

    try:
        result = await graph.ainvoke(state)
    except Exception as exc:
        console.print(
            Panel(
                "Ocurrio un error ejecutando el debate. Verifica tu API key "
                "del proveedor de modelo (MODEL_PROVIDER y la key correspondiente "
                "en tu .env).\n\n"
                f"Detalle: {exc}",
                title="Error en el debate",
                border_style="red",
            )
        )
        return

    for msg in result["messages"]:
        team = msg["team"]
        _print_tool_trace(team, msg.get("tool_calls", []))
        console.print(
            Panel(msg["content"], title=TEAM_LABELS.get(team, team), border_style=TEAM_STYLES.get(team, "cyan"))
        )

    if export is not None:
        result["mode"] = mode
        result["style"] = style
        _export_debate(question, result, export)


@app.command()
def chat(
    rounds: Optional[int] = typer.Option(None, help=ROUNDS_HELP),
    export: Optional[Path] = typer.Option(None, "--export", help=EXPORT_HELP),
    mode: Optional[ModeOption] = typer.Option(None, "--mode", help=MODE_HELP),
    style: Optional[StyleOption] = typer.Option(None, "--style", help=STYLE_HELP),
) -> None:
    """Chat interactivo: escribe preguntas de futbol, 'salir' para terminar."""
    console.print("[bold]Debate Barcelona vs Real Madrid[/bold] - escribe 'salir' para terminar.\n")
    mode_value, style_value = _resolve_config(mode, style, interactive=True)
    rounds_value = _resolve_rounds(rounds, style_value)
    turnos = rounds_value * 2
    console.print(
        f"\n[dim]Configuracion: modo={mode_value} | estilo={style_value} | "
        f"{rounds_value} rondas ({turnos} turnos, {rounds_value} respuestas c/u)[/dim]\n"
    )

    while True:
        try:
            question = typer.prompt("Tu pregunta")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Hasta luego.[/dim]")
            break
        if question.strip().lower() in {"salir", "exit", "quit"}:
            break
        asyncio.run(_run_debate(question, rounds_value, mode_value, style_value, export))
        console.print()


@app.command()
def ask(
    question: str,
    rounds: Optional[int] = typer.Option(None, help=ROUNDS_HELP),
    export: Optional[Path] = typer.Option(None, "--export", help=EXPORT_HELP),
    mode: ModeOption = typer.Option(ModeOption.mcp, "--mode", help=MODE_HELP),
    style: StyleOption = typer.Option(StyleOption.debate, "--style", help=STYLE_HELP),
) -> None:
    """Hace una sola pregunta y termina (util para scripts/pruebas)."""
    rounds_value = _resolve_rounds(rounds, style.value)
    asyncio.run(_run_debate(question, rounds_value, mode.value, style.value, export))


if __name__ == "__main__":
    app()
