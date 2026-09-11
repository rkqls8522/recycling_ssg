"""Application settings loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "recycling_ssg backend"
    app_version: str = "1.0.0"
    environment: str = "development"
    cors_allow_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Database (MySQL) ---
    database_url: str = (
        "mysql+pymysql://root:password@localhost:3306/recycling_ssg?charset=utf8mb4"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10
    auto_create_tables: bool = True
    auto_seed_master_data: bool = True

    # --- JWT ---
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24

    # --- AWS S3 ---
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "ap-northeast-2"
    aws_s3_bucket: str = "recycling-ssg-images"
    aws_s3_endpoint_url: str | None = None  # for local/minio testing
    s3_request_timeout_seconds: float = 10.0

    # --- Image upload constraints ---
    max_image_size_mb: int = 10
    allowed_image_content_types: str = "image/jpeg,image/jpg,image/png,image/webp"

    # --- Vision Server (internal) ---
    vision_server_base_url: str = "http://localhost:8100/internal/v1"
    vision_request_timeout_seconds: float = 15.0
    vision_confidence_threshold: float = 0.5
    vision_top_k: int = 5

    # --- 행정안전부 생활쓰레기배출정보 API ---
    public_waste_api_base_url: str = (
        "https://apis.data.go.kr/1741000/household_waste_info/info"
    )
    public_waste_api_service_key: str | None = None
    public_waste_api_timeout_seconds: float = 8.0

    # --- Gemini ---
    gemini_api_key: str | None = None
    gemini_model_name: str = "gemini-2.5-flash"
    gemini_vision_timeout_seconds: float = 20.0
    gemini_chat_timeout_seconds: float = 20.0

    # --- AI Agent / Chat ---
    chat_message_max_length: int = 1000

    # --- Shared taxonomy data (regions.json / waste_classes.json) ---
    # Defaults to <repo_root>/data/taxonomy, resolved relative to this file
    # at runtime (see core/paths.py). Override for non-standard deployments.
    taxonomy_data_dir: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def allowed_image_content_type_set(self) -> set[str]:
        return {
            c.strip().lower()
            for c in self.allowed_image_content_types.split(",")
            if c.strip()
        }

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
