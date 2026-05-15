# 🚀 Unified Development Commands

## 📦 Installation & Setup

### Install All Dependencies
```bash
npm install
```
This installs both backend (Python) and frontend (Node.js) dependencies.

### Prerequisites
- PostgreSQL 15+ running locally
- Python 3.11+
- Node.js 18+

### Database Setup
```bash
# Create database and user
createdb ballistic
createuser ballistic_user
psql -d ballistic -c "ALTER USER ballistic_user PASSWORD 'change_me_in_production';"
psql -d ballistic -c "GRANT ALL PRIVILEGES ON DATABASE ballistic TO ballistic_user;"

# Run migrations
npm run migrate
```

## 🖥️ Development Commands

### Start Development Servers
```bash
npm run dev
```
Starts both backend (port 8000) and frontend (port 5173) simultaneously.

### Individual Services
```bash
npm run dev:backend    # Backend only
npm run dev:frontend   # Frontend only
```

## 🔧 Maintenance Commands

### Database Operations
```bash
npm run migrate   # Run database migrations
```

### Build Commands
```bash
npm run build     # Build frontend for production
```

### Stop All Services
```bash
npm run stop      # Stop all development servers
```

## 🌐 Access URLs

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 👤 Default Login

- **Username**: `admin`
- **Password**: `admin`

## 📁 Project Structure

```
DeltaTest/
├── package.json          # ← Unified commands (run from here)
├── backend/              # FastAPI backend
│   ├── app/
│   ├── migrations/
│   └── requirements.txt
├── frontend/             # React frontend
│   ├── src/
│   ├── package.json
│   └── public/
├── storage/              # Local file storage
└── .env                  # Environment variables
```

## 💡 Usage Examples

### Daily Development Workflow
```bash
# Start everything
npm run dev

# Make changes to code
# Frontend hot reloads automatically
# Backend restarts automatically

# Stop when done
npm run stop
```

### Fresh Setup
```bash
# New developer setup
npm install
# Setup PostgreSQL (see above)
npm run migrate
npm run dev
```

### Database Changes
```bash
# After adding new models
npm run migrate
npm run dev
```

## 🎯 Benefits

- ✅ **Traditional development**: No Docker complexity
- ✅ **Unified commands**: Single npm script for everything
- ✅ **Fast development**: Direct file access, instant hot reload
- ✅ **Simple setup**: PostgreSQL + npm install
- ✅ **Cross-platform**: Works on macOS, Linux, Windows

## 🔍 Troubleshooting

### Port Conflicts
```bash
# Check what's using ports
lsof -i :5173
lsof -i :8000

# Kill processes if needed
npm run stop
```

### Database Issues
```bash
# Check PostgreSQL status
brew services list | grep postgresql  # macOS
sudo systemctl status postgresql     # Ubuntu

# Restart PostgreSQL
brew services restart postgresql@15   # macOS
sudo systemctl restart postgresql     # Ubuntu

# Reset database
npm run migrate
```

### Dependency Issues
```bash
# Reinstall everything
rm -rf node_modules frontend/node_modules
npm install
```

---

**Simple Traditional Development: `npm install` → `npm run dev` → Start coding!**
