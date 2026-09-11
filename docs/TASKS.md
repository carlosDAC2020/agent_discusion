# Reparto de tareas (3 devs)

La arquitectura separa el proyecto en 3 frentes independientes, cada uno
con su propia carpeta, para minimizar conflictos entre desarrolladores.

## Dev 1 — Cliente CLI y Orquestador (`src/cli`, `src/orchestrator`)

- `src/cli/main.py`: comandos `chat` (interactivo) y `ask` (una sola
  pregunta), formato de salida con `rich`.
- `src/orchestrator/state.py`: estado inicial del debate, seleccion
  aleatoria del primer turno.
- `src/orchestrator/graph.py`: grafo LangGraph, enrutamiento entre
  agentes, condicion de fin (numero de rondas).
- Pendiente / ideas de extension: historial persistente entre preguntas,
  comando para elegir cuantas rondas debatir, exportar el debate a un
  archivo.

## Dev 2 — Agentes (`src/agents`)

- `src/agents/base_agent.py`: fabrica generica de agente reactivo
  (`create_react_agent`), no deberia necesitar cambios frecuentes.
- `src/agents/barcelona_agent.py` y `real_madrid_agent.py`: prompt de
  sistema (personalidad, tono, sesgo argumentativo), reglas de cuando
  usar herramientas.
- Pendiente / ideas de extension: afinar prompts para respuestas mas
  naturales, agregar memoria de argumentos ya usados para no repetirse,
  limitar longitud de respuesta.

## Dev 3 — Servidor MCP y datos (`src/mcp_server`)

- `src/mcp_server/data.py`: fuente de datos (estadisticas de equipos,
  jugadores, historial de clasicos). Hoy es un diccionario en memoria.
- `src/mcp_server/server.py`: definicion de herramientas MCP
  (`get_team_stats`, `get_player_stats`, `compare_players`,
  `get_head_to_head`).
- Pendiente / ideas de extension: reemplazar los datos mock por una API
  real de estadisticas, agregar cache, nuevas herramientas (ej.
  `get_next_match`, `get_injuries`).

## Contrato entre partes (para trabajar en paralelo)

- Dev 2 y Dev 3 se comunican solo a traves de las herramientas MCP
  definidas en `server.py` (nombre, argumentos, forma del dict de
  retorno). Cualquier cambio de firma debe avisarse al Dev 2.
- Dev 1 y Dev 2 se comunican solo a traves de `build_reactive_agent` y
  las funciones `get_agent(tools)` expuestas por cada agente — Dev 1 no
  necesita conocer los prompts internos.
- `src/config/settings.py` centraliza variables de entorno (modelo LLM,
  comando de arranque del servidor MCP) para que los 3 devs usen la
  misma fuente de configuracion.

## Como correr el proyecto localmente

```bash
pip install -r requirements.txt
cp .env.example .env   # completar API key del proveedor elegido
python main.py ask "¿Quien tiene mejor delantera esta temporada?"
```
