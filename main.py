"""Punto de entrada del CLI.

Uso:
    python main.py chat
    python main.py ask "¿Quien tiene mejor delantera?"
"""

from src.cli.main import app

if __name__ == "__main__":
    app()
