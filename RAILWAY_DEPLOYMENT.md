# Railway Deployment Guide

This guide will help you deploy DeltaDash to Railway with both backend and frontend services.

## Prerequisites

- Your code pushed to GitHub
- A Railway account (free tier works)

## Step-by-Step Deployment

### Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `DeltaDash` repository
4. Railway will detect the `railway.toml` and create a backend service

### Step 2: Add Postgres Database

1. In your Railway project, click **New Service**
2. Select **Postgres** from the database options
3. Railway will automatically:
   - Create a PostgreSQL database
   - Inject the `DATABASE_URL` environment variable into your backend service
   - Handle all database credentials (user, password, host, port)

**No manual user creation needed** - Railway handles this automatically.

### Step 3: Configure Backend Environment Variables

1. Click on your backend service (the one created from your repo)
2. Go to the **Variables** tab
3. Add the following environment variables:

| Variable | Value | Notes |
|----------|-------|-------|
| `SECRET_KEY` | Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` | Required for JWT tokens |
| `CORS_ORIGINS` | `https://your-frontend-url.railway.app` | Will update after frontend is deployed |
| `APP_ENV` | `production` | Sets production mode |
| `USE_RAILWAY_STORAGE` | `true` | Enables Railway volume storage |

**Note:** For now, set `CORS_ORIGINS` to `*` (asterisk) during initial setup. Update it after your frontend is deployed.

### Step 4: Deploy the Backend

1. Click **Deploy** on your backend service
2. Monitor the build logs:
   - Railway will build the Docker image from `backend/Dockerfile`
   - Alembic migrations will run automatically via the start command
   - The FastAPI server will start on the assigned port

3. Once deployed, copy your backend URL (e.g., `https://your-backend.railway.app`)

### Step 5: Add Frontend Service

1. In your Railway project, click **New Service**
2. Select **Deploy from GitHub repo**
3. Choose the same `DeltaDash` repository
4. Configure the service settings:
   - **Root Directory:** `frontend`
   - **Dockerfile Path:** `frontend/Dockerfile`
5. In the **Variables** tab, add:
   - `VITE_API_URL`: `https://your-backend-url.railway.app` (from Step 4)
6. Click **Deploy**

### Step 6: Update CORS Configuration

1. Once your frontend is deployed, copy its URL
2. Go back to your backend service → **Variables** tab
3. Update `CORS_ORIGINS` to your frontend URL:
   - Example: `https://your-frontend.railway.app`
4. Redeploy the backend to apply changes

### Step 7: Verify Deployment

1. Visit your frontend URL - you should see the DeltaDash UI
2. Try logging in or creating an account
3. Check Railway logs if you encounter errors

## Troubleshooting

### Build Fails

- Check the **Logs** tab in Railway for specific error messages
- Common issues:
  - Missing dependencies in `requirements.txt`
  - Python version mismatch (we use 3.11)
  - Dockerfile syntax errors

### Database Migration Fails

- Ensure Postgres service is running before backend deployment
- Verify `DATABASE_URL` is set (Railway should provide this automatically)
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

Railway will automatically create volumes for the paths specified in `railway.toml`:
- `/app/storage/material_docs`
- `/app/storage/uploads`
- `/app/storage/reports`
- `/app/storage/model_artifacts`

These persist across deployments.

### Database Credentials

Railway's Postgres service handles all database credentials:
- The `DATABASE_URL` environment variable contains everything needed
- Format: `postgresql://username:password@host:port/database`
- No manual database user creation required

### Environment Variables

Railway provides these automatically:
- `PORT`: The port your service should listen on
- `DATABASE_URL`: Connection string for Postgres (when added)
- `RAILWAY_VOLUME_URL`: URL for volume access (if using volumes)

You must add these manually:
- `SECRET_KEY`: For JWT token signing
- `CORS_ORIGINS`: For frontend-backend communication
- `APP_ENV`: Environment mode
- `USE_RAILWAY_STORAGE`: To enable Railway volumes
- `VITE_API_URL`: Frontend build-time variable for backend URL

## Cost Estimate

Railway's free tier includes:
- $5/month credit (enough for small projects)
- 512MB RAM per service
- Shared CPU

Your setup requires:
- 1x Backend service (Python/FastAPI)
- 1x Frontend service (Nginx/Static)
- 1x Postgres database

This should fit within the free tier for development/testing.

## Next Steps

After successful deployment:
1. Set up a custom domain (optional)
2. Configure automatic deploys from GitHub
3. Set up monitoring and alerts
4. Add any additional environment variables needed for your specific use case
