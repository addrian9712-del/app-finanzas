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
- `POST /v1/sync/push`
- `GET /v1/sync/pull`

## Pruebas

```bash
cd backend
python -m unittest -v test_repository.py
```
