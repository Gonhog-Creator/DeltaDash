#!/usr/bin/env python3
"""
Interactive user creation script.
Prompts for user details and creates a user in the database.
This script requires local execution and DATABASE_URL environment variable.
"""
import sys
import os
import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.user import User
from app.core.security import get_password_hash
from datetime import datetime, timezone


def create_user_interactive():
    # Security check: Only run if DATABASE_URL is set (prevents remote execution)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable is required")
        print("This script can only be run locally with proper database credentials")
        sys.exit(1)

    # Additional security: Check if running in Railway environment
    if "railway" in database_url.lower() and ".internal" in database_url:
        print("Error: This script cannot use Railway internal URLs")
        print("Use DATABASE_PUBLIC_URL for local execution")
        sys.exit(1)

    print("=== Interactive User Creation ===")
    print()

    # Get user input
    username = input("Enter username: ").strip()
    if not username:
        print("Error: Username is required")
        sys.exit(1)

    full_name = input("Enter full name: ").strip()
    if not full_name:
        print("Error: Full name is required")
        sys.exit(1)

    password = getpass.getpass("Enter password: ")
    if not password:
        print("Error: Password is required")
        sys.exit(1)

    confirm_password = getpass.getpass("Confirm password: ")
    if password != confirm_password:
        print("Error: Passwords do not match")
        sys.exit(1)

    role = input("Enter role (admin/viewer/editor): ").strip().lower()
    if role not in ["admin", "viewer", "editor"]:
        print("Error: Invalid role. Must be admin, viewer, or editor")
        sys.exit(1)

    is_admin = role == "admin"

    print()
    print("=== User Details ===")
    print(f"Username: {username}")
    print(f"Full Name: {full_name}")
    print(f"Role: {role}")
    print(f"Is Admin: {is_admin}")
    print()

    confirm = input("Create this user? (y/n): ").strip().lower()
    if confirm != "y":
        print("User creation cancelled")
        sys.exit(0)

    db: Session = SessionLocal()
    try:
        # Check if user already exists
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"Error: User '{username}' already exists")
            sys.exit(1)

        # Create user
        now = datetime.now(timezone.utc)
        user = User(
            username=username,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
            is_admin=is_admin,
            created_at=now,
            updated_at=now
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print()
        print(f"✓ User created successfully!")
        print(f"  ID: {user.id}")
        print(f"  Username: {user.username}")
        print(f"  Full Name: {user.full_name}")
        print(f"  Role: {user.role}")
        print(f"  Is Admin: {user.is_admin}")
        print(f"  Created At: {user.created_at}")

    except Exception as e:
        print(f"Error creating user: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_user_interactive()
