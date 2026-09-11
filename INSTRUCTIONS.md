# Instrucciones — Dev 2: Agentes (Barcelona y Real Madrid)

Tu carpeta: `src/agents/`. No necesitas tocar `src/cli/`,
`src/orchestrator/` ni `src/mcp_server/` (si te hace falta algo de ahi,
coordina con Dev 1 / Dev 3 en vez de modificarlo directamente).

Lee primero `docs/ARCHITECTURE.md` y `docs/TASKS.md` para el panorama
completo.

## Archivos

- `src/agents/base_agent.py`: fabrica generica del agente reactivo
  (`create_react_agent` de LangGraph). No deberia necesitar cambios
  frecuentes — solo tocarlo si cambia algo estructural (ej. tipo de
  modelo, forma de pasar tools).
- `src/agents/barcelona_agent.py`: `SYSTEM_PROMPT` + `get_agent(tools)`.
- `src/agents/real_madrid_agent.py`: `SYSTEM_PROMPT` + `get_agent(tools)`.

## Checklist

- [ ] Instalar dependencias y probar el flujo completo:
      `pip install -r requirements.txt`, `cp .env.example .env`
      (completar `ANTHROPIC_API_KEY` u `OPENAI_API_KEY` segun
      `MODEL_PROVIDER`), `python main.py ask "¿Quien tiene mejor
      delantera?"`
- [ ] Afinar `SYSTEM_PROMPT` de cada agente para que:
  - Argumente siempre a favor de su equipo, con datos concretos (no
    inventados — debe usar las tools MCP para respaldar cifras).
  - Reconozca meritos del rival sin cambiar de bando en la conclusion.
  - Mantenga respuestas cortas (4-5 frases) y un tono/personalidad
    diferenciado entre ambos agentes.
- [ ] Verificar que el agente efectivamente llama a las tools MCP
      disponibles (`get_team_stats`, `get_player_stats`,
      `compare_players`, `get_head_to_head` — definidas por Dev 3 en
      `src/mcp_server/server.py`) en vez de inventar numeros.
- [ ] Revisar que el agente no "hable por el otro equipo" ni rompa su
      turno (el orquestador de Dev 1 ya fuerza la alternancia, pero el
      contenido de la respuesta es tu responsabilidad).
- [ ] Opcional: agregar memoria/anti-repeticion para que un agente no
      reutilice el mismo argumento en rondas sucesivas (usa
      `state["messages"]`, que ya recibe como contexto formateado en el
      prompt via el orquestador).
- [ ] Si necesitas una tool nueva (ej. lesiones, proximo partido),
      pidesela a Dev 3 especificando nombre, argumentos y forma de la
      respuesta esperada — no la implementes vos en `src/mcp_server/`.

## Contrato con los demas devs

- Tu unico punto de contacto hacia afuera es la funcion `get_agent(tools)`
  que exponen ambos modulos — Dev 1 la llama pasandole las tools ya
  cargadas desde MCP. No cambies esa firma sin avisar.
- Las `tools` que recibis vienen de `MultiServerMCPClient` (Dev 1/Dev 3),
  son objetos LangChain tool ya listos para pasar a
  `create_react_agent` — no necesitas conocer el servidor MCP por dentro,
  solo que tools existen y su nombre/proposito (ver
  `docs/TASKS.md` o preguntale a Dev 3).

## Cuando termines

Abre un PR de `dev2-agents` hacia `main` describiendo los cambios.
