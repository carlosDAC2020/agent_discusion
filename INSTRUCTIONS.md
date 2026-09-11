# Instrucciones — Dev 3: Servidor MCP y datos de futbol

Tu carpeta: `src/mcp_server/`. No necesitas tocar `src/cli/`,
`src/orchestrator/` ni `src/agents/` (si te hace falta algo de ahi,
coordina con Dev 1 / Dev 2 en vez de modificarlo directamente).

Lee primero `docs/ARCHITECTURE.md` y `docs/TASKS.md` para el panorama
completo.

## Archivos

- `src/mcp_server/data.py`: fuente de datos (equipos, jugadores,
  historial de clasicos). Hoy es un diccionario en memoria (mock).
- `src/mcp_server/server.py`: define las tools MCP expuestas via
  `FastMCP` (stdio): `get_team_stats`, `get_player_stats`,
  `compare_players`, `get_head_to_head`.

## Checklist

- [ ] Instalar dependencias y probar el servidor de forma standalone:
      `pip install -r requirements.txt`, luego
      `python -m src.mcp_server.server` (deberia quedar escuchando por
      stdio sin errores; para probarlo integrado, usa
      `python main.py ask "..."` desde la raiz del repo).
- [ ] Revisar/ampliar `data.py`:
  - Completar plantillas de jugadores y equipos (mas jugadores, datos
    mas realistas o actualizados).
  - Opcional: reemplazar el diccionario mock por una integracion con una
    API real de estadisticas de futbol (ej. football-data.org,
    API-Football), manteniendo la misma forma de retorno para no romper
    a Dev 2.
- [ ] Revisar/ampliar `server.py`:
  - Cada tool debe tener un docstring claro (se usa como descripcion
    para el LLM) y manejar el caso de "no encontrado" sin lanzar
    excepciones no controladas.
  - Agregar nuevas tools si Dev 2 las pide (ej. `get_next_match`,
    `get_injuries`), documentando nombre, argumentos y forma del
    resultado en `docs/TASKS.md`.
- [ ] Si cambias la forma (shape) de la respuesta de una tool existente,
      avisa a Dev 2 — el prompt del agente puede depender de esos
      campos.
- [ ] Opcional: agregar cache simple si se conecta a una API externa
      real, para no golpear rate limits durante el debate.

## Contrato con los demas devs

- Tu unico punto de contacto hacia afuera son las tools que registras
  con `@mcp.tool()` en `server.py`. El resto del sistema (Dev 1/Dev 2)
  las consume via `MultiServerMCPClient` + `MCP_SERVER_PARAMS`
  (`src/config/settings.py`) — nunca importan `src/mcp_server/`
  directamente.
- Si necesitas cambiar el comando de arranque del servidor (por ejemplo
  si pasas de stdio a otro transporte), coordina el cambio en
  `src/config/settings.py` con Dev 1.

## Cuando termines

Abre un PR de `dev3-mcp-server` hacia `main` describiendo los cambios.
