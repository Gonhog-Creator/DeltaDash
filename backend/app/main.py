from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os
# reload trigger

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.db.models.user import User
from app.api.v1 import auth, materials, ammunition, test_sessions, panels, shots, shot_patterns, analytics, locations, protocols, shot_data, vests, admin, ballistic, anchor_points, geometries, fabric_estimation, geometry_material_configs, covers

setup_logging()

app = FastAPI(
    title="Ballistic Test Analytics Platform",
    version="1.0.4",
    max_request_size=50 * 1024 * 1024  # 50MB max request size
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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
app.include_router(vests.router, prefix="/api/v1/vests", tags=["vests"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(ballistic.router, prefix="/api/v1", tags=["ballistic"])
app.include_router(anchor_points.router, prefix="/api/v1", tags=["anchor-points"])
app.include_router(geometries.router, prefix="/api/v1/geometries", tags=["geometries"])
app.include_router(fabric_estimation.router, prefix="/api/v1/fabric-estimation", tags=["fabric-estimation"])
app.include_router(geometry_material_configs.router, prefix="/api/v1/geometry-material-configs", tags=["geometry-material-configs"])
app.include_router(covers.router, prefix="/api/v1/covers", tags=["covers"])


@app.on_event("startup")
def seed_dev_users():
    if settings.APP_ENV != "development":
        return
    db = SessionLocal()
    try:
        dev_users = [
            ("admin", "Administrator", "admin", True),
            ("viewer", "Viewer", "viewer", False),
        ]
        for username, full_name, role, is_admin in dev_users:
            existing = db.query(User).filter(User.username == username).first()
            if not existing:
                user = User(
                    username=username,
                    full_name=full_name,
                    hashed_password=get_password_hash(username),
                    role=role,
                    is_active=True,
                    is_admin=is_admin,
                )
                db.add(user)
                db.commit()
                print(f"Seeded dev user: {username}")
    except Exception as e:
        print(f"Dev user seeding skipped: {e}")
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/")
def root():
    return {"message": "Ballistic Test Analytics Platform API", "status": "operational"}

