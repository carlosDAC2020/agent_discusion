"""Cliente CLI: recibe preguntas de futbol y muestra el debate entre agentes.

Responsabilidad del Dev 1: UX de la CLI y orquestacion end-to-end.
"""

import asyncio
import enum
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

import questionary
import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel

from src.agents.barcelona_agent import DISPLAY_NAME as BARCELONA_NAME
from src.agents.barcelona_agent import TEAM_NAME as BARCELONA
from src.agents.real_madrid_agent import DISPLAY_NAME as REAL_MADRID_NAME
from src.agents.real_madrid_agent import TEAM_NAME as REAL_MADRID
from src.config.settings import MODE_KNOWLEDGE, MODE_MCP, STYLE_ANSWER, STYLE_DEBATE
from src.orchestrator.graph import _extract_text, build_debate_graph
from src.orchestrator.state import initial_state
from src.social.base import DebatePublisher, PublishError
from src.social.models import debate_from_result
from src.social.registry import available_platforms, get_publisher

if sys.platform == "win32":
    # La consola de Windows suele usar un codepage (ej. 850) que rompe los
    # acentos/enies al imprimir UTF-8. Forzamos UTF-8 para que se vean bien.
    os.system("chcp 65001 > NUL")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(add_completion=False, help="Debate de agentes Barcelona vs Real Madrid.")
console = Console()

TEAM_LABELS = {
    BARCELONA: BARCELONA_NAME,
    REAL_MADRID: REAL_MADRID_NAME,
}
TEAM_STYLES = {
    BARCELONA: "blue",
    REAL_MADRID: "white",
}

# Frases en lenguaje natural para lo que esta haciendo el agente al llamar
# cada tool MCP, para no exponerle a alguien no tecnico un nombre de funcion
# como "get_trophies_comparison()". Si aparece una tool nueva que no esta en
# este mapa, usamos un mensaje generico como fallback (ver _tool_trace_line).
TOOL_FRIENDLY_MESSAGES = {
    "get_team_stats": lambda args: "consultando las estadisticas del equipo...",
    "get_player_stats": lambda args: f"buscando los numeros de {args.get('player_name', 'el jugador')}...",
    "compare_players": lambda args: (
        f"comparando a {args.get('player_a', '?')} contra {args.get('player_b', '?')}..."
    ),
    "get_head_to_head": lambda args: "repasando los ultimos clasicos...",
    "get_head_to_head_summary": lambda args: "sacando el resumen historico del clasico...",
    "get_trophies_comparison": lambda args: "contando los titulos de cada equipo...",
    "get_injuries_or_squad_status": lambda args: "revisando la enfermeria del equipo...",
    "search_web": lambda args: "buscando informacion actualizada en internet...",
}


def _tool_trace_line(tool_name: str, args: dict) -> str:
    builder = TOOL_FRIENDLY_MESSAGES.get(tool_name)
    message = builder(args) if builder else "consultando datos..."
    return f"[dim]↳ {message}[/dim]"

EXPORT_HELP = "Exporta el debate a un archivo (.txt o .json). Se agrega al final si ya existe."
PUBLISH_HELP = f"Publica el debate en una red social al terminar. Opciones: {', '.join(available_platforms())}."


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


def _resolve_publisher(publish_to: Optional[str]) -> Optional[DebatePublisher]:
    """Valida plataforma y credenciales ANTES de correr el debate (para no
    gastar llamadas al modelo si el usuario tipeo mal el nombre, o si le
    faltan credenciales de esa red social)."""
    if publish_to is None:
        return None
    try:
        publisher = get_publisher(publish_to)
    except ValueError as exc:
        console.print(Panel(str(exc), title="Plataforma invalida", border_style="red"))
        raise typer.Exit(code=1) from exc

    try:
        publisher.ensure_ready()
    except PublishError as exc:
        console.print(
            Panel(str(exc), title=f"No se puede publicar en {publisher.name}", border_style="red")
        )
        raise typer.Exit(code=1) from exc

    return publisher


def _publish_debate(publisher: DebatePublisher, question: str, mode: str, style: str, result: dict) -> None:
    debate = debate_from_result(question, mode, style, result)
    try:
        publish_result = publisher.publish(debate)
    except PublishError as exc:
        console.print(
            Panel(str(exc), title=f"No se pudo publicar en {publisher.name}", border_style="red")
        )
        return
    except NotImplementedError as exc:
        console.print(Panel(str(exc), title="Plataforma no implementada", border_style="yellow"))
        return
    console.print(
        f"[dim]Publicado en {publish_result.platform}: {publish_result.posted} mensajes.[/dim]"
    )


async def _run_debate(
    question: str,
    rounds: int,
    mode: str,
    style: str,
    export: Optional[Path] = None,
    publisher: Optional[DebatePublisher] = None,
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

    # Streaming en vivo: mostramos cada turno token a token (y las tools que
    # el agente va llamando) a medida que se generan, en vez de esperar a
    # que termine todo el debate para recien mostrarlo.
    current_team: Optional[str] = None
    buffer = ""
    tool_lines: List[str] = []
    live: Optional[Live] = None
    final_result: Optional[dict] = None

    def _panel() -> Panel:
        body = "\n".join(tool_lines)
        if body and buffer:
            body += "\n\n" + buffer
        elif buffer:
            body = buffer
        elif not body:
            body = f"[dim]{TEAM_LABELS[current_team]} esta pensando...[/dim]"
        return Panel(body, title=TEAM_LABELS[current_team], border_style=TEAM_STYLES.get(current_team, "cyan"))

    try:
        async for event in graph.astream_events(state, version="v2"):
            kind = event["event"]
            name = event.get("name")

            if kind == "on_chain_start" and name in TEAM_LABELS:
                if live is not None:
                    # Defensivo: si el turno anterior no cerro su Live antes
                    # de que arranque uno nuevo (p.ej. algun evento interno
                    # inesperado), lo cerramos aca para no terminar con dos
                    # paneles dibujados para el mismo turno.
                    live.stop()
                current_team = name
                buffer = ""
                tool_lines = []
                live = Live(_panel(), console=console, refresh_per_second=12)
                live.start()

            elif kind == "on_chat_model_stream" and live is not None:
                text = _extract_text(event["data"]["chunk"].content)
                if text:
                    buffer += text
                    live.update(_panel())

            elif kind == "on_tool_start" and live is not None:
                tool_lines.append(_tool_trace_line(name, event["data"].get("input") or {}))
                live.update(_panel())

            elif kind == "on_chain_end" and name in TEAM_LABELS:
                output = event["data"].get("output")
                if output:
                    final_result = output
                    if not buffer.strip():
                        msgs = output.get("messages") or []
                        if msgs:
                            buffer = msgs[-1].get("content", "")
                if live is not None:
                    live.update(_panel())
                    live.stop()
                    live = None
                current_team = None
    except Exception as exc:
        if live is not None:
            live.stop()
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

    # Los eventos de on_chain_end solo traen lo que el nodo retorna
    # (messages, turns_taken), no el estado completo (a diferencia de
    # graph.ainvoke): completamos con los campos que vienen del estado
    # inicial y no cambian durante la ejecucion. Tanto exportar como
    # publicar necesitan esta misma forma completa.
    final_state = {**state, **final_result, "mode": mode, "style": style} if final_result is not None else None

    if export is not None and final_state is not None:
        _export_debate(question, final_state, export)

    if publisher is not None and final_state is not None:
        # `_publish_debate` hace llamadas de red sincronas (requests/praw).
        # Se corre en un thread aparte para no bloquear el loop de asyncio
        # que ya esta corriendo aca (evita el warning de PRAW sobre uso en
        # entornos asincronos, y no frena el event loop durante la llamada).
        await asyncio.to_thread(_publish_debate, publisher, question, mode, style, final_state)


@app.command()
def chat(
    rounds: Optional[int] = typer.Option(None, help=ROUNDS_HELP),
    export: Optional[Path] = typer.Option(None, "--export", help=EXPORT_HELP),
    mode: Optional[ModeOption] = typer.Option(None, "--mode", help=MODE_HELP),
    style: Optional[StyleOption] = typer.Option(None, "--style", help=STYLE_HELP),
    publish_to: Optional[str] = typer.Option(None, "--publish-to", help=PUBLISH_HELP),
) -> None:
    """Chat interactivo: escribe preguntas de futbol, 'salir' para terminar."""
    console.print("[bold]Debate Barcelona vs Real Madrid[/bold] - escribe 'salir' para terminar.\n")
    publisher = _resolve_publisher(publish_to)
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
        asyncio.run(_run_debate(question, rounds_value, mode_value, style_value, export, publisher))
        console.print()


@app.command()
def ask(
    question: str,
    rounds: Optional[int] = typer.Option(None, help=ROUNDS_HELP),
    export: Optional[Path] = typer.Option(None, "--export", help=EXPORT_HELP),
    mode: ModeOption = typer.Option(ModeOption.mcp, "--mode", help=MODE_HELP),
    style: StyleOption = typer.Option(StyleOption.debate, "--style", help=STYLE_HELP),
    publish_to: Optional[str] = typer.Option(None, "--publish-to", help=PUBLISH_HELP),
) -> None:
    """Hace una sola pregunta y termina (util para scripts/pruebas)."""
    publisher = _resolve_publisher(publish_to)
    rounds_value = _resolve_rounds(rounds, style.value)
    asyncio.run(_run_debate(question, rounds_value, mode.value, style.value, export, publisher))


@app.command()
def listen(
    mode: ModeOption = typer.Option(ModeOption.mcp, "--mode", help=MODE_HELP),
    style: StyleOption = typer.Option(StyleOption.debate, "--style", help=STYLE_HELP),
    rounds: Optional[int] = typer.Option(None, help=ROUNDS_HELP),
) -> None:
    """Escucha el grupo de Telegram: cualquiera escribe '/debate <pregunta>' y dispara un debate."""
    from src.social.telegram_listener import TRIGGER_PREFIX, TelegramListener

    publisher = _resolve_publisher("telegram")
    listener = TelegramListener()
    rounds_value = _resolve_rounds(rounds, style.value)

    console.print(
        f"[dim]Escuchando \"{TRIGGER_PREFIX} <pregunta>\" en el chat de Telegram "
        f"(modo={mode.value}, estilo={style.value}). Ctrl+C para salir.[/dim]\n"
    )

    while True:
        try:
            questions = listener.poll_once()
        except PublishError as exc:
            console.print(Panel(str(exc), title="Error escuchando Telegram", border_style="red"))
            time.sleep(5)
            continue
        except KeyboardInterrupt:
            console.print("\n[dim]Hasta luego.[/dim]")
            break

        for question in questions:
            console.print(f"[bold]Pregunta recibida por Telegram:[/bold] {question}\n")
            asyncio.run(_run_debate(question, rounds_value, mode.value, style.value, None, publisher))
            console.print()


if __name__ == "__main__":
    app()
