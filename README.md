# agent_discusion

Debate multiagente sobre futbol: un cliente CLI hace preguntas
(estadisticas, jugadores, historia) y dos agentes reactivos —uno del
**FC Barcelona** y otro del **Real Madrid**— responden por turnos,
argumentando siempre a favor de su equipo y apoyandose en herramientas
externas via **MCP**. La orquestacion usa **LangGraph**.

- Orden de turnos: el primer equipo en hablar se elige al azar; luego se
  respeta la alternancia.
- Arquitectura y diagrama de flujo: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Reparto de tareas para 3 devs: [`docs/TASKS.md`](docs/TASKS.md)

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env   # configurar MODEL_PROVIDER y la API key correspondiente
python main.py ask "¿Quien tiene mejor delantera esta temporada?"
# o modo interactivo:
python main.py chat
```

## Estructura

```
src/
  cli/            # Dev 1 - cliente CLI
  orchestrator/   # Dev 1 - grafo LangGraph, logica de turnos
  agents/         # Dev 2 - agentes reactivos Barcelona / Real Madrid
  mcp_server/      # Dev 3 - servidor MCP con herramientas de futbol
  config/         # configuracion compartida
docs/             # arquitectura y reparto de tareas
```
