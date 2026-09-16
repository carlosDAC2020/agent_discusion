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

- `src/mcp_server/data.py`: fuente de datos (estadisticas ampliadas de equipos,
  plantillas completas de 20 jugadores, historial detallado de clasicos y estado de bajas).
- `src/mcp_server/server.py`: definicion de herramientas MCP:
  - `get_team_stats(team: str)`: estadisticas, palmares y temporada actual.
  - `get_player_stats(player_name: str)`: estadisticas individuales con soporte de alias/apodos.
  - `compare_players(player_a: str, player_b: str)`: comparativa cara a cara.
  - `get_head_to_head()`: ultimos 5 y 10 clasicos, balance historico y mayores goleadas.
  - `get_head_to_head_summary()`: resumen cuantitativo del historial oficial.
  - `get_trophies_comparison()`: comparativa directa de titulos oficiales entre ambos clubes.
  - `get_injuries_or_squad_status(team: str)`: estado de la enfermeria y bajas.


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

## Fase 2 — Nuevas features por dev

La Fase 1 (scaffold + CLI + agentes + MCP) esta cerrada y mergeada en
`main`. La Fase 2 reparte 3 features independientes, una por dev, cada
una en su propia rama/paquete para seguir trabajando en paralelo sin
pisarse. Ver [`CONTRIBUTING.md`](../CONTRIBUTING.md) para el proceso de
ramas, commits y PRs, y la seccion "Contrato entre partes (Fase 2)" ahi
mismo para el detalle de las interfaces entre modulos.

### Dev Harold — Debate en red social (`src/social/`)

Rama: `feature/harold-social-debate` · Label: `dev:harold` `area:social`

- Publicar el debate generado por `src/orchestrator/` en una red social
  (Reddit, Telegram u otra a definir) — cada turno como mensaje/post,
  o el debate completo como hilo.
- Reutilizar el debate ya orquestado, no reimplementar logica de turnos.
- Definir donde vive la configuracion de credenciales de la red social
  (token de bot, subreddit/canal) en `.env` / `src/config/settings.py`,
  siguiendo el mismo patron que las demas API keys.
- Entregable minimo: comando (`python main.py post` o flag en `ask`/
  `chat`) que corre un debate y lo publica.

### Dev Jesus — Debate en audio/video (`src/voice/`)

Rama: `feature/jesus-voice-video-debate` · Label: `dev:jesus` `area:audio-video`

- Convertir cada turno de texto del debate en audio (TTS) y,
  opcionalmente, video (avatar/subtitulos).
- Debe ser un modulo opcional: el flujo de texto por CLI (`ask`/`chat`)
  sigue funcionando sin tener instaladas las dependencias de audio/video.
- Definir el punto de enganche exacto (mismo lugar de donde Harold toma
  el texto de cada turno) para no duplicar logica de consumo del debate.
- Entregable minimo: comando o flag que genera un archivo de audio (o
  video) por turno o del debate completo.

### Dev Carlos — Personalidad y sesgo de los agentes (`src/agents/`)

Rama: `feature/carlos-agent-personality` · Label: `dev:carlos` `area:agent-personality`

- Expandir `SYSTEM_PROMPT` de cada agente: dialecto/regionalismos propios
  del hincha de cada equipo, frases caracteristicas, sesgo personal mas
  marcado (sin dejar de reconocer meritos del rival, regla ya vigente).
- Mantener la forma de la respuesta del agente sin cambios (o avisar en
  el PR si cambia, ya que Harold y Jesus consumen ese texto).
- Entregable minimo: prompts actualizados + verificacion manual de que
  el tono/dialecto se nota en un debate completo (`python main.py ask`).

## Labels usados en GitHub

- Dev responsable: `dev:harold`, `dev:jesus`, `dev:carlos`.
- Area: `area:social`, `area:audio-video`, `area:agent-personality`.
- Tipo: labels estandar de GitHub (`enhancement`, `bug`, `documentation`).
