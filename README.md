# DeltaDash - Ballistic Test Analytics & Prediction Platform

A private, always-on web application for storing ballistic test data, managing material specifications, analyzing BFD/trauma outcomes, predicting vest performance, and matching RFP requirements to certified vests.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or Docker for containerized DB)

### First-Time Setup

```bash
# Install all dependencies (backend + frontend)
npm install

# Create database and user
createdb ballistic
createuser ballistic_user
psql -d ballistic -c "ALTER USER ballistic_user PASSWORD 'change_me_in_production';"
psql -d ballistic -c "GRANT ALL PRIVILEGES ON DATABASE ballistic TO ballistic_user;"

# Run database migrations
npm run migrate

# Start development servers
npm run dev
```

### Daily Development

```bash
npm run dev          # Start both backend (port 8000) and frontend (port 5173)
npm run dev:backend  # Backend only
npm run dev:frontend # Frontend only
npm run stop         # Stop all services
npm run build        # Build frontend for production
```

### Alternative: Docker Compose

```bash
docker-compose up -d
docker-compose exec backend alembic upgrade head
docker-compose exec backend python seed_data.py
```

### Database-Only (Docker)

```bash
docker compose up -d postgres
```

Then run backend and frontend natively:
```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

### Access URLs

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Default Login

- Admin: admin@ballistic.test / admin123
- Researcher: researcher@ballistic.test / research123

## Features

- **Test Sessions**: Upload Excel test data, group by vest/protocol, track official certifications
- **ML Prediction**: XGBoost models for backface deformation (regression) and perforation (classification) with extrapolation detection
- **Test Planner**: Candidate vest scoring and recommendations for new tests
- **Vests Library**: Material composition, layers, construction details, female vest support
- **Materials**: Physical properties, mechanical specs, weave types, coatings
- **Ammunition**: Caliber normalization, projectile mass, velocity data
- **Geometries**: Panel surface areas by size for energy distribution calculations
- **Analytics**: BFD distributions, velocity comparisons, vest performance dashboards
- **RFP / Pliego Matcher**: AI-powered requirement extraction from bid documents, vest matching with multi-threat-level support, per-level weight limits, female vest scoring, PDF export (EN/ES)
- **Model Management**: Versioned model storage, training metrics, health checks, hyperparameter optimization

## Project Structure

```
DeltaDash/
├── package.json              # Unified npm commands
├── backend/                   # FastAPI Python backend
│   ├── app/
│   │   ├── api/v1/           # API endpoints
│   │   ├── core/             # Config, security
│   │   ├── db/models/        # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/
│   │   │   ├── ml/           # ML training and prediction
│   │   │   ├── pliego_matcher.py
│   │   │   ├── test_session_service.py
│   │   │   └── excel_parser.py
│   ├── migrations/           # Alembic database migrations
│   └── requirements.txt
├── frontend/                  # React + TypeScript + Tailwind
│   ├── src/
│   │   ├── pages/            # React pages
│   │   ├── components/       # Shared components
│   │   ├── hooks/           # Custom React hooks
│   │   ├── api/             # API client and types
│   │   └── utils/           # PDF export, helpers
├── storage/                  # File storage (uploads, model artifacts, reports)
├── docs/                     # Documentation
│   └── 1.2-BL-Plan.md       # Ballistic limit ML plan
├── docker-compose.yml
└── .env
```

## Database Commands

```bash
npm run migrate              # Run Alembic migrations

# Create new migration after model changes
cd backend && alembic revision --autogenerate -m "Description"

# Access database directly
docker compose exec postgres psql -U ballistic_user -d ballistic
```

## Troubleshooting

### Port Conflicts

```bash
lsof -i :5173    # Check frontend port
lsof -i :8000    # Check backend port
npm run stop     # Kill all dev servers
```

### Database Issues

```bash
# Check PostgreSQL status
brew services list | grep postgresql  # macOS
sudo systemctl status postgresql      # Ubuntu

# Restart PostgreSQL
brew services restart postgresql@15  # macOS
sudo systemctl restart postgresql     # Ubuntu

# Reset database (Docker)
docker-compose down -v
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

### Frontend Build Issues

```bash
rm -rf node_modules frontend/node_modules
npm install
```

## Security Notes

- Change `SECRET_KEY` in production
- Change default database password
- Use HTTPS in production
- Review CORS settings for production

## Documentation

- [Railway Deployment & Troubleshooting](RAILWAY.md)
- [Ballistic Limit ML Plan (v1.2.0)](docs/1.2-BL-Plan.md)
