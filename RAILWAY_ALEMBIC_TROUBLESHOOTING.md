# Railway Alembic Migration Issue - Troubleshooting Summary

## Problem
After pushing to Railway, the backend was returning 500 errors with the message:
```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn) column model_runs.training_avg_error does not exist
```

The `/api/v1/ballistic/versions-with-metrics` endpoint was failing because the database schema was out of sync with the model definition.

## Root Cause
The `model_runs` table in the Railway PostgreSQL database was missing the `training_avg_error` column that was added to the `ModelRun` model in the codebase. This typically happens when:
- A new migration is created but not run on the production database
- The deployment doesn't include running migrations automatically

## Solution Steps

### 1. Create Migration File
```bash
cd /path/to/backend
source venv/bin/activate
alembic revision -m "add_training_avg_error_to_model_runs"
```

### 2. Update Migration File
Edit the generated migration file to add the column:
```python
def upgrade() -> None:
    op.add_column('model_runs', sa.Column('training_avg_error', sa.Float(), nullable=True))

def downgrade() -> None:
    op.drop_column('model_runs', 'training_avg_error')
```

### 3. Connect to Railway Database
Use Railway's TCP proxy to access the production database from local machine:
```bash
railway connect Postgres
```

### 4. Get Database Connection Details
```bash
railway variables --service Postgres
```
Look for:
- `RAILWAY_TCP_PROXY_DOMAIN`: shuttle.proxy.rlwy.net
- `RAILWAY_TCP_PROXY_PORT`: 37435
- `PGUSER`: postgres
- `PGPASSWORD`: <password>
- `POSTGRES_DB`: railway

### 5. Execute SQL Directly
```bash
psql postgresql://postgres:PASSWORD@shuttle.proxy.rlwy.net:PORT/railway -c "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS training_avg_error FLOAT;"
```

### 6. Trigger Redeploy
```bash
railway up
```

### 7. Verify Fix
```bash
railway logs --service DeltaDash-backend --tail 20
```
Look for 200 OK responses instead of 500 errors.

## Alternative Approach (if Railway CLI migration works)
If `railway run` can execute on the remote service:
```bash
railway run --service DeltaDash-backend -- alembic upgrade head
```
Note: This often fails because it tries to connect to Railway's internal database hostname from the local machine.

## Key Takeaways
- Railway's internal database hostname (`postgres.railway.internal`) is only accessible from within Railway's environment
- Use the TCP proxy domain (`shuttle.proxy.rlwy.net`) and port to connect from local machine
- Direct SQL execution is often more reliable than Alembic for quick fixes on Railway
- Always trigger a redeploy after schema changes to ensure the backend picks up the changes
- The migration file should still be committed to the repo for future deployments
