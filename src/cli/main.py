"""Cliente CLI: recibe preguntas de futbol y muestra el debate entre agentes.

Responsabilidad del Dev 1: UX de la CLI y orquestacion end-to-end.
"""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel

from src.orchestrator.graph import build_debate_graph
from src.orchestrator.state import initial_state

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


async def _run_debate(question: str, rounds: int) -> None:
    graph = await build_debate_graph()
    state = initial_state(question, max_rounds=rounds)
    orden = " -> ".join(TEAM_LABELS[t] for t in state["turn_order"])
    console.print(f"[dim]Orden de turnos (elegido al azar): {orden}[/dim]\n")

    result = await graph.ainvoke(state)
    for msg in result["messages"]:
        team = msg["team"]
        console.print(
            Panel(msg["content"], title=TEAM_LABELS.get(team, team), border_style=TEAM_STYLES.get(team, "cyan"))
        )


@app.command()
def chat(rounds: int = typer.Option(1, help="Rondas de intervencion por cada equipo.")) -> None:
    """Chat interactivo: escribe preguntas de futbol, 'salir' para terminar."""
    console.print("[bold]Debate Barcelona vs Real Madrid[/bold] - escribe 'salir' para terminar.\n")
    while True:
        question = typer.prompt("Tu pregunta")
        if question.strip().lower() in {"salir", "exit", "quit"}:
            break
        asyncio.run(_run_debate(question, rounds))
        console.print()


@app.command()
def ask(
    question: str,
    rounds: int = typer.Option(1, help="Rondas de intervencion por cada equipo."),
) -> None:
    """Hace una sola pregunta y termina (util para scripts/pruebas)."""
    asyncio.run(_run_debate(question, rounds))


if __name__ == "__main__":
    app()
