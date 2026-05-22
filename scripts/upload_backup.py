#!/usr/bin/env python3
"""Script to upload a backup file to Railway storage via base64 encoding."""
import base64
import sys
import os
from app.core.config import settings

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python upload_backup.py <base64_content> <filename>")
        sys.exit(1)

    base64_content = sys.argv[1]
    filename = sys.argv[2]

    # Create backup directory
    backup_dir = os.path.join(settings.upload_dir, 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    # Decode and save
    backup_path = os.path.join(backup_dir, filename)
    with open(backup_path, 'wb') as f:
        f.write(base64.b64decode(base64_content))

    print(f"Backup uploaded successfully to {backup_path}")
