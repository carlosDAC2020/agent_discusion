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

- [x] Instalar dependencias y probar el servidor de forma standalone:
      `pip install -r requirements.txt`, luego
      `python -m src.mcp_server.server` (probado standalone y via MultiServerMCPClient).
- [x] Revisar/ampliar `data.py`:
  - Completar plantillas de jugadores y equipos (20 jugadores clave, datos
    reales de temporada 2024-2025, palmares y balance historico).
- [x] Revisar/ampliar `server.py`:
  - Cada tool tiene un docstring detallado y maneja el caso de "no encontrado"
    sin lanzar excepciones no controladas. Soporta busqueda flexible y alias.
  - Nuevas tools agregadas y documentadas en `docs/TASKS.md`:
    `get_head_to_head_summary`, `get_trophies_comparison`, `get_injuries_or_squad_status`.
- [x] Mantener retrocompatibilidad de la forma (shape) de las respuestas
      existentes para no romper a Dev 2.
- [x] Suite de pruebas unitarias implementada en `tests/test_mcp_server.py`.

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
