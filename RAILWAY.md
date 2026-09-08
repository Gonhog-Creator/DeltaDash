# Railway Deployment & Troubleshooting

## Prerequisites

- Your code pushed to GitHub
- A Railway account (free tier works)
- Railway CLI installed (`npm install -g @railway/cli`)

## Initial Deployment

### Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **New Project** -> **Deploy from GitHub repo**
3. Select your `DeltaDash` repository
4. Railway will detect the `railway.toml` and create a backend service

### Step 2: Add Postgres Database

1. In your Railway project, click **New Service**
2. Select **Postgres** from the database options
3. Railway will automatically:
   - Create a PostgreSQL database
   - Inject the `DATABASE_URL` environment variable into your backend service
   - Handle all database credentials (user, password, host, port)

No manual user creation needed - Railway handles this automatically.

### Step 3: Configure Backend Environment Variables

1. Click on your backend service
2. Go to the **Variables** tab
3. Add the following:

| Variable | Value | Notes |
|----------|-------|-------|
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` | Required for JWT tokens |
| `CORS_ORIGINS` | `https://your-frontend-url.railway.app` | Update after frontend deployed |
| `APP_ENV` | `production` | Sets production mode |
| `USE_RAILWAY_STORAGE` | `true` | Enables Railway volume storage |

Set `CORS_ORIGINS` to `*` during initial setup, then update after frontend is deployed.

### Step 4: Deploy the Backend

1. Click **Deploy** on your backend service
2. Monitor the build logs:
   - Railway builds the Docker image from `backend/Dockerfile`
   - Alembic migrations run automatically via the start command
   - FastAPI server starts on the assigned port
3. Copy your backend URL (e.g., `https://your-backend.railway.app`)

### Step 5: Add Frontend Service

1. Click **New Service** -> **Deploy from GitHub repo**
2. Choose the same `DeltaDash` repository
3. Configure:
   - **Root Directory:** `frontend`
   - **Dockerfile Path:** `frontend/Dockerfile`
4. Add variable: `VITE_API_URL` = `https://your-backend-url.railway.app`
5. Click **Deploy**

### Step 6: Update CORS Configuration

1. Copy your frontend URL
2. Go to backend service -> **Variables** tab
3. Update `CORS_ORIGINS` to your frontend URL (e.g., `https://your-frontend.railway.app`)
4. Redeploy the backend

### Step 7: Verify

1. Visit your frontend URL - you should see the DeltaDash UI
2. Try logging in
3. Check Railway logs if you encounter errors

## Railway CLI Commands

```bash
# Link to project (first time)
railway link --project DeltaDash

# Link to specific service
railway link --project DeltaDash --service Postgres
railway link --project DeltaDash --service DeltaDash-backend

# View variables
railway variables

# Deploy
railway up

# View logs
railway logs --service DeltaDash-backend --tail 20

# Connect to database
railway connect Postgres
```

## Connecting to Remote Database from Local Machine

Railway's internal database hostname (`postgres.railway.internal`) is only accessible from within Railway's environment. Use the TCP proxy to connect locally:

```bash
# Get connection details
railway variables --service Postgres

# Look for:
#   DATABASE_PUBLIC_URL (contains the proxy host and port)
#   PGUSER, PGPASSWORD, PGDATABASE

# Connect with psql
PGPASSWORD=<password> psql -h shuttle.proxy.rlwy.net -p <port> -U postgres -d railway -c "SELECT 1;"

# Or use the full URL
psql postgresql://postgres:PASSWORD@shuttle.proxy.rlwy.net:PORT/railway
```

## Alembic Migration Troubleshooting

### Problem: Missing Column Errors After Deploy

After pushing to Railway, the backend returns 500 errors:
```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn) column X does not exist
```

This happens when a new migration is committed but not run on the production database.

### Solution 1: Direct SQL (Quick Fix)

```bash
# Connect to Railway database (see above)
PGPASSWORD=<password> psql -h shuttle.proxy.rlwy.net -p <port> -U postgres -d railway \
  -c "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS training_avg_error FLOAT;"
```

Then trigger a redeploy:
```bash
railway up
```

### Solution 2: Railway Run Alembic (If Available)

```bash
railway run --service DeltaDash-backend -- alembic upgrade head
```

Note: This often fails because it tries to connect to Railway's internal database hostname from your local machine. Use direct SQL instead.

### Key Takeaways

- Railway's internal database hostname (`postgres.railway.internal`) is only accessible from within Railway
- Use the TCP proxy domain (`shuttle.proxy.rlwy.net`) and port to connect from local
- Direct SQL execution is often more reliable than Alembic for quick fixes on Railway
- Always trigger a redeploy after schema changes
- The migration file should still be committed to the repo for future deployments

## General Troubleshooting

### Build Fails

- Check the **Logs** tab in Railway for specific error messages
- Common issues:
  - Missing dependencies in `requirements.txt`
  - Python version mismatch (we use 3.11)
  - Dockerfile syntax errors

### Database Migration Fails

- Ensure Postgres service is running before backend deployment
- Verify `DATABASE_URL` is set (Railway provides this automatically)
- Check that alembic can connect to the database in the logs

### CORS Errors

- Verify `CORS_ORIGINS` matches your frontend URL exactly
- Include the protocol (https://) and no trailing slash
- Multiple origins can be comma-separated: `https://url1.com,https://url2.com`

### Frontend Can't Connect to Backend

- Verify `VITE_API_URL` is set correctly on the frontend service
- Check that the backend URL is accessible
- Ensure the backend is running and healthy (check /health endpoint)

### Storage Issues

- Verify `USE_RAILWAY_STORAGE=true` is set on backend
- Railway volumes are automatically created based on `railway.toml` configuration
- Check that storage directories exist in the Dockerfile

## Railway-Specific Notes

### Volumes

Railway automatically creates volumes for paths specified in `railway.toml`:
- `/app/storage/material_docs`
- `/app/storage/uploads`
- `/app/storage/reports`
- `/app/storage/model_artifacts`

These persist across deployments.

### Environment Variables

Railway provides automatically:
- `PORT`: The port your service should listen on
- `DATABASE_URL`: Connection string for Postgres
- `RAILWAY_VOLUME_URL`: URL for volume access (if using volumes)

You must add manually:
- `SECRET_KEY`: For JWT token signing
- `CORS_ORIGINS`: For frontend-backend communication
- `APP_ENV`: Environment mode
- `USE_RAILWAY_STORAGE`: To enable Railway volumes
- `VITE_API_URL`: Frontend build-time variable for backend URL

### Cost Estimate

Railway's free tier includes:
- $5/month credit (enough for small projects)
- 512MB RAM per service
- Shared CPU

Your setup requires:
- 1x Backend service (Python/FastAPI)
- 1x Frontend service (Nginx/Static)
- 1x Postgres database

This should fit within the free tier for development/testing.
