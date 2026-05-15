# Development Startup

Run these commands in three separate terminals to start the development environment.

## Terminal 1: Database
```bash
docker compose up -d postgres
```

## Terminal 2: Backend
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Terminal 3: Frontend
```bash
cd frontend
npm run dev
```

## Access
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Stop
```bash
# Stop postgres (data persists in volume)
docker compose down
```
