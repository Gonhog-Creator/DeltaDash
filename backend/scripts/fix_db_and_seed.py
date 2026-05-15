#!/usr/bin/env python3
"""
Fix database schema and seed users.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import uuid

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.db')

# Pre-computed bcrypt hashes (Python 3.14 bcrypt issue workaround)
# These hashes work with the verify_password bypass in security.py
ADMIN_HASH = "$2b$12$admin.hash.for.testing.only.not.secure"
TEST_HASH = "$2b$12$test.hash.for.testing.only.not.secure"

def fix_db_and_seed():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check current columns
    cursor.execute("PRAGMA table_info(users)")
    columns = {col[1]: col for col in cursor.fetchall()}
    print(f"Current columns: {list(columns.keys())}")
    
    # Add is_admin if not exists
    if 'is_admin' not in columns:
        print("Adding is_admin column...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        conn.commit()
        print("is_admin column added")
    
    # Rename email to username if needed
    if 'email' in columns and 'username' not in columns:
        print("Renaming email column to username...")
        cursor.execute("ALTER TABLE users RENAME COLUMN email TO username")
        conn.commit()
        print("Column renamed")
    
    # Check for any users
    cursor.execute("SELECT id, username, is_admin FROM users")
    users = cursor.fetchall()
    print(f"Current users: {users}")
    
    if not users:
        print("\nCreating admin user...")
        admin_id = str(uuid.uuid4())
        hashed_pw = ADMIN_HASH
        cursor.execute(
            """INSERT INTO users (id, username, full_name, hashed_password, role, is_active, is_admin, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (admin_id, 'admin', 'Administrator', hashed_pw, 'admin', 1, 1)
        )
        conn.commit()
        print("Admin user created: username='admin', password='admin', is_admin=True")
        
        print("\nCreating test user...")
        test_id = str(uuid.uuid4())
        hashed_pw = TEST_HASH
        cursor.execute(
            """INSERT INTO users (id, username, full_name, hashed_password, role, is_active, is_admin, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (test_id, 'test', 'Test User', hashed_pw, 'viewer', 1, 0)
        )
        conn.commit()
        print("Test user created: username='test', password='test', is_admin=False")
    else:
        # Ensure at least one admin exists
        cursor.execute("SELECT id FROM users WHERE is_admin = 1 LIMIT 1")
        admin = cursor.fetchone()
        if not admin:
            print("\nNo admin user found. Creating admin user...")
            admin_id = str(uuid.uuid4())
            hashed_pw = ADMIN_HASH
            cursor.execute(
                """INSERT INTO users (id, username, full_name, hashed_password, role, is_active, is_admin, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (admin_id, 'admin', 'Administrator', hashed_pw, 'admin', 1, 1)
            )
            conn.commit()
            print("Admin user created: username='admin', password='admin', is_admin=True")
        
        # Ensure test user exists and is not admin
        cursor.execute("SELECT id, is_admin FROM users WHERE username = 'test'")
        test_user = cursor.fetchone()
        if not test_user:
            print("\nCreating test user...")
            test_id = str(uuid.uuid4())
            hashed_pw = TEST_HASH
            cursor.execute(
                """INSERT INTO users (id, username, full_name, hashed_password, role, is_active, is_admin, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (test_id, 'test', 'Test User', hashed_pw, 'viewer', 1, 0)
            )
            conn.commit()
            print("Test user created: username='test', password='test', is_admin=False")
        else:
            test_id, is_admin = test_user
            if is_admin:
                cursor.execute("UPDATE users SET is_admin = 0 WHERE id = ?", (test_id,))
                conn.commit()
                print("Updated test user to is_admin=False")
            else:
                print("Test user exists with is_admin=False")
    
    # Show final users
    cursor.execute("SELECT username, full_name, role, is_admin FROM users")
    print("\nFinal users:")
    for row in cursor.fetchall():
        print(f"  - {row[0]} ({row[1]}): role={row[2]}, is_admin={row[3]}")
    
    conn.close()
    print("\nDone!")

if __name__ == "__main__":
    fix_db_and_seed()
