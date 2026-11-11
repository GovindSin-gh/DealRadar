import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./dealradar.db")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")
    model_path: str = os.getenv("MODEL_PATH", str(Path(__file__).resolve().parents[1] / "models" / "champion" / "model.joblib"))
    live_scraping: bool = os.getenv("LIVE_SCRAPING", "false").lower() == "true"
    rate_limit_per_hour: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "5"))
    watch_limit_per_hour: int = int(os.getenv("WATCH_LIMIT_PER_HOUR", "10"))
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    mail_from: str = os.getenv("MAIL_FROM", "")
    public_api_url: str = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    admin_token: str = os.getenv("ADMIN_TOKEN", "")
    daily_delay_seconds: float = float(os.getenv("DAILY_DELAY_SECONDS", "3"))
    llm_extract_fallback: bool = os.getenv("LLM_EXTRACT_FALLBACK", "true").lower() == "true"
    cache_hours: int = int(os.getenv("CACHE_HOURS", "24"))
    cors_origins: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]

    def __init__(self):
        # Some providers hand out "postgres://", SQLAlchemy wants "postgresql://".
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)


settings = Settings()
