"""Configuracion compartida del proyecto (modelo LLM y arranque del servidor MCP)."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "google_genai:gemini-3.6-flash")

# Temperatura del modelo: mas alta = respuestas mas creativas/variadas (util
# para que el dialecto y las pullas de cada agente no suenen repetidas debate
# tras debate), mas baja = respuestas mas deterministas. Default subido desde
# el valor por defecto del proveedor (~0.7) para dar mas variedad al modo
# debate sin volverse incoherente.
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.9"))

# API key para la tool de busqueda web (Tavily, https://tavily.com - tier gratuito)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Credenciales para publicar el debate en Telegram (src/social/telegram_publisher.py).
# Un bot POR EQUIPO (cada uno se obtiene hablando con @BotFather): asi Josep y
# Paco publican sus turnos como cuentas de Telegram independientes, no como un
# unico bot narrando ambos lados. Chat id: el canal/chat destino, con AMBOS
# bots agregados ahi como administradores.
TELEGRAM_BOT_TOKEN_BARCELONA = os.getenv("TELEGRAM_BOT_TOKEN_BARCELONA", "")
TELEGRAM_BOT_TOKEN_REAL_MADRID = os.getenv("TELEGRAM_BOT_TOKEN_REAL_MADRID", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Credenciales para publicar el debate en Reddit (src/social/reddit_publisher.py).
# App tipo "script" creada en https://www.reddit.com/prefs/apps (da client_id
# y client_secret), mas usuario/clave de la cuenta que va a postear y el
# subreddit destino (sin "r/", solo el nombre).
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "agent_discusion-debate-bot/0.1")
REDDIT_SUBREDDIT = os.getenv("REDDIT_SUBREDDIT", "")

# Por defecto usamos el mismo interprete que corre la CLI (sys.executable)
# en vez de "python" a secas: en Windows ese nombre puede resolver al stub
# de la Microsoft Store en lugar del interprete real del entorno.
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND") or sys.executable
MCP_SERVER_ARGS = os.getenv("MCP_SERVER_ARGS", "-m src.mcp_server.server").split()

MCP_SERVER_PARAMS = {
    "command": MCP_SERVER_COMMAND,
    "args": MCP_SERVER_ARGS,
    "transport": "stdio",
}

# Modos de respuesta de los agentes, configurables desde la CLI.
# MODE_KNOWLEDGE: el agente responde solo con su conocimiento entrenado, sin tools.
# MODE_MCP: el agente puede usar las tools MCP (stats internas + busqueda web) para fundamentar la respuesta.
MODE_KNOWLEDGE = "knowledge"
MODE_MCP = "mcp"
MODES = (MODE_KNOWLEDGE, MODE_MCP)

# Estilos de interaccion entre agentes, configurables desde la CLI.
# STYLE_ANSWER: cada agente responde la pregunta de forma independiente, sin ver ni rebatir al rival.
# STYLE_DEBATE: los agentes ven lo que dijo el rival y responden defendiendo su postura, sabiendo que estan debatiendo.
STYLE_ANSWER = "answer"
STYLE_DEBATE = "debate"
STYLES = (STYLE_ANSWER, STYLE_DEBATE)
