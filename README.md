# Ballistic Test Analytics & Prediction Platform

A private, always-on, React-based web application for storing ballistic test data, managing material specifications, analyzing BFD / trauma outcomes, and estimating outcomes for theoretical armor layups.

## Quick Start (First Launch)

### Prerequisites
- Docker and Docker Compose installed
- Git

### 1. Clone and Setup
```bash
git clone <repository-url>
cd DeltaTest
```

### 2. Environment Configuration
```bash
# Copy the environment file (already done for this setup)
# .env file is already configured for development
```

### 3. Launch with Docker Compose
```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### 4. Initialize Database
```bash
# Run database migrations
docker-compose exec backend alembic upgrade head

# Create seed data (admin user and sample data)
docker-compose exec backend python seed_data.py
```

### 5. Access the Application
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### 6. Login Credentials
- **Admin**: admin@ballistic.test / admin123
- **Researcher**: researcher@ballistic.test / research123

## Development Status

### ✅ Implemented Features
- **Backend**: FastAPI with SQLAlchemy models
- **Database**: PostgreSQL with all core tables
- **Authentication**: JWT-based auth with role-based access
- **Frontend**: React + TypeScript + Tailwind CSS
- **Basic Pages**: Login, Dashboard, Materials, Ammunition
- **API Endpoints**: Full CRUD for materials, ammunition, test sessions, panels, shots

### 🚧 In Progress / Missing Features
- **Frontend Pages**: Test Sessions, Panels, Shots, Analytics, Prediction, Import
- **Spreadsheet Import**: File upload and data mapping
- **Analytics Engine**: ANOVA, regression, mixed-effects models
- **Prediction System**: BFD and penetration prediction
- **Report Generation**: PDF/CSV export
- **Material Document Upload**: Specification sheet management

### 📝 Current Limitations
- No data visualization/charts yet
- No statistical modeling implementation
- No file upload functionality
- Limited frontend functionality (only materials and ammunition fully implemented)

## Project Structure
```
DeltaTest/
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── api/v1/        # API endpoints
│   │   ├── db/models/     # SQLAlchemy models
│   │   └── core/          # Configuration and security
│   ├── migrations/        # Alembic database migrations
│   └── seed_data.py       # Initial data setup
├── frontend/               # React TypeScript frontend
│   ├── src/
│   │   ├── pages/        # React pages
│   │   ├── components/    # Shared components
│   │   ├── hooks/         # Custom React hooks
│   │   └── types/         # TypeScript definitions
├── storage/                # File storage directory
├── docker-compose.yml      # Docker service configuration
└── .env                   # Environment variables
```

## Development Workflow

### Adding New Features
1. **Backend**: Add models in `backend/app/db/models/`
2. **API**: Create endpoints in `backend/app/api/v1/`
3. **Frontend**: Add pages in `frontend/src/pages/`
4. **Types**: Update TypeScript definitions in `frontend/src/types/`

### Database Changes
```bash
# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose exec backend alembic upgrade head
```

### Development Commands
```bash
# View logs
docker-compose logs -f [service-name]

# Access backend shell
docker-compose exec backend bash

# Access database
docker-compose exec postgres psql -U ballistic_user -d ballistic
```

## Security Notes
- Default passwords are for development only
- Change SECRET_KEY in production
- Use HTTPS in production
- Review CORS settings for production

## Troubleshooting

### Port Conflicts
If ports 5173, 8000, or 5432 are occupied, modify them in `docker-compose.yml`

### Database Connection Issues
```bash
# Reset database
docker-compose down -v
docker-compose up -d
docker-compose exec backend alembic upgrade head
docker-compose exec backend python seed_data.py
```

### Frontend Build Issues
```bash
# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

## Next Steps for Full Implementation
1. Implement remaining frontend pages
2. Add spreadsheet import functionality
3. Build analytics and modeling engine
4. Create prediction system
5. Add report generation
6. Implement material document upload
7. Add data visualization charts
8. Enhance security features
