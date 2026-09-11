# Instrucciones — Dev 1: Cliente CLI y Orquestador

Tu carpeta: `src/cli/`, `src/orchestrator/`. No necesitas tocar
`src/agents/` ni `src/mcp_server/` (si te hace falta algo de ahi, coordina
con Dev 2 / Dev 3 en vez de modificarlo directamente).

Lee primero `docs/ARCHITECTURE.md` y `docs/TASKS.md` para el panorama
completo.

## Checklist

- [ ] Instalar dependencias y validar que el flujo end-to-end corre:
      `pip install -r requirements.txt`, `cp .env.example .env`,
      `python main.py ask "¿Quien tiene mejor delantera?"`
- [ ] Revisar `src/orchestrator/state.py`: confirmar que el primer turno
      se elige al azar (`random.shuffle`) y que el orden se respeta el
      resto del debate.
- [ ] Revisar `src/orchestrator/graph.py`: el grafo LangGraph enruta
      entre `barcelona` y `real_madrid` usando `add_conditional_edges`,
      terminando cuando `turns_taken >= max_turns`.
- [ ] Mejorar la CLI (`src/cli/main.py`):
  - Comando `chat` (loop interactivo) y `ask` (una sola pregunta) ya
    existen — validar UX, manejo de errores si el servidor MCP no
    arranca, mensajes claros.
  - Opcional: flag para elegir cuantas rondas debate cada equipo
    (`--rounds`, ya soportado, probar con valores >1).
  - Opcional: exportar el debate a un archivo (txt/json).
- [ ] Si cambias el shape del estado (`DebateState`), avisa a Dev 2 (no
      deberia afectarlo, ya que solo interactua via `get_agent(tools)`)
      y documenta el cambio en `docs/ARCHITECTURE.md`.
- [ ] Agregar manejo de errores si `MultiServerMCPClient` no logra
      conectar al servidor MCP (mensaje claro en la CLI, no traceback
      crudo).
- [ ] (Opcional) Agregar tests basicos del router (`_entry_router`,
      `_next_router`) sin necesidad de invocar LLM real, mockeando
      agentes.

## Contrato con los demas devs

- Consumis los agentes solo via `get_agent(tools)` que exponen
  `src/agents/barcelona_agent.py` y `real_madrid_agent.py` (Dev 2). No
  dependas de los prompts internos.
- Consumis las tools MCP solo a traves de `MultiServerMCPClient` +
  `MCP_SERVER_PARAMS` (`src/config/settings.py`). No importes nada de
  `src/mcp_server/` directamente.

## Cuando termines

Abre un PR de `dev1-cli-orchestrator` hacia `main` describiendo los
cambios.
