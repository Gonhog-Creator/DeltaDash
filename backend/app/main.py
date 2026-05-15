from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1 import auth, materials, ammunition, test_sessions, panels, shots, shot_patterns, analytics, locations, protocols, shot_data

setup_logging()

app = FastAPI(title="Ballistic Test Analytics Platform", version="0.1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(materials.router, prefix="/api/v1/materials", tags=["materials"])
app.include_router(ammunition.router, prefix="/api/v1/ammunition", tags=["ammunition"])
app.include_router(test_sessions.router, prefix="/api/v1/test-sessions", tags=["test-sessions"])
app.include_router(panels.router, prefix="/api/v1/panels", tags=["panels"])
app.include_router(shots.router, prefix="/api/v1/shots", tags=["shots"])
app.include_router(shot_patterns.router, prefix="/api/v1/shot-patterns", tags=["shot-patterns"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(locations.router, prefix="/api/v1/locations", tags=["locations"])
app.include_router(protocols.router, prefix="/api/v1/protocols", tags=["protocols"])
app.include_router(shot_data.router, prefix="/api/v1/shot-data", tags=["shot-data"])


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/")
def root():
    return {"message": "Ballistic Test Analytics Platform API", "status": "🚀 Ready for Development", "optimized": True}
