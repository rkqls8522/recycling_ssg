"""Filesystem path helpers shared across the backend service."""

from __future__ import annotations

from pathlib import Path

from core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def taxonomy_data_dir() -> Path:
    if settings.taxonomy_data_dir:
        return Path(settings.taxonomy_data_dir)
    return REPO_ROOT / "data" / "taxonomy"
