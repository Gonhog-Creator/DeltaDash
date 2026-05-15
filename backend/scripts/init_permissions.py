#!/usr/bin/env python3
"""
Initialize permissions and seed users.
This script adds the is_admin column and creates test users.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.db')

def init_permissions():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if is_admin column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'is_admin' not in columns:
        print("Adding is_admin column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        conn.commit()
        print("is_admin column added")
    else:
        print("is_admin column already exists")
    
    # Check for admin user and set is_admin=True
    cursor.execute("SELECT id, username, is_admin FROM users WHERE username = 'admin'")
    admin = cursor.fetchone()
    
    if admin:
        admin_id, username, is_admin = admin
        if not is_admin:
            cursor.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin_id,))
            conn.commit()
            print(f"Updated admin user ({username}) to is_admin=True")
        else:
            print(f"Admin user ({username}) already has is_admin=True")
    else:
        print("Admin user not found - you need to create one first")
    
    # Check for test user or create one
    cursor.execute("SELECT id, username, is_admin FROM users WHERE username = 'test'")
    test_user = cursor.fetchone()
    
    if test_user:
        test_id, username, is_admin = test_user
        if is_admin:
            cursor.execute("UPDATE users SET is_admin = 0 WHERE id = ?", (test_id,))
            conn.commit()
            print(f"Updated test user ({username}) to is_admin=False")
        else:
            print(f"Test user ({username}) already has is_admin=False")
    else:
        print("Creating test user with password 'test' (not an admin)...")
        # Import here to avoid dependency issues
        from app.core.security import get_password_hash
        import uuid
        
        test_id = str(uuid.uuid4())
        hashed_password = get_password_hash("test")
        
        cursor.execute(
            """INSERT INTO users (id, username, full_name, hashed_password, role, is_active, is_admin)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (test_id, 'test', 'Test User', hashed_password, 'viewer', 1, 0)
        )
        conn.commit()
        print("Test user created: username='test', password='test', is_admin=False")
    
    conn.close()
    print("\nDone! You can now test the ammunition permissions:")
    print("- Admin user can add/edit/delete ammunition")
    print("- Test user (test/test) can only view ammunition")

if __name__ == "__main__":
    init_permissions()
