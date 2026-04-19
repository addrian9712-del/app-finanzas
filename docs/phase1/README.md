# App Finanzas — Fase 1 (Bootstrap)

Este entregable inicial prepara la base técnica para construir la app modular:

- Finanzas personales
- Tarjetas prediseñadas/personalizadas (tareas, rutinas, metas, estudio)
- Agenda diaria
- Estudio
- Arquitectura offline-first con sincronización

## Objetivo de Fase 1

Definir cimientos consistentes para que el desarrollo avance por módulos sin romper compatibilidad:

1. Estructura funcional de pantallas
2. Modelo de datos inicial (SQL)
3. Contrato API inicial (OpenAPI)
4. Eventos de dominio (lógica de negocio)
5. Flujo de sincronización offline/online

## Entregables de esta fase

- `docs/phase1/screen-structure.md`
- `docs/phase1/domain-events.md`
- `docs/phase1/offline-online-flow.md`
- `backend/schema.sql`
- `backend/openapi.yaml`

## Siguiente fase sugerida

- Implementar frontend (pantallas Home / Tarjetas / Agenda)
- ✅ CRUD base de `user_cards`, `card_instances`, `routine_steps` en backend mock
- ✅ Gate de calidad pre-Fase 2 (alineación OpenAPI/mock, validaciones y conflictos sync)
- ✅ Worker de sincronización local (base push/retry/backoff)

## Nota operativa (PR bloqueada por cambios fuera de Codex)

Si aparece el mensaje de Codex que impide actualizar una PR existente, no intentes forzar esa PR:

- crea una PR nueva desde una rama nueva;
- usa `scripts/recover_pr_branch.sh` para automatizar recuperación de rama;
- referencia `docs/ops/pr-recovery.md` para el flujo completo.
