#!/usr/bin/env python3
"""
Create admin user for development.
"""
import uuid
import psycopg2
import bcrypt
import os
import sys

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_admin_user():
    db_url = "postgresql://ballistic_user:ballistic_pass@localhost:5432/ballistic"
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Check if admin already exists
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        existing = cursor.fetchone()
        
        if existing:
            print("Admin user already exists")
            cursor.close()
            conn.close()
            return
        
        user_id = str(uuid.uuid4())
        hashed_password = hash_password("admin")
        
        sql = """INSERT INTO users (id, username, full_name, hashed_password, role, is_active, is_admin, created_at, updated_at)
                 VALUES (%s, %s, %s, %s, %s, true, %s, NOW(), NOW())"""
        
        cursor.execute(sql, (user_id, 'admin', 'Administrator', hashed_password, 'admin', True))
        conn.commit()
        
        print("Admin user created successfully!")
        print("Username: admin")
        print("Password: admin")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_admin_user()
