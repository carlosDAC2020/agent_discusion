# Configuración pendiente del owner (`carlosDAC2020`)

Estas acciones requieren permiso **Admin** sobre el repo, que ningún
otro dev tiene por API — hay que hacerlas manualmente desde GitHub,
una sola vez. Checklist:

- [ ] 1. Invitar a `oruz-123` como colaborador
- [ ] 2. Activar branch protection en `main`
- [ ] 3. Activar borrado automático de ramas al mergear
- [ ] 4. Confirmar que las Actions corren sin aprobación manual
- [ ] 5. (Opcional) Revisar el primer run de `secret-scan`

---

## 1. Invitar a `oruz-123` (cuenta secundaria de Carlos)

`oruz-123` es la cuenta con la que ya aparecen commits antiguos en el
repo, pero no está en la lista de colaboradores actual — así que no se
le puede asignar issues hasta que se la invite.

1. **Settings** (del repo) → **Collaborators and teams**.
2. **Add people** → escribir `oruz-123` → seleccionar.
3. Rol: **Write** (igual que `haroldstyven` y `lastHunter956`).
4. `oruz-123` debe aceptar la invitación (le llega por email o
   notificación de GitHub).
5. Una vez aceptada, se le puede asignar el issue #9 (`feat(agents):
   expandir personalidad...`) también a `oruz-123` si Carlos prefiere
   usar esa cuenta en vez de `carlosDAC2020`.

## 2. Branch protection para `main`

**Settings → Branches → Branch protection rules → Add rule**

- Branch name pattern: `main`
- [x] Require a pull request before merging
  - Required approvals: `1`
  - [x] Dismiss stale pull request approvals when new commits are pushed
- [x] Require status checks to pass before merging
  - [x] Require branches to be up to date before merging
  - Buscar y marcar los checks (apareceran despues de que corra al
    menos un PR con las Actions nuevas): `tests`, `ruff`, `gitleaks`.
- [x] Require conversation resolution before merging
- [ ] Allow force pushes → dejar **desactivado**
- [ ] Allow deletions → dejar **desactivado**

Guardar con **Create** / **Save changes**.

## 3. Borrado automático de ramas al mergear

**Settings → General → Pull Requests**

- [x] Automatically delete head branches

Esto borra la rama de cada PR apenas se mergea (complementa al workflow
`branch-cleanup.yml`, que limpia lo que quede suelto — ramas viejas ya
mergeadas que no pasaron por este flujo, o borradas manualmente por
alguien fuera de un PR).

## 4. Confirmar permisos de Actions

**Settings → Actions → General**

- En "Actions permissions": dejar **Allow all actions and reusable
  workflows** (o al menos permitir `actions/*` y `gitleaks/*`,
  `crazy-max`/`dorny` no se usan aquí).
- En "Workflow permissions": alcanza con **Read and write permissions**
  si se quiere que `stale.yml` pueda cerrar issues/PRs automáticamente
  (si no, esa Action fallará al intentar comentar/cerrar).

## 5. (Opcional) Revisar `secret-scan`

`gitleaks-action@v2` funciona sin licencia en repos personales/públicos.
Si GitHub pide un `GITLEAKS_LICENSE` (solo pasa en cuentas de
Organización), avisar — se puede cambiar a `trufflesecurity/trufflehog`
como alternativa sin licencia.

---

Una vez completado este checklist, cualquier PR nuevo va a requerir
review + CI en verde antes de poder mergear a `main`, y las ramas ya
mergeadas se van a limpiar solas. Ver [`CONTRIBUTING.md`](../CONTRIBUTING.md)
para el resto del flujo de trabajo.
