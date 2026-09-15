from sqlalchemy import Float, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class FeedbackCandidate(Base):
    """분석 당시 Top-K 후보 snapshot. feedback_id 확정 이후에도 수정하지 않는다.

    Composite primary key (feedback_id, rank) -- no surrogate id column --
    matching the already-deployed production schema (섹션 "라이브 DB 스키마
    정합성" 참고). The Python attribute stays named ``rank`` for readability
    everywhere it's used (analyze.py, tests); only the physical column name
    is ``candidate_rank`` on the actual table.
    """

    __tablename__ = "feedback_candidates"

    feedback_id: Mapped[int] = mapped_column(
        ForeignKey("feedback.feedback_id"), primary_key=True
    )
    rank: Mapped[int] = mapped_column("candidate_rank", SmallInteger, primary_key=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("waste_classes.class_id"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
