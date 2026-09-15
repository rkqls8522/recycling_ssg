from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "backend"


class ReadyResponse(BaseModel):
    status: str
    database: bool
