from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite+aiosqlite:///./switchops.db'
    redis_url: str = 'redis://localhost:6379/0'
    app_secret_key: str = ''
    app_encryption_key: str = ''
    environment: str = 'development'
    frontend_url: str = 'http://localhost:3000'
    backend_url: str = 'http://localhost:8000'
    switch_server_url: str = ''
    switch_registration_key: str = ''
    model_provider: str = 'ollama'
    model_base_url: str = 'http://localhost:11434'
    model_name: str = 'qwen3:8b'
    model_api_key: str = ''
    smtp_host: str = ''
    smtp_port: int = 1025
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_from_email: str = 'switchops@example.test'
    smtp_sandbox: bool = True
    smtp_starttls: bool = False
    minio_endpoint: str = ''
    minio_access_key: str = ''
    minio_secret_key: str = ''
    minio_bucket: str = 'switchops-private'
    google_client_id: str = ''
    google_client_secret: str = ''
    google_redirect_uri: str = 'http://localhost:8000/api/v1/integrations/google/callback'
    max_handoffs: int = 16
    max_model_calls: int = 16
    handoff_timeout_seconds: int = 900
    session_hours: int = 12
    upload_max_bytes: int = 10 * 1024 * 1024
    embeddings_enabled: bool = False
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'


@lru_cache
def settings() -> Settings:
    return Settings()
