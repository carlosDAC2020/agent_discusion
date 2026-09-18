# El Clásico Debate 🔵🔴⚪

Dos hinchas con IA que jamás se ponen de acuerdo sobre fútbol — y ahora
también hablan, se mueven por un bar y publican sus peleas en redes
sociales.

---

## La historia (para cualquiera, sin saber de código)

Imaginate un bar. En la barra hay dos parroquianos que no se caen bien:
**Josep**, culé de toda la vida, cría hincha de La Masia y de "Més que un
club"; y **Paco**, madridista convencido, de los que sacan pecho con las
Champions y el "Hala Madrid" en cada frase. Les preguntás cualquier cosa
de fútbol — quién tiene mejor cantera, mejor portero, mejor entrenador —
y arrancan a debatir, cada uno defendiendo a su equipo con datos reales
(no se inventan cifras, las consultan) y con su propio acento y sus
propias manías.

Eso es este proyecto: dos agentes de IA con personalidad propia que
debatís sobre fútbol, y que podés "ver" de varias formas:

- **Por texto**, en una terminal, como un chat normal.
- **En un grupo de Telegram**, donde Josep y Paco son literalmente dos
  cuentas distintas (cada uno con su nombre y su foto) que se contestan
  en vivo — y cualquiera en el grupo puede escribir `/debate <pregunta>`
  para que arranquen a discutir solos, sin que nadie toque una consola.
- **En Reddit**, como un post con hilo de comentarios.
- **En una simulación 2.5D de un bar**, con pixel art, donde Josep y
  Paco caminan, se sientan, hacen vida ambiente — y cuando les tocás el
  timbre con una pregunta real, se plantan y debaten con voz sintetizada
  (Gemini TTS), como si estuvieran ahí de verdad.

No hay un guion escrito: cada respuesta la genera un modelo de lenguaje
(Gemini, Claude o GPT, a elección) en el momento, con datos reales de
estadísticas de fútbol que consulta sobre la marcha.

---

## Para devs (la parte técnica)

### Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env   # completar MODEL_PROVIDER y su API key
python main.py ask "¿Quien tiene mejor delantera esta temporada?"
```

### Comandos

| Comando | Qué hace |
|---|---|
| `python main.py ask "<pregunta>"` | Una pregunta, un debate, termina. Flags: `--mode` (`mcp`\|`knowledge`), `--style` (`debate`\|`answer`), `--rounds`, `--export <archivo>`, `--publish-to` (`telegram`\|`reddit`). |
| `python main.py chat` | Modo interactivo, loop de preguntas hasta escribir `salir`. |
| `python main.py listen` | Escucha un grupo de Telegram: cualquiera escribe `/debate <pregunta>` y dispara el debate solo, publicando la respuesta. Corre indefinidamente (Ctrl+C para salir). |
| `python main.py sim` | Simulación 2.5D del bar en Pygame. Flags: `--debug`, `--demo-movement`, `--bdi` (comportamiento autónomo), `--dialogue` (debate real con voz). |

### Arquitectura y reparto de trabajo

- Diagrama de flujo y decisiones de diseño: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Qué construyó cada dev y en qué issue: [`docs/TASKS.md`](docs/TASKS.md)
- Cómo se trabaja en este repo (ramas, commits, PRs, CI): [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Setup que solo puede hacer el owner del repo (branch protection, etc.): [`docs/OWNER_SETUP.md`](docs/OWNER_SETUP.md)

### Estructura

```
src/
  cli/            # Cliente CLI (Typer): ask, chat, listen, sim
  orchestrator/   # Grafo LangGraph: logica de turnos del debate
  agents/         # Agentes reactivos Josep (Barcelona) y Paco (Real Madrid)
  mcp_server/     # Servidor MCP: stats de futbol, comparativas, historial de clasicos
  social/         # Publica el debate en redes sociales
    telegram_publisher.py   # 3 bots (narrador + uno por equipo)
    telegram_listener.py    # escucha "/debate <pregunta>" en el chat
    reddit_publisher.py     # post + comentarios encadenados
    discord_publisher.py    # planeado (stub)
    bluesky_publisher.py    # planeado (stub)
  simulation/     # Simulacion 2.5D en Pygame: BDI, navegacion A*, audio (Gemini TTS)
  config/         # Configuracion compartida (.env)
docs/             # Arquitectura, reparto de tareas, setup de owner
tests/            # pytest - sin llamar a LLMs ni APIs reales
```

### Variables de entorno (`.env`)

| Variable | Para qué |
|---|---|
| `MODEL_PROVIDER`, `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Modelo LLM que usan los agentes. |
| `TAVILY_API_KEY` | Búsqueda web opcional (modo `mcp`). |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_BOT_TOKEN_BARCELONA` + `TELEGRAM_BOT_TOKEN_REAL_MADRID` + `TELEGRAM_CHAT_ID` | `--publish-to telegram` y `listen`. Los 3 bots deben estar en un **grupo** (no canal). |
| `REDDIT_CLIENT_ID/SECRET`, `REDDIT_USERNAME/PASSWORD`, `REDDIT_SUBREDDIT` | `--publish-to reddit`. |
| `MCP_SERVER_COMMAND` / `MCP_SERVER_ARGS` | Arranque del servidor MCP (default: automático). |

Detalle completo de cada una, con instrucciones de dónde conseguirlas:
[`.env.example`](.env.example).

### Tests

```bash
pytest -q
```

Todo mockeado (sin llamar a LLMs, Telegram, Reddit ni MCP reales).

### Stack

LangGraph (orquestación) · MCP (herramientas de datos) · Typer + Rich
(CLI) · Pygame (simulación) · Telegram Bot API · PRAW (Reddit) · Gemini
TTS (voz).
