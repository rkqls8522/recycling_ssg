from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Image(Base):
    """AWS S3 이미지 Object Key 저장.

    Note: no ``user_id``/``created_at`` here -- matching the already-deployed
    production schema (섹션 "라이브 DB 스키마 정합성" 참고). Ownership is
    tracked on ``feedback.user_id`` instead (every image is created together
    with exactly one feedback row in the /analyze flow, so it is never
    orphaned/ownerless), which is also all the spec's own DB field table
    (섹션 18) requires of ``images``.
    """

    __tablename__ = "images"

    image_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    # The MIME type actually stored at s3_key (services.image_processing may
    # re-encode the original upload, e.g. PNG -> JPEG), needed to tell
    # Gemini the right mime_type when re-reading it in feedback.not_in_list.
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, default="image/jpeg")
