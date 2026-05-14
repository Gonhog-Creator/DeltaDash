from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    UPLOAD_DIR: str = "/app/storage/uploads"
    MATERIAL_DOCS_DIR: str = "/app/storage/material_docs"
    REPORTS_DIR: str = "/app/storage/reports"
    MODEL_ARTIFACTS_DIR: str = "/app/storage/model_artifacts"
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
