import os
from functools import lru_cache
from pathlib import Path


def _load_env_file() -> None:
    """Read backend/.env into the process environment.

    os.getenv reads the *process* environment, which a .env file is not part of
    until something loads it. Without this the file is documentation rather than
    configuration - every setting silently falls back to its default, and the
    first setting with no default (GROQ_API_KEY) is the first to reveal it.

    Real environment variables win, so a value exported in the shell or set by a
    deployment platform is not overwritten by a stale local file.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass

    # Fallback parser, so a missing python-dotenv does not silently drop config.
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


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
