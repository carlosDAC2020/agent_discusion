"""Configuracion compartida del proyecto (modelo LLM y arranque del servidor MCP)."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "anthropic:claude-sonnet-5")

# Por defecto usamos el mismo interprete que corre la CLI (sys.executable)
# en vez de "python" a secas: en Windows ese nombre puede resolver al stub
# de la Microsoft Store en lugar del interprete real del entorno.
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", sys.executable)
MCP_SERVER_ARGS = os.getenv("MCP_SERVER_ARGS", "-m src.mcp_server.server").split()

MCP_SERVER_PARAMS = {
    "command": MCP_SERVER_COMMAND,
    "args": MCP_SERVER_ARGS,
    "transport": "stdio",
}
