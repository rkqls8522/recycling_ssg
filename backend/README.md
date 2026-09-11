# recycling_ssg Backend

FastAPI backend implementing the 17 Backend endpoints from
`recycling_ssg_API_상세명세서_v6.0.pdf` (health/ready, auth, users, regions,
analyze, feedback, disposal, chat, favorites). It talks to a separate
Vision service (see `../vision/`) for YOLO inference.

## Setup

```bash
cd backend
uv sync
cp .env.example .env   # then fill in DATABASE_URL, JWT_SECRET_KEY, AWS_*, etc.
```

Create the MySQL database referenced by `DATABASE_URL` first (the app only
creates tables inside it, not the database itself):

```sql
CREATE DATABASE recycling_ssg CHARACTER SET utf8mb4;
```

## Run

```bash
uv run uvicorn main:app --reload --port 8000
```

On startup the app (when `AUTO_CREATE_TABLES=true`) creates all tables via
SQLAlchemy `create_all()` and (when `AUTO_SEED_MASTER_DATA=true`) seeds the
`regions` (56 rows) and `waste_classes` (86 rows) Master tables from
`../data/taxonomy/*.json` — the same files the Vision service uses, so
`class_id` always means the same thing on both sides.

For a production setup, replace `AUTO_CREATE_TABLES` with a real migration
tool (e.g. Alembic) before going live.

## Layout

```
backend/
  main.py            FastAPI app wiring: middleware, routers, startup hooks
  core/
    config.py        Settings (env vars)
    database.py      SQLAlchemy engine/session/Base
    security.py      bcrypt password hashing + JWT
    deps.py           get_current_user dependency
    middleware.py      X-Request-ID middleware
    exceptions.py       AppError + ErrorResponse exception handlers
    paths.py            filesystem path helpers
  models/            SQLAlchemy ORM models (users/regions/waste_classes/...)
  schemas/           Pydantic request/response schemas
  services/
    s3_service.py            S3 upload/download/compensating delete
    vision_client.py         HTTP client for the internal Vision service
    public_waste_client.py   행정안전부 생활쓰레기배출정보 API client
    disposal_service.py      region+class -> disposal info orchestration
    gemini_service.py        Gemini Vision Fallback + chat text generation
    image_validation.py      multipart image validation
  agent/             Stateless AI Agent used by POST /api/v1/chat
  api/               One router module per resource
  db/
    seed.py              idempotent regions/waste_classes seeding
    taxonomy_loader.py   loads ../data/taxonomy/*.json
  tests/
```

## Notes on external integrations

- **JWT**: `core/security.py` issues HS256 tokens (`JWT_SECRET_KEY`,
  `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`). Logout is stateless — the client just
  discards the token; the server only validates it.
- **행정안전부 API key decoding**: `services/public_waste_client.py` always
  `urllib.parse.unquote()`s the configured service key before handing it to
  httpx, because data.go.kr keys are often copy-pasted in their
  URL-encoded form and httpx would otherwise double-encode them. The exact
  response field names (`_FIELD_CANDIDATES`) are best-guess based on the
  UDDI 표준데이터 convention — verify against a live response and adjust once
  you have a real service key.
- **S3**: only `images.s3_key` is ever persisted (never a presigned URL).
  If the DB transaction after upload fails, `s3_service.delete_object` is
  called as a compensating action (섹션 19).
- **Gemini**: used for (1) the `not-in-list` Vision Fallback, restricted to
  the service's own `waste_classes` taxonomy, and (2) free-text answers in
  the stateless chat agent. If `GEMINI_API_KEY` is unset, the vision
  fallback endpoint returns `503 GEMINI_NOT_CONFIGURED` per spec, while the
  chat endpoint instead degrades to a deterministic templated answer so the
  feature keeps working without a key.
