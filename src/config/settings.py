"""Configuracion compartida del proyecto (modelo LLM y arranque del servidor MCP)."""

import os

from dotenv import load_dotenv

load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "anthropic:claude-sonnet-5")

MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", "python")
MCP_SERVER_ARGS = os.getenv("MCP_SERVER_ARGS", "-m src.mcp_server.server").split()

MCP_SERVER_PARAMS = {
    "command": MCP_SERVER_COMMAND,
    "args": MCP_SERVER_ARGS,
    "transport": "stdio",
}
