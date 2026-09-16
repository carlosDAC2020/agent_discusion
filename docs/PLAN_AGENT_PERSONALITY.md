# Plan: personalidad, dialecto y pique entre agentes (issue #9)

Rama: `feature/carlos-agent-personality`
Alcance: `src/agents/barcelona_agent.py`, `src/agents/real_madrid_agent.py` y,
como ajuste puntual de soporte, `src/agents/base_agent.py` +
`src/config/settings.py` (ambos ya bajo responsabilidad de Dev 2 segun sus
propios docstrings) para subir la temperatura del modelo — ver seccion 3.1.
Fuera de alcance: `src/mcp_server/`, `src/orchestrator/`, formato de la
respuesta (el texto sigue siendo texto plano; Harold y Jesus consumen esa
forma tal cual).

## 1. Objetivo

Hoy el `SYSTEM_PROMPT` de cada agente es correcto pero genérico: cualquiera de
los dos podría decir las mismas frases con el nombre del equipo cambiado. La
idea es que se note, sin leer el nombre del agente, cuál es culé y cuál
madridista — por vocabulario, no solo por a quién defiende — y que en modo
debate se pique más al rival en vez de solo "reconocer méritos y rebatir" de
forma aséptica.

## 2. Investigación (fuentes reales, no inventadas)

Búsquedas hechas (ver sesión): frases de hinchas del Barça, expresiones
catalanas cotidianas, frases típicas madridistas, y pullas típicas de la
rivalidad Madrid-Barça en redes.

**Barcelona / catalán** — [LALIGA: por qué "culés"](https://www.laliga.com/en-GB/news/why-are-barcelona-called-the-cules),
[expresiones catalanas - Lingopie](https://es.lingopie.com/blog/expresiones-en-catalan/),
[frases hechas en catalán](https://www.cursdecatala.com/es/frases-hechas-en-catalan/):
- Lema: **"Més que un club"** (más que un club).
- Grito de aliento: **"Visca el Barça"**, **"Força Barça"**.
- Palabras/muletillas catalanas de uso cotidiano para salpicar el texto (no
  frases enteras en catalán — el agente responde en español, solo mecha
  regionalismos): **"collons"** (interjección, "¡joder!"/"¡cojones!"),
  **"escolta"** ("escucha", para llamar la atención antes de un argumento),
  **"hala"** (ánimo/venga — cuidado: en catalán es de aliento suave, NO
  confundir con el "¡Hala Madrid!" rival, hay que evitar la palabra "hala"
  sola para no generar ambigüedad — se usa mejor "va, va" o "som-hi" =
  "vamos"), **"noi/noia"** ("tío/tía", coloquial), **"seny"** (sensatez,
  concepto identitario catalán: "aquí hace falta seny, no cuentos").
- Identidad "culé": alusión a que son aficion "más que un club", con arraigo
  social y de cantera (La Masia) frente al gasto del rival.

**Real Madrid / madridismo** — [okdiario: origen de "Hala Madrid"](https://okdiario.com/diariomadridista/real-madrid/que-significa-hala-madrid-quien-invento-esa-frase-473417),
[frases del Real Madrid](https://www.frasess.net/frases-del-real-madrid-1521.html):
- Grito de guerra: **"¡Hala Madrid!"** (del árabe "hala" = "adelante, vamos").
- **"Hasta el final"**, **"Con el Real Madrid hasta la muerte"**.
- Identidad histórica: referencias a "el equipo del siglo", a las Copas de
  Europa/Champions acumuladas, al Santiago Bernabéu, y a la remontada como
  sello ("el que resiste, gana").

**Pullas cruzadas de la rivalidad** (clásico contenido de redes/foros de
fútbol, no atribuible a una fuente única, se usa como referencia de tono, no
se cita textual):
- Barcelona hacia Madrid: cuestionar el gasto en fichajes vs. cantera propia,
  ironizar con los títulos "antiguos" del Madrid frente al juego actual.
- Madrid hacia Barcelona: cuestionar quejas arbitrales del barcelonismo,
  ironizar con "Més que un club" como excusa para todo.
- Ambos lados: mencionar de pasada rivalidades históricas (Cruyff/Guardiola
  vs. Di Stéfano/Zidane) como argumento de autoridad.

Estas pullas se usan como **plantilla de tono para el modo debate**, nunca
como insulto personal ni discurso de odio — ver sección de límites.

## 3. Diseño del prompt

Para cada agente, agregar al `SYSTEM_PROMPT` (no reemplazar las reglas
existentes de "usar tools", "no inventar cifras", "no cambiar de bando"):

1. **Bloque de identidad/dialecto**: 1 párrafo nuevo con las muletillas
   propias del equipo (lista cerrada de 5-6 palabras/expresiones) y la regla
   de "usalas de vez en cuando, no en cada frase, para que suene natural y
   no una caricatura".
2. **Bloque de pique (solo aplica en `STYLE_DEBATE`, vía `base_agent.py` ya
   inyecta el modo)**: nueva instrucción explícita de picar al rival con una
   pulla característica de la rivalidad antes de rebatir con el dato — hoy
   el prompt de `base_agent.py` ya dice "reconoce brevemente su punto y
   rebatilo"; se añade en el prompt de cada equipo una lista de 2-3 pullas
   propias para variar el pique sin repetirse debate tras debate.
3. **Límite explícito**: nunca insultar a personas reales, hinchas o
   jugadores fuera de la ironía deportiva de toda la vida; nada de discurso
   de odio, xenofobia ni comentarios sobre catalanismo/nacionalismo político
   — el catalán es sabor de idioma/identidad de equipo, no una toma de
   postura política. Esto va explícito en el prompt para evitar que el LLM
   se vaya de tema si alguien pregunta algo politizado.

### 3.1. Temperatura del modelo

Se sube la temperatura de generacion (`init_chat_model(..., temperature=X)`)
para que el dialecto y las pullas no suenen enlatadas de debate en debate.
Se agrega `MODEL_TEMPERATURE` a `src/config/settings.py` (default `0.9`,
configurable via env var `MODEL_TEMPERATURE`) y se pasa como kwarg en
`build_reactive_agent` (`src/agents/base_agent.py`). Riesgo: mas temperatura
puede aumentar la chance de alucinar datos; se mitiga porque las reglas
existentes de "nunca inventes cifras, usa las tools primero" siguen intactas
en el prompt — la temperatura afecta el estilo/variedad del texto, no obliga
a inventar numeros. Si en la verificacion manual se nota que el agente
alucina mas de la cuenta, bajar a 0.7-0.8 antes de abrir el PR.

## 4. Verificación de que no rompe el contrato (issue #9, criterio 3)

- El prompt sigue devolviendo texto plano (ninguna tool, ningún schema
  nuevo). `build_reactive_agent` no se toca.
- Se corre manualmente con las 4 combinaciones de modo/estilo:
  ```
  python main.py ask "quien tiene mejor cantera" --mode knowledge --style debate
  python main.py ask "quien tiene mejor cantera" --mode mcp --style debate
  python main.py ask "quien tiene mejor cantera" --mode knowledge --style answer
  python main.py ask "quien tiene mejor cantera" --mode mcp --style answer
  ```
  Confirmar que en `debate` se nota el pique y el dialecto, que en `answer`
  el agente sigue respondiendo solo (sin rebatir), y que en ningún caso
  cambia el tipo de dato devuelto (sigue siendo un string de respuesta).

## 5. Riesgos / cosas a vigilar

- **Sobreactuación**: si se abusa del catalán/regionalismo, puede sonar a
  caricatura o quedar ilegible. Mitigación: instrucción explícita de
  "ocasional, no en cada frase" + lista cerrada y corta de expresiones.
  Nombre del truco de la industria de prompting: *dial de intensidad
  explícito* ("de vez en cuando", no "siempre").
- **Deriva a temas sensibles**: el catalanismo tiene carga política real
  fuera del fútbol. El prompt debe anclar el catalán únicamente como
  identidad futbolera/cultural del hincha, y bloquear explícitamente que el
  agente opine de política catalana o independentismo.
- **Ruptura de contrato con Harold/Jesus**: si el texto queda con demasiadas
  palabras en catalán puro (no traducidas), puede afectar TTS (agente de
  Jesus, voz) o legibilidad en redes (agente de Harold). Mitigación: las
  expresiones catalanas elegidas son cortas, reconocibles y ya con presencia
  en el español coloquial de aficionados (o se explican solas en contexto),
  nunca frases largas 100% en catalán.

## 6. Extension de alcance (decidido con Carlos, post-implementacion inicial)

Ademas de lo anterior, se agregaron dos features pedidas directamente:

1. **Nombres propios en vez de nombre de equipo**: `DISPLAY_NAME` en cada
   agente (`Josep` para Barcelona, `Paco` para Real Madrid) y el
   `SYSTEM_PROMPT` de cada uno ahora se presenta con ese nombre en vez de
   "Culer IA"/"Merengue IA". El label que muestra la CLI (`TEAM_LABELS` en
   `src/cli/main.py`) y el que arma el orquestador (`_team_label` en
   `src/orchestrator/graph.py`) pasan a leer `DISPLAY_NAME` de cada modulo
   de agente en vez de tener "FC Barcelona"/"Real Madrid" hardcodeado.
2. **Streaming en tiempo real**: la CLI (`_run_debate` en
   `src/cli/main.py`) pasa de `graph.ainvoke(state)` (esperar todo el
   debate y recien ahi mostrarlo) a `graph.astream_events(state)`, con un
   panel `rich.live.Live` por turno que se va llenando token a token (y con
   las llamadas a tools apareciendo arriba del texto a medida que ocurren),
   para dar trazabilidad real de como se genera cada respuesta.

**Nota de alcance**: `src/cli/main.py` y `src/orchestrator/graph.py` estan
formalmente asignados a Dev 1 en `docs/TASKS.md`, no a Dev 2 (agentes). Se
decidio con Carlos (owner, y quien tambien lleva Dev 1 en este proyecto)
implementarlo en esta misma rama para no bloquear el avance, mencionandolo
explicitamente aqui y en el PR para que quede trazado. `_team_label`
cambia de logica (lee `DISPLAY_NAME` en vez de un `if` hardcodeado) pero el
contrato de datos (`DebateState`, forma de `messages`) no cambia — los
tests existentes de `tests/test_orchestrator.py` siguen validos porque
siguen usando `_make_node`/`agent.ainvoke` tal cual (el streaming se agrega
solo en la capa de CLI, no en el grafo). Se actualizo un test que
hardcodeaba el label viejo ("Real Madrid" -> "Paco").

**Detalle tecnico de la implementacion de streaming**: se usa
`graph.astream_events(state, version="v2")` en vez de `graph.ainvoke`.
Los eventos `on_chat_model_stream`/`on_tool_start` internos del agente
ReAct no traen el nombre de nuestro nodo externo (`barcelona`/
`real_madrid`) en `metadata.langgraph_node` -viene "agent"/"tools", que es
el nombre interno del grafo de `create_react_agent`-, asi que el turno
activo se rastrea con los eventos `on_chain_start`/`on_chain_end` del nodo
externo (que si vienen con `name` = `"barcelona"`/`"real_madrid"`), ya que
la ejecucion es estrictamente secuencial entre ambos equipos.

**Bug encontrado y corregido durante la verificacion manual**: el
`output` de un evento `on_chain_end` de un nodo es solo lo que esa funcion
de nodo retorna (`{"messages": [...], "turns_taken": N}`), no el estado
completo del grafo como si devuelve `graph.ainvoke`. Al usarlo directo
para `--export`, `turn_order` quedaba `null` en el archivo exportado. Se
corrigio mergeando ese resultado parcial con el estado inicial
(`{**state, **final_result, ...}`) antes de exportar.

## 7. Plan de commits

1. Este documento de plan.
2. `barcelona_agent.py`: nuevo bloque de dialecto/pique culé.
3. `real_madrid_agent.py`: nuevo bloque de dialecto/pique madridista.
4. Verificación manual (los 4 comandos de la sección 4) documentada en el PR.
