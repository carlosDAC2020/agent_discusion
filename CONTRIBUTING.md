# Guía de contribución

Este documento formaliza la metodología de trabajo del proyecto ahora que
entra en su **Fase 2** (3 devs, features en paralelo). Complementa a
[`docs/TASKS.md`](docs/TASKS.md) (qué hace cada dev) y
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (cómo está armado el
sistema).

## Ramas

- `main` es la rama protegida: siempre debe quedar en estado desplegable
  (tests en verde). Nadie commitea directo a `main`, todo entra por PR.
- Nomenclatura: `<tipo>/<dev>-<descripcion-corta>`
  - `tipo`: `feature`, `fix`, `chore`, `docs`, `refactor`, `test`.
  - `dev`: slug del autor principal de la rama (`harold`, `jesus`, `carlos`).
  - Ejemplos:
    - `feature/harold-social-debate`
    - `feature/jesus-voice-video-debate`
    - `feature/carlos-agent-personality`
- Una rama = un tema. Si el trabajo crece y no tiene relación directa con
  el issue original, se abre una rama/issue nuevo en vez de acumular todo.

## Commits — Conventional Commits

Formato: `<tipo>(<scope opcional>): <descripción en imperativo>`

Tipos permitidos:

| Tipo       | Uso                                                         |
|------------|--------------------------------------------------------------|
| `feat`     | Nueva funcionalidad visible para el usuario                  |
| `fix`      | Corrección de bug                                             |
| `docs`     | Solo documentación                                            |
| `refactor` | Cambio de código que no altera comportamiento externo         |
| `test`     | Agregar o corregir tests                                      |
| `chore`    | Tareas de mantenimiento (deps, config, CI)                    |
| `perf`     | Mejora de rendimiento                                          |
| `style`    | Formato, sin cambios de lógica                                 |

Scopes sugeridos (opcionales, en minúscula):
`cli`, `orchestrator`, `agents`, `mcp`, `social`, `voice`, `personality`,
`config`, `docs`, `ci`.

Ejemplos:

```
feat(social): agrega bot de Telegram para publicar turnos del debate
fix(voice): corrige timeout al sintetizar audio largo
docs(tasks): actualiza reparto de fase 2
```

- Un commit = un cambio lógico. Preferir varios commits pequeños y claros
  sobre uno gigante.
- El cuerpo del commit (opcional, línea en blanco + texto) se usa para el
  *por qué*, no para repetir el diff.

## Pull Requests

1. Antes de abrir el PR: rebase/merge de `main` reciente, tests en verde
   localmente (`pytest`).
2. Título del PR en formato Conventional Commits (igual que un commit),
   ej: `feat(social): integración con Reddit para publicar el debate`.
3. Completar la plantilla de PR (`.github/PULL_REQUEST_TEMPLATE.md`):
   resumen, issue relacionado, plan de pruebas, impacto en el contrato
   entre devs (si aplica).
4. **Al menos 1 revisión aprobada** de otro dev antes de mergear (el
   dueño del área afectada, ver `CODEOWNERS` abajo). Excepción: cambios
   triviales de docs/typo pueden autoaprobarse si no hay nadie disponible
   y se anota el motivo en el PR.
5. CI (`pytest` vía GitHub Actions, ver `.github/workflows/ci.yml`) debe
   pasar en verde.
6. Estrategia de merge: **squash and merge** — el mensaje del squash debe
   quedar en formato Conventional Commits (GitHub lo prellena con el
   título del PR). Mantiene el historial de `main` lineal y legible.
7. Borrar la rama al mergear.

### Reglas de protección de `main` (a configurar por un admin del repo)

Este checkout tiene permiso `WRITE`, no `ADMIN`, así que estas reglas no
se pueden activar por API desde aquí — quedan documentadas para que
`carlosDAC2020` las active en *Settings → Branches → Branch protection
rules* para `main`:

- [ ] Require a pull request before merging (mínimo 1 aprobación).
- [ ] Require status checks to pass before merging (`ci / tests`).
- [ ] No permitir force-push ni borrado de `main`.
- [ ] Require branches to be up to date before merging.

## Issues y labels

Cada tarea de feature vive como un Issue en GitHub, etiquetado con:

- **Dev responsable**: `dev:harold`, `dev:jesus`, `dev:carlos`.
- **Área**: `area:social`, `area:audio-video`, `area:agent-personality`
  (o el área existente que corresponda).
- **Tipo**: se reutiliza el label estándar `enhancement` / `bug` /
  `documentation` de GitHub.

Ver el reparto completo de la Fase 2 en
[`docs/TASKS.md`](docs/TASKS.md#fase-2--nuevas-features-por-dev).

## Contrato entre partes (Fase 2)

Para minimizar conflictos, cada feature nueva vive en su propio paquete
y solo se comunica con el resto a través de interfaces ya existentes:

- **Harold — integración social** (`src/social/`): consume el debate ya
  generado por `src/orchestrator/` (no reimplementa lógica de turnos) y
  publica el resultado en la red social elegida. No debe requerir
  cambios en `src/agents/` ni `src/mcp_server/`.
- **Jesus — voz/video** (`src/voice/` o `src/av/`): consume el texto de
  cada turno del debate (mismo punto de entrada que Harold) y genera
  audio/video por turno. Cualquier dependencia pesada (TTS, video) debe
  quedar aislada en su propio módulo y ser opcional (el CLI de texto
  debe seguir funcionando sin instalarla).
- **Carlos — personalidad de agentes** (`src/agents/`): cambios de
  prompt, tono, dialecto y sesgo. Si cambia la *forma* de la respuesta
  del agente (no solo el contenido del prompt) de manera que afecte a
  Harold o Jesus (p. ej. nuevos campos en la salida), debe avisarse en
  el issue correspondiente antes de mergear.

Cualquier cambio de firma/contrato entre módulos se avisa en el PR
(sección "Impacto en el contrato" de la plantilla) y se etiqueta a los
devs afectados.

## Definition of Done

- [ ] Código con tests (cuando aplique) y `pytest` en verde.
- [ ] Sin credenciales ni tokens hardcodeados (usar `.env`).
- [ ] Documentación actualizada si el comportamiento visible cambia
      (`README.md`, `docs/ARCHITECTURE.md`).
- [ ] PR revisado y aprobado por al menos 1 dev.
- [ ] Issue relacionado cerrado automáticamente por el PR (`Closes #N`).
