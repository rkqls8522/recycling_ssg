from __future__ import annotations

from pydantic import BaseModel, Field

from core.config import settings


class ChatRequest(BaseModel):
    feedback_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=settings.chat_message_max_length)


class ChatResponse(BaseModel):
    feedback_id: int
    answer: str
    warnings: list[str] = []
