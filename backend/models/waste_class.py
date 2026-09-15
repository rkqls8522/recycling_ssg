from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class WasteClass(Base):
    """Vision AI(YOLO)와 서비스가 공유하는 폐기물 taxonomy. class_id는 YOLO의
    class index와 동일하게 유지한다 (data.yaml 기준)."""

    __tablename__ = "waste_classes"

    class_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    major_category: Mapped[str] = mapped_column(String(100), nullable=False)
    minor_category: Mapped[str] = mapped_column(String(100), nullable=False)
