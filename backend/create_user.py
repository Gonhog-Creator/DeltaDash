"""
Script to generate user records for direct database insertion.
Run this script to get SQL INSERT statements for creating users.
"""

import uuid


def generate_user_sql(username: str, hashed_password: str, full_name: str = None, role: str = "viewer", is_admin: bool = False):
    """Generate SQL INSERT statement for a user with a pre-hashed password."""
    user_id = str(uuid.uuid4())
    
    if full_name is None:
        full_name = username
    
    sql = f"""INSERT INTO users (id, username, full_name, hashed_password, role, is_active, is_admin, created_at, updated_at)
VALUES ('{user_id}', '{username}', '{full_name}', '{hashed_password}', '{role}', true, {str(is_admin).lower()}, NOW(), NOW());"""
    
    return sql


def main():
    print("=" * 80)
    print("User Creation SQL Generator")
    print("=" * 80)
    print()
    print("NOTE: This script generates SQL INSERT statements for custom users.")
    print("For custom passwords, use an online bcrypt hasher or run this in the Docker container.")
    print()
    
    print("=" * 80)
    print("Create custom users")
    print("=" * 80)
    print()
    
    while True:
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
        print("=" * 80)
        print(f"User: {username}")
        print(f"Password: {password}")
        print(f"Role: {role}")
        print(f"Admin: {is_admin}")
        print()
        print("Step 1: Hash your password using: https://bcrypt-generator.com/")
        print("Step 2: Replace <HASHED_PASSWORD> below with your bcrypt hash")
        print()
        print(generate_user_sql(username, "<HASHED_PASSWORD>", full_name, role, is_admin))
        print("=" * 80)
        print()


if __name__ == "__main__":
    main()
