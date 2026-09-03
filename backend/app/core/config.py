from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str
    REMOTE_DATABASE_URL: str = ""
    PRODUCTION_BACKEND_URL: str = "https://deltadash-backend-production.up.railway.app"
    PRODUCTION_API_TOKEN: str = ""
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8000,https://deltadash-production.up.railway.app"
    VERSION: str = "1.1.0"
    
    # Storage configuration
    USE_RAILWAY_STORAGE: bool = False  # Set to True to use Railway storage
    RAILWAY_VOLUME_URL: str = ""  # Optional: URL for Railway volume access
    
    # Local storage paths (fallback)
    LOCAL_UPLOAD_DIR: str = "storage/uploads"
    LOCAL_MATERIAL_DOCS_DIR: str = "storage/material_docs"
    LOCAL_GEOMETRY_DOCS_DIR: str = "storage/geometry_docs"
    LOCAL_GEOMETRY_IMAGES_DIR: str = "storage/geometry_images"
    LOCAL_REPORTS_DIR: str = "storage/reports"
    LOCAL_MODEL_ARTIFACTS_DIR: str = "storage/model_artifacts"
    LOCAL_MODEL_DOCS_DIR: str = "storage/model_docs"
    
    # Production storage paths (Railway)
    UPLOAD_DIR: str = "/app/storage/uploads"
    MATERIAL_DOCS_DIR: str = "/app/storage/material_docs"
    GEOMETRY_DOCS_DIR: str = "/app/storage/geometry_docs"
    GEOMETRY_IMAGES_DIR: str = "/app/storage/geometry_images"
    REPORTS_DIR: str = "/app/storage/reports"
    MODEL_ARTIFACTS_DIR: str = "/app/storage/model_artifacts"
    MODEL_DOCS_DIR: str = "/app/storage/model_docs"
    
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
    def geometry_docs_dir(self) -> str:
        """Get the appropriate geometry docs directory based on environment"""
        if self.USE_RAILWAY_STORAGE and os.path.exists(self.GEOMETRY_DOCS_DIR):
            return self.GEOMETRY_DOCS_DIR
        # Ensure local directory exists
        os.makedirs(self.LOCAL_GEOMETRY_DOCS_DIR, exist_ok=True)
        return self.LOCAL_GEOMETRY_DOCS_DIR
    
    @property
    def geometry_images_dir(self) -> str:
        """Get the appropriate geometry images directory based on environment"""
        if self.USE_RAILWAY_STORAGE and os.path.exists(self.GEOMETRY_IMAGES_DIR):
            return self.GEOMETRY_IMAGES_DIR
        # Ensure local directory exists
        os.makedirs(self.LOCAL_GEOMETRY_IMAGES_DIR, exist_ok=True)
        return self.LOCAL_GEOMETRY_IMAGES_DIR
    
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

    @property
    def model_docs_dir(self) -> str:
        """Get the appropriate model docs directory based on environment"""
        if self.USE_RAILWAY_STORAGE and os.path.exists(self.MODEL_DOCS_DIR):
            return self.MODEL_DOCS_DIR
        os.makedirs(self.LOCAL_MODEL_DOCS_DIR, exist_ok=True)
        return self.LOCAL_MODEL_DOCS_DIR

    class Config:
        env_file = ".env"


settings = Settings()
