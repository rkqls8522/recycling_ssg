from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.timestamps import now_kst


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    image_id: Mapped[int] = mapped_column(
        ForeignKey("images.image_id"), nullable=False, unique=True
    )

    predicted_class_id: Mapped[int] = mapped_column(
        ForeignKey("waste_classes.class_id"), nullable=False
    )
    predicted_score: Mapped[float] = mapped_column(Float, nullable=False)

    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x2: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y2: Mapped[float] = mapped_column(Float, nullable=False)

    model_version: Mapped[str] = mapped_column(String(100), nullable=False)

    final_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("waste_classes.class_id"), nullable=True
    )
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # USER | GEMINI | NULL(미수정)
    correction_source: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_kst, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_kst, server_default=func.now(),
        onupdate=now_kst,
        nullable=False,
    )

    @property
    def is_completed(self) -> bool:
        return self.is_correct is not None
