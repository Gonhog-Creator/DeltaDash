#!/usr/bin/env python3
"""Fix missing columns in the users table."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine
import sqlalchemy as sa

with engine.connect() as conn:
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR NOT NULL DEFAULT 'viewer'"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"))
    conn.commit()
    print("Columns added successfully")

    insp = sa.inspect(conn)
    print("users columns:", [c["name"] for c in insp.get_columns("users")])
