from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import Base after creating engine to avoid circular imports
from app.db.base import Base


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
