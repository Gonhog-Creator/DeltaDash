#!/bin/bash
set -e

# Handle stale alembic version in database
echo "Checking database migration state..."

# Use Python to check if tables exist and handle migration state
python3 -c "
from app.db.session import SessionLocal
from sqlalchemy import text, inspect
import subprocess
db = SessionLocal()
try:
    # Check if alembic_version table exists
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    
    # Get current revision if alembic_version exists
    current_rev = None
    if 'alembic_version' in tables:
        result = db.execute(text('SELECT version_num FROM alembic_version'))
        row = result.fetchone()
        if row:
            current_rev = row[0]
    print(f'Current database revision: {current_rev or \"None\"}')
    
    # Check if application tables exist
    app_tables = ['ammunition', 'materials', 'vests', 'test_sessions', 'shot_data']
    has_app_tables = any(t in tables for t in app_tables)
    
    # If tables exist but no revision or invalid revision, reset to initial
    if has_app_tables and (not current_rev or current_rev == 'None'):
        print('Application tables exist but no revision, resetting to initial migration')
        if 'alembic_version' in tables:
            db.execute(text('DELETE FROM alembic_version'))
        db.execute(text('INSERT INTO alembic_version (version_num) VALUES (:rev)'), {'rev': '314b789d9830'})
        db.commit()
        print('Reset to initial revision 314b789d9830')
    elif not has_app_tables:
        print('No application tables found, will run migrations from scratch')
        if 'alembic_version' in tables:
            db.execute(text('DELETE FROM alembic_version'))
            db.commit()
    else:
        print(f'Database has revision {current_rev}, will attempt migrations')
except Exception as e:
    print(f'Error checking database state: {e}')
    import traceback
    traceback.print_exc()
    db.rollback()
    exit(1)
finally:
    db.close()
" || echo "Failed to check database state, will attempt migrations"

# Run Alembic migrations
echo "Running database migrations..."
# Try to upgrade, but if it fails due to existing objects, continue
alembic upgrade head || echo "Migration upgrade had issues, but continuing..."

# Start the application
echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --forwarded-allow-ips='*'
