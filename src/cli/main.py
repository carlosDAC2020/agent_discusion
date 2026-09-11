"""Cliente CLI: recibe preguntas de futbol y muestra el debate entre agentes.

Responsabilidad del Dev 1: UX de la CLI y orquestacion end-to-end.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

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
                "turn_order": result.get("turn_order"),
                "messages": result["messages"],
            }
        )
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(f"Pregunta: {question}\n")
            for msg in result["messages"]:
                equipo = TEAM_LABELS.get(msg["team"], msg["team"])
                f.write(f"[{equipo}] {msg['content']}\n")
            f.write("\n" + "-" * 40 + "\n\n")

    console.print(f"[dim]Debate exportado a {path}[/dim]")


async def _run_debate(question: str, rounds: int, export: Optional[Path] = None) -> None:
    try:
        graph = await build_debate_graph()
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

    state = initial_state(question, max_rounds=rounds)
    orden = " -> ".join(TEAM_LABELS[t] for t in state["turn_order"])
    console.print(f"[dim]Orden de turnos (elegido al azar): {orden}[/dim]\n")

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
        console.print(
            Panel(msg["content"], title=TEAM_LABELS.get(team, team), border_style=TEAM_STYLES.get(team, "cyan"))
        )

    if export is not None:
        _export_debate(question, result, export)


@app.command()
def chat(
    rounds: int = typer.Option(1, help="Rondas de intervencion por cada equipo."),
    export: Optional[Path] = typer.Option(None, "--export", help=EXPORT_HELP),
) -> None:
    """Chat interactivo: escribe preguntas de futbol, 'salir' para terminar."""
    console.print("[bold]Debate Barcelona vs Real Madrid[/bold] - escribe 'salir' para terminar.\n")
    while True:
        try:
            question = typer.prompt("Tu pregunta")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Hasta luego.[/dim]")
            break
        if question.strip().lower() in {"salir", "exit", "quit"}:
            break
        asyncio.run(_run_debate(question, rounds, export))
        console.print()


@app.command()
def ask(
    question: str,
    rounds: int = typer.Option(1, help="Rondas de intervencion por cada equipo."),
    export: Optional[Path] = typer.Option(None, "--export", help=EXPORT_HELP),
) -> None:
    """Hace una sola pregunta y termina (util para scripts/pruebas)."""
    asyncio.run(_run_debate(question, rounds, export))


if __name__ == "__main__":
    app()
