from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class FeedbackCandidate(Base):
    """분석 당시 Top-K 후보 snapshot. feedback_id 확정 이후에도 수정하지 않는다."""

    __tablename__ = "feedback_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    feedback_id: Mapped[int] = mapped_column(
        ForeignKey("feedback.feedback_id"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("waste_classes.class_id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
