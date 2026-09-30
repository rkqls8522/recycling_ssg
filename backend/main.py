"""recycling_ssg FastAPI backend entrypoint.

Wires together the request-id middleware, CORS, exception handlers, DB
table/master-data bootstrap and every /api/v1/* router (섹션 5 Endpoint 요약).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models  # noqa: F401 - populates Base.metadata before create_all()
from api import (
    analyze,
    auth,
    chat,
    disposal,
    favorites,
    feedback,
    health,
    regions,
    users,
)
from core.config import settings
from core.database import Base, SessionLocal, engine
from core.exceptions import register_exception_handlers
from core.logging_config import configure_logging
from core.middleware import RequestIDMiddleware
from db.seed import seed_all

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        logger.info("DB tables ensured via create_all()")

    if settings.auto_seed_master_data:
        db = SessionLocal()
        try:
            seed_all(db)
        finally:
            db.close()

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(regions.router)
app.include_router(analyze.router)
app.include_router(feedback.router)
app.include_router(disposal.router)
app.include_router(chat.router)
app.include_router(favorites.router)
