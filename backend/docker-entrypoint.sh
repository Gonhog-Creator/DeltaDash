#!/bin/bash
set -e

# Handle stale alembic version in database
echo "Checking database migration state..."
CURRENT_REVISION=$(alembic current 2>/dev/null || echo "")
if [ -n "$CURRENT_REVISION" ] && [ "$CURRENT_REVISION" != "None" ]; then
    echo "Current database revision: $CURRENT_REVISION"
    # Check if the current revision exists in migration files
    if ! alembic show "$CURRENT_REVISION" >/dev/null 2>&1; then
        echo "Current revision $CURRENT_REVISION not found in migration files"
        echo "Stamping database to base revision to reset migration history"
        alembic stamp None
    fi
fi

# Run Alembic migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --forwarded-allow-ips='*'
