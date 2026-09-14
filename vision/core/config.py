"""Vision Server settings loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class VisionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / "vision" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8100

    # Point this at your fine-tuned recycling checkpoint, e.g. a copy of
    # ai/models/yolo/01_experiment_augmentation/runs/<winning_run>/weights/best.pt.
    # Intentionally does NOT default to the untrained COCO weights/yolo26n.pt --
    # that would silently return COCO class indices instead of the 86-class
    # recycling taxonomy and corrupt every downstream class_id.
    model_path: str = "weights/best.pt"
    model_version: str = "yolo-recycling-v1"

    # Detection tuning. VISION_NO_MAIN_OBJECT is raised only when literally
    # nothing is detected even at this low floor -- the *business* confidence
    # gate (0.5) is applied by the Backend, not here (spec 섹션 1/8.1/13.1).
    low_confidence_floor: float = 0.05
    nms_iou: float = 0.45
    max_detections: int = 100
    candidate_iou_match: float = 0.5
    top_k: int = 5

    taxonomy_data_dir: str | None = None

    max_image_size_mb: int = 10
    allowed_image_content_types: str = "image/jpeg,image/jpg,image/png,image/webp"

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024

    @property
    def allowed_image_content_type_set(self) -> set[str]:
        return {c.strip().lower() for c in self.allowed_image_content_types.split(",") if c.strip()}

    @property
    def resolved_model_path(self) -> Path:
        p = Path(self.model_path)
        return p if p.is_absolute() else REPO_ROOT / p

    @property
    def resolved_taxonomy_dir(self) -> Path:
        if self.taxonomy_data_dir:
            return Path(self.taxonomy_data_dir)
        return REPO_ROOT / "data" / "taxonomy"


@lru_cache
def get_settings() -> VisionSettings:
    return VisionSettings()


settings = get_settings()
