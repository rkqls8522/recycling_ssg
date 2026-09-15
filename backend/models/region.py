from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Region(Base):
    """서울특별시 25개 자치구 + 경기도 31개 시·군, 총 56개 고정 Master."""

    __tablename__ = "regions"

    region_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    sido_name: Mapped[str] = mapped_column(String(50), nullable=False)
    sgg_name: Mapped[str] = mapped_column(String(50), nullable=False)
