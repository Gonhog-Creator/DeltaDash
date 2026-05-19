"""
Script to generate user records and insert them directly into the database.
Run this script to create users in the database.
"""

import uuid
import psycopg2
import os
import bcrypt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_user_in_db(username: str, password: str, full_name: str = None, role: str = "viewer", is_admin: bool = False, db_url: str = None):
    """Create a user directly in the database."""
    user_id = str(uuid.uuid4())
    
    if full_name is None:
        full_name = username
    
    # Hash the password
    hashed_password = hash_password(password)
    
    # Connect to database
    if db_url is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("DATABASE_URL not found in .env file or environment variables")
            print("Please ensure DATABASE_URL is set in your .env file")
            return False
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        sql = """INSERT INTO users (id, username, full_name, hashed_password, role, is_active, is_admin, created_at, updated_at)
VALUES (%s, %s, %s, %s, %s, true, %s, NOW(), NOW())"""
        
        cursor.execute(sql, (user_id, username, full_name, hashed_password, role, is_admin))
        conn.commit()
        
        print(f"User '{username}' created successfully!")
        print(f"ID: {user_id}")
        print(f"Role: {role}")
        print(f"Admin: {is_admin}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error creating user: {e}")
        return False


def main():
    print("=" * 80)
    print("User Creation Script")
    print("=" * 80)
    print()
    
    # Get database URL from command line or environment
    import sys
    db_url = None
    if len(sys.argv) > 1:
        db_url = sys.argv[1]
        print(f"Using database URL from command line")
    elif os.getenv("REMOTE_DATABASE_URL"):
        db_url = os.getenv("REMOTE_DATABASE_URL")
        print(f"Using REMOTE_DATABASE_URL from .env file (Railway database)")
    elif os.getenv("DATABASE_URL"):
        db_url = os.getenv("DATABASE_URL")
        print(f"Using DATABASE_URL from .env file (local database)")
    else:
        print("DATABASE_URL not found in .env file or environment variables")
        print("Please set DATABASE_URL in your .env file")
        print()
        db_url = input("Enter database URL: ").strip()
    
    print(f"Connecting to database...")
    print()
    
    while True:
        print("=" * 80)
        print("Create a new user")
        print("=" * 80)
        
        username = input("Username (or press Enter to exit): ").strip()
        if not username:
            break
        
        password = input("Password: ").strip()
        if not password:
            print("Password is required!")
            continue
        
        full_name = input("Full name (press Enter to use username): ").strip()
        if not full_name:
            full_name = username
        
        role = input("Role (viewer/editor/admin, default: viewer): ").strip().lower()
        if role not in ["viewer", "editor", "admin"]:
            role = "viewer"
        
        is_admin_input = input("Is admin? (y/n, default: n): ").strip().lower()
        is_admin = is_admin_input == "y"
        
        if role == "admin":
            is_admin = True
        
        print()
        print(f"Creating user: {username}")
        print(f"Role: {role}")
        print(f"Admin: {is_admin}")
        print()
        
        if create_user_in_db(username, password, full_name, role, is_admin, db_url):
            print()
        else:
            print("Failed to create user. Please try again.")
            print()


if __name__ == "__main__":
    main()
