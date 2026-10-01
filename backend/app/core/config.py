import os
from pathlib import Path
from pydantic import BaseModel, Field

class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "development")
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:3000")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./recruitradar.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    llm_provider: str = os.getenv("LLM_PROVIDER", "fake")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model_strong: str = os.getenv("LLM_MODEL_STRONG", "fake-strong")
    llm_model_fast: str = os.getenv("LLM_MODEL_FAST", "fake-fast")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "fake-embed")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "1024"))
    
    storage_endpoint: str = os.getenv("STORAGE_ENDPOINT", "http://localhost:9000")
    storage_bucket_clean: str = os.getenv("STORAGE_BUCKET_CLEAN", "clean")
    storage_bucket_quarantine: str = os.getenv("STORAGE_BUCKET_QUARANTINE", "quarantine")
    storage_access_key: str = os.getenv("STORAGE_ACCESS_KEY", "minioadmin")
    storage_secret_key: str = os.getenv("STORAGE_SECRET_KEY", "minioadmin")
    local_storage_path: str = os.getenv("LOCAL_STORAGE_PATH", "./storage_data")
    
    pii_encryption_key: str = os.getenv("PII_ENCRYPTION_KEY", "dev_secret_key_32_bytes_len_1234567890")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev_jwt_secret_recruit_radar_mvp_2026")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    
    av_scan_endpoint: str = os.getenv("AV_SCAN_ENDPOINT", "")
    rate_limit_default_rpm: int = int(os.getenv("RATE_LIMIT_DEFAULT_RPM", "120"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    max_files_per_batch: int = int(os.getenv("MAX_FILES_PER_BATCH", "500"))
    
    run_max_usd: float = float(os.getenv("RUN_MAX_USD", "10.0"))
    run_max_steps: int = int(os.getenv("RUN_MAX_STEPS", "1000"))
    run_max_minutes: int = int(os.getenv("RUN_MAX_MINUTES", "30"))
    default_retention_days: int = int(os.getenv("DEFAULT_RETENTION_DAYS", "180"))
    default_timezone: str = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")
    
    scoring_config_version: str = "2.0.0"

settings = Settings()
