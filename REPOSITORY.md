# REPOSITORY.md

Documentación técnica del repositorio: estructura, arquitectura y decisiones de performance/memoria.

El repositorio contiene dos servicios: el **backend API** (`app/`, FastAPI + MongoDB) y el **servicio OCR** (`ocr-service/`, worker de RabbitMQ con Tesseract). Ver la sección "Servicio OCR" al final.

## Stack

- **FastAPI** (ASGI, async) + **Uvicorn** (`uvicorn[standard]` trae `uvloop` y `httptools`)
- **MongoDB** vía **Motor** (driver async oficial)
- **Pydantic v2** / **pydantic-settings** para modelos y configuración
- **argon2-cffi** para hashing de contraseñas (Argon2id, ganador del PHC, resistente a GPU cracking)
- **PyJWT** para tokens de acceso/refresh (HS256)
- **aio-pika** para publicar/consumir RabbitMQ de forma async
- **redis** (asyncio) para rate limiting y cache
- **minio** para almacenamiento de documentos

## Estructura

```
app/
├── main.py                      # instancia FastAPI, middlewares, routers, exception handlers
├── core/
│   ├── lifespan.py              # ciclo de vida: Mongo + índices + Redis + consumer de ocr_results
│   ├── cache/redis.py           # cliente Redis async (rate limiting / cache, fail-open)
│   └── config/
│       ├── settings.py          # pydantic-settings (una clase por servicio, cada una lee .env)
│       └── database/
│           ├── mongo.py         # singleton Motor con connection pooling configurable
│           └── deps.py          # dependencia get_db compartida por todos los routers
├── shared/
│   ├── dto/response.py          # APIResponse[T] / PaginatedResponse[T] genéricos
│   ├── exceptions/base.py       # jerarquía de excepciones de dominio -> status HTTP
│   └── utils/
│       ├── validators.py        # PyObjectId (validación de ObjectId en modelos Pydantic)
│       └── rate_limit.py        # dependencia rate_limiter(scope, limit, window) sobre Redis
└── features/
    ├── auth/
    │   ├── application/
    │   │   ├── dto.py                   # LoginRequestDTO, TokenResponseDTO, CurrentUserDTO
    │   │   └── services.py              # AuthService: login, refresh, create/decode de JWT
    │   └── presentation/
    │       ├── dependencies.py          # get_current_user, require_roles(*roles)
    │       └── routes/auth_routes.py    # POST /login, POST /refresh, GET /me
    ├── documents/
    │   ├── domain/models.py             # Document + DocumentStatus (pending/completed/failed)
    │   ├── application/
    │   │   ├── dto.py                   # DocumentResponseDTO, DocumentSummaryDTO, CursorPage[T]
    │   │   └── services.py              # DocumentService: upload, list, apply_ocr_result
    │   ├── infrastructure/
    │   │   ├── repositories/document_repository.py   # paginación por cursor
    │   │   ├── storage.py               # MinIOStorage (timeouts acotados)
    │   │   └── queue.py                 # OCRJobPublisher + OCRResultConsumer (aio-pika)
    │   └── presentation/routes/document_routes.py    # POST/GET /api/v1/documents
    └── organizations/
        ├── domain/models.py             # entidades de persistencia (Organization, User)
        ├── application/
        │   ├── dto.py                   # contratos de entrada/salida de la API
        │   └── services.py              # reglas de negocio, orquesta el repositorio
        ├── infrastructure/repositories/
        │   ├── base_repository.py       # CRUD genérico sobre Motor
        │   └── organization_repository.py
        └── presentation/routes/
            └── organization_routes.py   # endpoints /api/v1/organizations

tests/
├── conftest.py       # AsyncClient + mongomock-motor + fakes de MinIO/RabbitMQ (sin infra real)
├── test_health.py
├── test_organizations.py
├── test_auth.py
└── test_documents.py
```

Separación por capas (domain / application / infrastructure / presentation) para que las reglas de negocio en `services.py` no dependan de Motor ni de FastAPI directamente — se pueden testear o reemplazar de forma aislada.

## Por qué "users" es una colección separada

`User` referencia a su organización con `organization_id` en vez de vivir embebido en un array dentro de `Organization`. Con documentos embebidos, una organización con miles de usuarios crecería sin límite hasta el tope de 16MB por documento de MongoDB, y cualquier operación sobre la organización cargaría todos sus usuarios en memoria aunque no se necesiten. Con colecciones separadas + índice en `organization_id`, listar o contar usuarios es una query independiente y paginada.

## Decisiones de performance / memoria

- **Connection pooling real**: `MongoDB` (`app/core/config/database/mongo.py`) es un singleton creado una sola vez en el `lifespan`, con `minPoolSize`/`maxPoolSize`/`maxIdleTimeMS` configurables por entorno (`app/core/config/settings.py`). Evita abrir una conexión TCP nueva por request.
- **Paginación acotada**: todos los endpoints de listado (`GET /organizations`, `GET /organizations/{id}/users`) exigen `page_size` con `le=100`. Nunca se hace `find().to_list(None)` — el cursor de Motor siempre lleva `skip`/`limit`/`batch_size` (`base_repository.py`), así que el tamaño de una respuesta nunca es proporcional al tamaño de la colección.
- **Proyecciones en Mongo**: `list_users` excluye `password_hash` a nivel de query (`USER_LIST_PROJECTION = {"password_hash": 0}`) en vez de traer el campo y descartarlo en Python — menos bytes viajando por la red y menos memoria retenida en el proceso.
- **`password_hash` con `exclude=True`**: en el modelo `User`, el campo está marcado para no serializarse nunca, como segunda barrera además del DTO de respuesta (`UserResponseDTO`) que ya no lo incluye.
- **Índices creados una vez al arrancar**: `OrganizationRepository.ensure_indexes()` corre en el `lifespan`, no en cada request. Los índices únicos (`organizations.email`, `organizations.name`, `users.email`) hacen que las validaciones de duplicados sean lookups por índice (O(log n)) en vez de escaneos de colección.
- **Verificación de límites sin cargar datos**: `add_user` valida el máximo de usuarios con `count_documents` (cuenta en el servidor de Mongo), nunca trayendo la lista completa a Python para hacer `len()`.
- **Serialización rápida**: con FastAPI reciente (0.115+), definir `response_model` en cada endpoint hace que la respuesta se serialice directo desde Pydantic-core a bytes JSON, sin pasar por `jsonable_encoder` + `json.dumps`. Por eso no se usa `ORJSONResponse`: sería una capa redundante y más lenta que el camino nativo cuando ya hay `response_model`.
- **Compresión de payloads**: `GZipMiddleware` con `minimum_size=1024` comprime únicamente respuestas que valen la pena (listados grandes, `/openapi.json`), sin gastar CPU en respuestas pequeñas.
- **`uvloop` + `httptools`**: incluidos vía `uvicorn[standard]`, dan un loop de eventos y parser HTTP más rápidos que los de la stdlib.
- **Hashing de contraseñas fuera del hot path de lectura**: Argon2 es deliberadamente costoso en CPU/memoria — se usa solo al crear un usuario, nunca en endpoints de lectura.
- **`.env` sin cargar dos veces**: cada sub-config (`MongoSettings`, `RedisSettings`, etc.) declara su propio `env_prefix` y lee el `.env` una vez vía `pydantic-settings`, evitando el patrón de `os.environ` global mutable disperso por el código.

## Testing sin infraestructura externa

`tests/conftest.py` monta la app con `httpx.AsyncClient` sobre `ASGITransport` (sin sockets reales) y sustituye la dependencia de Mongo por `mongomock-motor`. La suite completa corre en milisegundos y no requiere Docker ni una instancia de MongoDB — útil en CI y en desarrollo local.

## Autenticación (JWT)

`POST /api/v1/auth/login` valida email+contraseña (Argon2) y devuelve un par de tokens HS256: `access_token` (24h por defecto) y `refresh_token` (7 días). `POST /api/v1/auth/refresh` rota el par completo; `GET /api/v1/auth/me` devuelve el usuario del token. El payload lleva `sub` (user id), `org`, `roles` y `type` (`access`/`refresh`) — un refresh token no sirve como access token y viceversa.

`get_current_user` (en `app/features/auth/presentation/dependencies.py`) valida el Bearer token **y** recarga el usuario desde MongoDB, así un usuario desactivado pierde acceso de inmediato aunque su token siga vigente. `require_roles(UserRole.ADMIN, ...)` construye dependencias de autorización por rol. Los endpoints de documents ya están protegidos; los de organizations quedaron públicos a propósito (bootstrap: crear la primera organización y usuario) — protegerlos es agregar `Depends(get_current_user)` al router.

El login tiene **rate limiting** (10 intentos/minuto por IP) usando Redis con `INCR` + `EXPIRE`. Si Redis está caído, el limitador es *fail-open*: loguea el problema y deja pasar, para que la disponibilidad del login no dependa de Redis.

## Documentos + integración con el OCR

Flujo completo: `POST /api/v1/documents` (multipart, requiere Bearer token) → valida MIME (`pdf/png/jpeg/tiff`) y tamaño (`MAX_UPLOAD_MB`, leído en chunks de 1MB con corte temprano) → sube a MinIO (`documents/{org_id}/{uuid}/{nombre}`) → inserta el documento con `status: pending` → publica `{"job_id": <doc_id>, "file_path": ...}` en `ocr_jobs`.

En el `lifespan` corre `OCRResultConsumer` (aio-pika, tarea asyncio con reconexión automática) que escucha `ocr_results`: cuando el servicio OCR termina, descarga el JSON de resultado desde MinIO y persiste en MongoDB el texto extraído, confianza, páginas y hash (`status: completed`), o marca `status: failed` con el error. `GET /api/v1/documents/{id}` devuelve el documento con su `ocr_text`.

Si MinIO o RabbitMQ están caídos al subir, el endpoint responde `503` con mensaje claro (y el documento queda marcado `failed` si ya se había insertado) — nunca queda un archivo huérfano "pending" para siempre por un error de infraestructura visible en el request.

## Paginación por cursor (documents)

`GET /api/v1/documents?limit=20&cursor=<id>` pagina por `_id` descendente con `{"_id": {"$lt": cursor}}` en lugar de `skip`: el costo de obtener la página N es constante (seek por índice), mientras que `skip` recorre y descarta N×limit documentos. Se pide `limit+1` para saber si hay página siguiente sin un `count` extra, y la respuesta incluye `next_cursor` listo para la siguiente llamada. El índice compuesto `(organization_id, _id desc)` cubre exactamente esta query. El listado además excluye `ocr_text` por proyección — el texto completo (que puede ser cientos de KB por documento) solo viaja en el GET individual.

## Manejo de errores

`app/shared/exceptions/base.py` define `AppException` y subclases (`NotFoundError`, `ConflictError`, `ValidationError`, ...) con su propio `status_code`. Un único `exception_handler` en `main.py` las traduce a JSON consistente (`{"success": false, "error_code": ..., "message": ...}`), así que los servicios lanzan excepciones de dominio sin conocer HTTP.

## Variables de entorno

Ver [.env.example](.env.example). `JWT_SECRET` es obligatorio y debe tener al menos 32 caracteres (validado en `SecuritySettings`); la app no arranca sin él.

## Servicio OCR (`ocr-service/`)

Worker independiente que consume trabajos de OCR desde RabbitMQ, procesa documentos (imágenes y PDFs) con Tesseract y publica los resultados.

```
ocr-service/
├── src/
│   ├── main.py                  # FastAPI (health) + lifespan que arranca el consumer
│   ├── core/config.py           # pydantic-settings (RabbitMQ, MinIO, Redis, OCR)
│   ├── services/
│   │   ├── ocr.py               # OCREngine: Tesseract + preprocesado OpenCV
│   │   ├── processor.py         # DocumentProcessor: descarga → hash → cache → OCR → subida
│   │   └── consumer.py          # RabbitMQConsumer: cola ocr_jobs → ocr_results
│   └── clients/
│       ├── minio.py             # descarga/subida de archivos
│       └── redis.py             # cache async de resultados por hash
├── tests/test_processor.py
├── Dockerfile                   # python:3.12-slim + tesseract-ocr(-spa/-eng) + poppler-utils
├── requirements.txt
└── .env.example
```

**Flujo de un trabajo**: mensaje JSON `{"job_id", "file_path", "output_path"?}` en la cola `ocr_jobs` → descarga el archivo de MinIO → calcula SHA-256 → si el hash está en Redis devuelve el resultado cacheado (sin re-OCR) → si no, corre Tesseract (detecta PDF por magic bytes `%PDF`) → guarda en cache con TTL → sube el JSON de resultado a MinIO (`ocr-results/{hash}.json`) → publica `{"job_id", "status", "result_path", "pages", "confidence"}` en `ocr_results` → ack. Si falla, reintenta 3 veces con backoff exponencial y luego publica `status: failed` + nack sin requeue.

**Decisiones de performance/memoria del OCR**:
- **PDFs página por página**: `pdfinfo_from_bytes` obtiene el total y luego `convert_from_bytes(first_page=n, last_page=n, grayscale=True)` rasteriza una sola página a la vez en escala de grises — la memoria queda acotada al tamaño de una página, no del documento completo.
- **Cache por hash de contenido**: dos trabajos sobre el mismo archivo (o el mismo archivo re-subido) no repiten el OCR — Tesseract es la parte cara. El cache degrada con gracia: si Redis está caído, se loguea un warning y el OCR sigue funcionando.
- **Una sola pasada de Tesseract**: `image_to_data` da texto y confianza a la vez (reconstruyendo líneas por `block/par/line_num`) en lugar de llamar a `image_to_string` + `image_to_data` (dos pasadas de OCR).
- **`opencv-python-headless`**: sin dependencias de GUI — imagen Docker más chica.
- **`prefetch_count=1`**: el worker no acumula mensajes sin procesar; con OCR de minutos por documento, esto permite escalar horizontalmente agregando réplicas del contenedor.
- **Timeouts acotados en MinIO**: el cliente usa `connect=5s` y 2 reintentos — con MinIO caído el servicio arranca igual en ~2s en vez de colgarse.
- **Resiliencia**: el consumer corre en un thread propio con reconexión automática cada 5s; la app HTTP (health check) nunca se cae por infraestructura caída, y `/health` expone `consumer_running` para monitorear.

Para probarlo completo: `docker compose up` (levanta `ocr` junto con RabbitMQ/MinIO/Redis) y publicar un mensaje en `ocr_jobs`.

## Próximos pasos sugeridos

- Proteger los endpoints de organizations con `get_current_user` + `require_roles(UserRole.ADMIN)` una vez definido el flujo de bootstrap (registro inicial / seeding).
- Blacklist de refresh tokens en Redis (logout real) — hoy un refresh token robado vale hasta su expiración.
- Webhooks o WebSocket para notificar al cliente cuando un documento pasa a `completed`, en vez de polling sobre `GET /documents/{id}`.
- Migrar organizations a paginación por cursor si esa colección también crece (documents ya la usa).
