# FlowOps

Plataforma de automatización de procesamiento documental. Backend en FastAPI + MongoDB (Motor, async).

## Requisitos

- Python 3.11+
- MongoDB (local, Docker o Atlas)
- Docker + Docker Compose (opcional, para levantar toda la infraestructura)

## Puesta en marcha

```bash
python3 -m venv venv
source venv/bin/activate
make install

cp .env.example .env
# editar .env y ajustar JWT_SECRET (mínimo 32 caracteres) y credenciales

make dev
```

La API queda disponible en `http://localhost:8000`, con documentación interactiva en `/docs` y `/redoc`.

## Con Docker Compose

Levanta la API junto con MongoDB, Redis, RabbitMQ y MinIO:

```bash
make up
make logs
```

## Comandos

| Comando          | Descripción                                  |
|-------------------|-----------------------------------------------|
| `make dev`        | Servidor con auto-reload                      |
| `make run`        | Servidor en modo producción (2 workers)       |
| `make test`       | Corre la suite de tests (`pytest`)            |
| `make lint`       | `ruff check`                                  |
| `make format`     | `black` + `ruff --fix`                        |
| `make typecheck`  | `mypy`                                        |
| `make up`/`down`  | Levanta/baja los servicios de Docker Compose  |

## Endpoints principales

```
GET    /health
GET    /config                                       (solo fuera de production)

POST   /api/v1/organizations
GET    /api/v1/organizations
GET    /api/v1/organizations/{id}
PUT    /api/v1/organizations/{id}
DELETE /api/v1/organizations/{id}
PATCH  /api/v1/organizations/{id}/activate
PATCH  /api/v1/organizations/{id}/deactivate

POST   /api/v1/organizations/{id}/users
GET    /api/v1/organizations/{id}/users
DELETE /api/v1/organizations/{id}/users/{user_id}
```

Ver [REPOSITORY.md](REPOSITORY.md) para la arquitectura completa, decisiones de diseño y notas de performance/memoria.
