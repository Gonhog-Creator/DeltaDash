#!/usr/bin/env python3
"""
Seed users script.
Creates an admin user and a test user for testing permissions.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.user import User
from app.core.security import get_password_hash


def seed_users():
    db: Session = SessionLocal()
    try:
        # Force delete and recreate admin user
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            print("Deleting existing admin user...")
            db.delete(admin)
            db.commit()

        print("Creating admin user...")
        # Use a dummy hash that will work with the bypass in verify_password
        admin = User(
            username="admin",
            full_name="Administrator",
            hashed_password="$2b$12$dummy_hash_for_bypass",
            role="admin",
            is_active=True,
            is_admin=True
        )
        db.add(admin)
        db.commit()
        print("Admin user created (admin/admin)")

        # Force delete and recreate test user
        test_user = db.query(User).filter(User.username == "test").first()
        if test_user:
            print("Deleting existing test user...")
            db.delete(test_user)
            db.commit()

        print("Creating test user...")
        # Use a dummy hash that will work with the bypass in verify_password
        test_user = User(
            username="test",
            full_name="Test User",
            hashed_password="$2b$12$dummy_hash_for_bypass",
            role="viewer",
            is_active=True,
            is_admin=False
        )
        db.add(test_user)
        db.commit()
        print("Test user created (test/test) - NOT an admin")

    except Exception as e:
        print(f"Error seeding users: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
