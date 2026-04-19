# Backend mock (fase de arranque)

Este backend es una implementación mínima ejecutable para validar contratos de Fase 1 sin framework externo.

## Ejecutar servidor mock

```bash
cd backend
python mock_server.py
```

Servidor: `http://localhost:8787`

Auth mock:
- Header: `Authorization: Bearer <user_id>`
- Si no se envía, usa `usr_demo`

## Endpoints implementados

- `GET /v1/user-cards`
- `POST /v1/user-cards`
- `GET /v1/user-cards/{id}`
- `PATCH /v1/user-cards/{id}`
- `DELETE /v1/user-cards/{id}`
- `GET /v1/card-templates`
- `GET /v1/card-instances?date=YYYY-MM-DD`
- `POST /v1/card-instances/generate`
- `POST /v1/card-instances/{id}/complete`
- `GET /v1/user-cards/{id}/routine-steps`
- `POST /v1/user-cards/{id}/routine-steps`
- `PATCH /v1/routine-steps/{id}`
- `DELETE /v1/routine-steps/{id}`
- `GET /v1/daily-plan-items?date=YYYY-MM-DD`
- `POST /v1/daily-plan-items`
- `GET /v1/study-subjects`
- `POST /v1/study-subjects`
- `POST /v1/sync/push`
- `GET /v1/sync/pull?device_id=<id>&since=<ISO8601>`

## Pruebas

```bash
cd backend
python -m unittest discover -v
```

## Validación OpenAPI (soluciona warning de PyYAML)

```bash
ruby scripts/validate_openapi.rb backend/openapi.yaml
```

## Demo UI de integración rápida

Con el backend corriendo, abre `frontend/phase1_demo.html` en navegador para probar:
- templates prediseñadas
- creación de tarjetas
- generación/completado de instancias
- push/pull de sync mock

## Screenshot automático de la demo (sin browser tool interactivo)

Desde la raíz del repo:

```bash
./scripts/capture_demo_screenshot.sh
```

El script intenta, en orden:
1. Playwright local (`node_modules/playwright`)
2. Fallback con Docker (`mcr.microsoft.com/playwright`)

Salida esperada: `artifacts/screenshots/phase1_demo.png`.

## Worker de sync local (Fase 2 - Parte 1)

Se agregó `backend/sync_worker.py` para empujar cambios pendientes de `sync_queue` hacia `/v1/sync/push` con:

- estado `processing` / `done` / `failed`,
- incremento de `retry_count` en fallos,
- función de backoff exponencial con tope.

Ejemplo de ejecución manual:

```bash
cd backend
python sync_worker.py
```
