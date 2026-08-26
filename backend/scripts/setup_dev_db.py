"""Create all tables from SQLAlchemy models and seed an admin user if none exists."""
import os
import sys
import uuid
import bcrypt
import psycopg2
from dotenv import load_dotenv

# Add backend dir to path so 'app' is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return

    # Create tables from models
    from app.db.base import Base
    from app.db.session import engine
    import app.db.models  # noqa: F401 - register all models with Base

    Base.metadata.create_all(engine)
    print("Tables created/verified OK")

    # Seed admin user if none exists
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username = %s", ("admin",))
    if cur.fetchone():
        print("Admin user already exists")
    else:
        hashed = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (id, username, full_name, hashed_password, role, is_active, is_admin, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, true, true, NOW(), NOW())",
            (str(uuid.uuid4()), "admin", "Admin User", hashed, "admin"),
        )
        conn.commit()
        print("Admin user created (username: admin, password: admin)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
