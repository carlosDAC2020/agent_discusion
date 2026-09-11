# Instrucciones por dev

Checklists de trabajo de cada uno de los 3 devs del proyecto (ver
`docs/TASKS.md` para el reparto completo y `docs/ARCHITECTURE.md` para el
panorama de arquitectura). Cada seccion documenta el trabajo ya hecho en
su rama correspondiente.

## Dev 1 — Cliente CLI y Orquestador (`src/cli/`, `src/orchestrator/`)

Rama: `dev1-cli-orchestrator`.

- [x] Instalar dependencias y validar el flujo end-to-end.
- [x] Revisar `src/orchestrator/state.py` (turno inicial aleatorio,
      orden respetado el resto del debate).
- [x] Revisar `src/orchestrator/graph.py` (enrutamiento condicional,
      fin por `max_turns`).
- [x] Mejorar la CLI (`src/cli/main.py`): UX de `chat`/`ask`, manejo de
      errores claro si falla la conexion MCP o la inicializacion del
      modelo (sin traceback crudo).
- [x] Exportar el debate a un archivo (`--export`, txt/json).
- [x] Tests basicos del router (`_entry_router`, `_next_router`) con
      agentes mockeados, sin invocar LLM real.

## Dev 2 — Agentes (`src/agents/`)

Rama: `dev2-agents`.

- [x] Instalar dependencias y probar el flujo completo.
- [x] Afinar `SYSTEM_PROMPT` de cada agente: postura siempre a favor de
      su equipo, reconoce meritos del rival sin cambiar de bando, tono y
      personalidad diferenciados, respuestas concisas (4-5 frases).
- [x] Verificar que los agentes usan las tools MCP en vez de inventar
      cifras.
- [x] Anti-repeticion: un agente no reutiliza el mismo dato/argumento en
      rondas sucesivas.
- [x] 3 bugs bloqueantes encontrados y corregidos durante pruebas
      end-to-end (afectan a los 3 devs):
  - `MCP_SERVER_COMMAND` ahora usa `sys.executable` por defecto en vez de
    `"python"` a secas (evita el stub roto de Microsoft Store en
    Windows).
  - Nodos del grafo (`src/orchestrator/graph.py`) convertidos a
    `async def` con `agent.ainvoke()` (las tools MCP son async-only).
  - Normalizacion del `content` del modelo a texto plano
    (`_extract_text`), ya que Gemini puede devolver una lista de bloques
    en vez de un string simple.
  - Consola de Windows forzada a UTF-8 para que no se rompan acentos.

## Dev 3 — Servidor MCP y datos (`src/mcp_server/`)

Rama: `dev3-mcp-server`.

- [x] Instalar dependencias y probar el servidor standalone y via
      `MultiServerMCPClient`.
- [x] Ampliar `data.py`: 20 jugadores clave, estadisticas de temporada
      2024-2025, palmares y balance historico de clasicos, estado de
      bajas/enfermeria.
- [x] Ampliar `server.py`: busqueda flexible con alias y normalizacion
      de acentos, manejo de errores controlado (sin excepciones no
      atrapadas), nuevas tools (`get_head_to_head_summary`,
      `get_trophies_comparison`, `get_injuries_or_squad_status`).
- [x] Retrocompatibilidad de la forma (shape) de las respuestas
      existentes para no romper a Dev 1/Dev 2.
- [x] Suite de pruebas unitarias (`tests/test_mcp_server.py`).

## Contrato entre partes

Ver `docs/TASKS.md` — Dev 1 consume agentes via `get_agent(tools)` (Dev 2)
y tools MCP via `MultiServerMCPClient` + `MCP_SERVER_PARAMS`
(`src/config/settings.py`); Dev 2 consume tools MCP ya cargadas sin
conocer `src/mcp_server/` por dentro; Dev 3 expone tools via `@mcp.tool()`
manteniendo la forma de las respuestas para no romper a los demas.
