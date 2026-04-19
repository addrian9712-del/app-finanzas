# Flujo offline/online (Fase 1)

## Principio
La app usa patrón **offline-first**:

1. Toda escritura se guarda primero en base local.
2. Se encola cambio en `sync_queue`.
3. UI confirma: "Guardado localmente".
4. Worker sincroniza cuando hay red.

## Push (local -> remoto)

- Seleccionar cambios `pending`
- Enviar lote (`/v1/sync/push`)
- Si éxito:
  - actualizar versiones locales
  - marcar como sincronizados
- Si error:
  - aumentar `retry_count`
  - registrar `last_error`
  - reintento con backoff

## Pull (remoto -> local)

- Consultar `/v1/sync/pull?since=<timestamp>`
- Aplicar cambios en DB local
- Actualizar `last_pull_at`

## Conflictos

Estrategia base:
- LWW (`updated_at`) para entidades estándar
- Merge por paso en `routine_step_logs` para no perder checks

## Estados de UI sugeridos

- Guardado localmente
- Sincronizado
- Error de sincronización
