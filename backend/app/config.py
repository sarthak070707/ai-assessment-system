import os
from functools import lru_cache


class Settings:
    """Runtime configuration, read from environment with sensible local defaults."""

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./assessment.db")
        self.jwt_secret = os.getenv("JWT_SECRET", "dev-only-secret-replace-me-with-32-plus-random-bytes")
        self.jwt_algorithm = "HS256"
        self.jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        # Scores inside this band are too uncertain to auto-award; a human decides.
        self.review_lower = float(os.getenv("REVIEW_LOWER", "0.35"))
        self.review_upper = float(os.getenv("REVIEW_UPPER", "0.65"))

        self.code_timeout_seconds = int(os.getenv("CODE_TIMEOUT_SECONDS", "5"))
        self.code_memory_mb = int(os.getenv("CODE_MEMORY_MB", "256"))

        # Restricts candidate exam access to named networks, mirroring how an
        # institution confines a paper to lab machines. Blank means unrestricted,
        # which is the right default for local development and demos.
        raw = os.getenv("EXAM_ALLOWED_NETWORKS", "").strip()
        self.exam_allowed_networks = [n.strip() for n in raw.split(",") if n.strip()]
        self.access_code_hours = int(os.getenv("ACCESS_CODE_VALID_HOURS", "6"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
