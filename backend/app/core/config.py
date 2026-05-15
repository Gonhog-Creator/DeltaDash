from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:5173"
    
    # Storage configuration
    USE_RAILWAY_STORAGE: bool = False  # Set to True to use Railway storage
    RAILWAY_VOLUME_URL: str = ""  # Optional: URL for Railway volume access
    
    # Local storage paths (fallback)
    LOCAL_UPLOAD_DIR: str = "storage/uploads"
    LOCAL_MATERIAL_DOCS_DIR: str = "storage/material_docs"
    LOCAL_REPORTS_DIR: str = "storage/reports"
    LOCAL_MODEL_ARTIFACTS_DIR: str = "storage/model_artifacts"
    
    # Production storage paths (Railway)
    UPLOAD_DIR: str = "/app/storage/uploads"
    MATERIAL_DOCS_DIR: str = "/app/storage/material_docs"
    REPORTS_DIR: str = "/app/storage/reports"
    MODEL_ARTIFACTS_DIR: str = "/app/storage/model_artifacts"
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def upload_dir(self) -> str:
        """Get the appropriate uploads directory based on environment"""
        if self.USE_RAILWAY_STORAGE and os.path.exists(self.UPLOAD_DIR):
            return self.UPLOAD_DIR
        # Ensure local directory exists
        os.makedirs(self.LOCAL_UPLOAD_DIR, exist_ok=True)
        return self.LOCAL_UPLOAD_DIR
    
    @property
    def material_docs_dir(self) -> str:
        """Get the appropriate material docs directory based on environment"""
        if self.USE_RAILWAY_STORAGE and os.path.exists(self.MATERIAL_DOCS_DIR):
            return self.MATERIAL_DOCS_DIR
        # Ensure local directory exists
        os.makedirs(self.LOCAL_MATERIAL_DOCS_DIR, exist_ok=True)
        return self.LOCAL_MATERIAL_DOCS_DIR
    
    @property
    def reports_dir(self) -> str:
        """Get the appropriate reports directory based on environment"""
        if self.USE_RAILWAY_STORAGE and os.path.exists(self.REPORTS_DIR):
            return self.REPORTS_DIR
        # Ensure local directory exists
        os.makedirs(self.LOCAL_REPORTS_DIR, exist_ok=True)
        return self.LOCAL_REPORTS_DIR
    
    @property
    def model_artifacts_dir(self) -> str:
        """Get the appropriate model artifacts directory based on environment"""
        if self.USE_RAILWAY_STORAGE and os.path.exists(self.MODEL_ARTIFACTS_DIR):
            return self.MODEL_ARTIFACTS_DIR
        # Ensure local directory exists
        os.makedirs(self.LOCAL_MODEL_ARTIFACTS_DIR, exist_ok=True)
        return self.LOCAL_MODEL_ARTIFACTS_DIR

    class Config:
        env_file = ".env"


settings = Settings()
