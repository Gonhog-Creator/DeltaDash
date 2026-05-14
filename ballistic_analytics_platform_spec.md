# Ballistic Test Analytics & Prediction Platform

A private, always-on, React-based web application for storing ballistic test data, managing material specifications, analyzing BFD / trauma outcomes, and estimating outcomes for theoretical armor layups.

This document is intended to be used as a project specification for Claude, Windsurf, Cursor, PyCharm, VS Code, or another coding assistant.

---

## 1. Project Goal

Build a private web application that allows users to:

1. Upload historical ballistic test spreadsheets.
2. Normalize and store test records in a structured database.
3. Maintain a material library with fabric density, thickness, areal density, manufacturer, and specification sheets.
4. Maintain ammunition and shot-placement lookup tables.
5. Analyze BFD, velocity, penetration, trauma, and other outcomes.
6. Run ANOVA/regression/mixed-effects style analyses.
7. Create theoretical armor layups from known materials.
8. Estimate predicted BFD and trauma outcomes with uncertainty.
9. Expand the model as more test data becomes available.
10. Allow nontechnical users to use the system through a browser without cloning the repository.

The application should be designed for private R&D use, not public deployment.

---

## 2. Recommended Technical Stack

### Frontend

Use:

- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- Recharts or Plotly.js for charts
- TanStack Table for data tables
- React Hook Form + Zod for forms and validation

Suggested folder:

```text
frontend/
```

### Backend

Use:

- Python
- FastAPI
- SQLAlchemy 2.x
- Pydantic
- Alembic for migrations
- Pandas for spreadsheet parsing
- Statsmodels for ANOVA/regression/mixed-effects models
- Scikit-learn for predictive modeling
- Optional later: PyMC or Bambi for Bayesian models

Suggested folder:

```text
backend/
```

### Database

Use:

- PostgreSQL for production
- SQLite only for local development or early prototyping

Suggested production database:

```text
PostgreSQL 15+
```

### Object/File Storage

Use local private storage at first, then optionally move to S3-compatible storage.

Store:

- uploaded spreadsheets
- material specification sheets
- PDFs
- generated reports
- model artifacts

Suggested folder:

```text
storage/
```

### Deployment

Use one of:

- Docker Compose on a private VPS
- AWS Lightsail
- DigitalOcean Droplet
- Hetzner VPS
- Railway / Render / Fly.io if acceptable
- Internal company server

The app should run continuously as:

```text
React frontend served by Nginx
FastAPI backend served by Uvicorn/Gunicorn
PostgreSQL database
```

Use Docker Compose for reproducible deployment.

---

## 3. High-Level Architecture

```text
User Browser
    |
    v
React Frontend
    |
    v
FastAPI Backend
    |
    +--> PostgreSQL Database
    |
    +--> File Storage
    |
    +--> Modeling Engine
    |
    +--> Report Generator
```

---

## 4. Core Concepts

The application should separate the following entities:

1. Materials
2. Material specification sheets
3. Armor panels / vest builds
4. Layer stacks
5. Ammunition
6. Shot placement patterns
7. Individual shots
8. Test sessions
9. Outcome measurements
10. Statistical models
11. Predictions

This separation is important because the same material can appear in multiple panels, the same ammunition can be used across many tests, and one panel can receive multiple shots.

---

## 5. Database Schema

Use UUID primary keys unless there is a strong reason not to.

### 5.1 users

For authentication and authorization.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Suggested roles:

```text
admin
researcher
data_entry
viewer
```

---

### 5.2 materials

Stores known fabrics, backers, coatings, films, foams, ceramics, metals, and other armor-related materials.

```sql
CREATE TABLE materials (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT,
    manufacturer TEXT,
    supplier TEXT,
    material_class TEXT,
    fiber_type TEXT,
    weave_type TEXT,
    coating TEXT,
    color TEXT,
    areal_density_g_m2 NUMERIC,
    thickness_mm NUMERIC,
    density_g_cm3 NUMERIC,
    tensile_strength_mpa NUMERIC,
    modulus_gpa NUMERIC,
    elongation_percent NUMERIC,
    notes TEXT,
    source_confidence TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Example `material_class` values:

```text
aramid
UHMWPE
nylon
basalt
carbon_fiber
glass_fiber
ceramic
metal
foam
rubber
film
coating
unknown
```

---

### 5.3 material_documents

Stores specification sheets, safety sheets, technical PDFs, and images.

```sql
CREATE TABLE material_documents (
    id UUID PRIMARY KEY,
    material_id UUID REFERENCES materials(id),
    document_type TEXT,
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    parsed_text TEXT,
    manufacturer_detected TEXT,
    extraction_confidence NUMERIC,
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Example `document_type` values:

```text
MSS
TDS
SDS
COA
invoice
photo
unknown
```

---

### 5.4 ammunition

Stores projectile/ammunition details.

```sql
CREATE TABLE ammunition (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    caliber TEXT,
    projectile_type TEXT,
    projectile_mass_grains NUMERIC,
    projectile_mass_grams NUMERIC,
    nominal_velocity_fps NUMERIC,
    nominal_velocity_m_s NUMERIC,
    manufacturer TEXT,
    lot_number TEXT,
    standard_reference TEXT,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Example `projectile_type` values:

```text
FMJ
JHP
ball
AP
fragment
slug
unknown
```

---

### 5.5 test_sessions

Stores high-level information about a test day or test campaign.

```sql
CREATE TABLE test_sessions (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    test_date DATE,
    lab_name TEXT,
    operator TEXT,
    protocol TEXT,
    clay_temperature_c NUMERIC,
    ambient_temperature_c NUMERIC,
    humidity_percent NUMERIC,
    conditioning TEXT,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Example `conditioning` values:

```text
ambient
wet
hot
cold
tumbled
aged
unknown
```

---

### 5.6 armor_panels

Stores tested armor panel or vest build.

```sql
CREATE TABLE armor_panels (
    id UUID PRIMARY KEY,
    test_session_id UUID REFERENCES test_sessions(id),
    panel_code TEXT NOT NULL,
    vest_type TEXT,
    panel_shape TEXT,
    panel_width_mm NUMERIC,
    panel_height_mm NUMERIC,
    panel_thickness_mm NUMERIC,
    total_layers INTEGER,
    total_areal_density_g_m2 NUMERIC,
    total_mass_g NUMERIC,
    construction_notes TEXT,
    stitch_pattern TEXT,
    curvature TEXT,
    backing_material TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Example `vest_type` values:

```text
soft_armor
hard_plate
hybrid
helmet
shield
experimental_coupon
unknown
```

---

### 5.7 armor_panel_layers

Stores layer-by-layer construction.

```sql
CREATE TABLE armor_panel_layers (
    id UUID PRIMARY KEY,
    panel_id UUID REFERENCES armor_panels(id) ON DELETE CASCADE,
    layer_index INTEGER NOT NULL,
    material_id UUID REFERENCES materials(id),
    orientation_degrees NUMERIC,
    layer_count INTEGER NOT NULL DEFAULT 1,
    notes TEXT
);
```

This table is critical. Do not store only “24 layers” as a single field. The order and composition of layers may matter.

---

### 5.8 shot_patterns

Stores named shot-placement patterns.

```sql
CREATE TABLE shot_patterns (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    vest_type TEXT,
    protocol TEXT,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

### 5.9 shot_pattern_positions

Stores positions within a shot pattern.

```sql
CREATE TABLE shot_pattern_positions (
    id UUID PRIMARY KEY,
    shot_pattern_id UUID REFERENCES shot_patterns(id) ON DELETE CASCADE,
    shot_number INTEGER NOT NULL,
    x_normalized NUMERIC,
    y_normalized NUMERIC,
    x_mm NUMERIC,
    y_mm NUMERIC,
    impact_angle_degrees NUMERIC DEFAULT 0,
    location_label TEXT,
    notes TEXT
);
```

Use normalized coordinates where possible:

```text
x_normalized: 0.0 to 1.0 from left to right
y_normalized: 0.0 to 1.0 from bottom to top
```

---

### 5.10 shots

Stores individual ballistic shots and outcomes.

```sql
CREATE TABLE shots (
    id UUID PRIMARY KEY,
    test_session_id UUID REFERENCES test_sessions(id),
    panel_id UUID REFERENCES armor_panels(id),
    ammunition_id UUID REFERENCES ammunition(id),
    shot_pattern_position_id UUID REFERENCES shot_pattern_positions(id),
    shot_number INTEGER,
    measured_velocity_fps NUMERIC,
    measured_velocity_m_s NUMERIC,
    impact_angle_degrees NUMERIC,
    bfd_mm NUMERIC,
    penetration BOOLEAN,
    partial_penetration BOOLEAN,
    trauma_score NUMERIC,
    pass_fail TEXT,
    distance_m NUMERIC,
    yaw_observed BOOLEAN,
    edge_hit BOOLEAN,
    anomaly_flag BOOLEAN DEFAULT FALSE,
    anomaly_notes TEXT,
    raw_source_file TEXT,
    raw_row_number INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Suggested `pass_fail` values:

```text
pass
fail_bfd
fail_penetration
invalid
unknown
```

---

### 5.11 model_runs

Tracks fitted statistical/predictive models.

```sql
CREATE TABLE model_runs (
    id UUID PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_type TEXT NOT NULL,
    version TEXT NOT NULL,
    training_started_at TIMESTAMP,
    training_completed_at TIMESTAMP,
    training_row_count INTEGER,
    formula TEXT,
    metrics_json JSONB,
    artifact_path TEXT,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Example `model_type` values:

```text
anova
linear_regression
mixed_effects
random_forest
gradient_boosting
bayesian_hierarchical
logistic_regression
```

---

### 5.12 predictions

Stores generated predictions for traceability.

```sql
CREATE TABLE predictions (
    id UUID PRIMARY KEY,
    model_run_id UUID REFERENCES model_runs(id),
    requested_by UUID REFERENCES users(id),
    input_json JSONB NOT NULL,
    predicted_bfd_mm NUMERIC,
    prediction_interval_low_mm NUMERIC,
    prediction_interval_high_mm NUMERIC,
    probability_bfd_gt_44 NUMERIC,
    probability_penetration NUMERIC,
    extrapolation_warning BOOLEAN DEFAULT FALSE,
    comparable_shot_count INTEGER,
    output_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 6. Backend API Design

Base URL:

```text
/api/v1
```

### 6.1 Authentication

```text
POST /auth/login
POST /auth/logout
GET  /auth/me
POST /auth/change-password
```

Use JWT cookies or secure session cookies.

For private deployment, cookie-based auth is preferred over storing tokens in browser local storage.

---

### 6.2 Materials

```text
GET    /materials
POST   /materials
GET    /materials/{material_id}
PATCH  /materials/{material_id}
DELETE /materials/{material_id}
POST   /materials/{material_id}/documents
GET    /materials/{material_id}/documents
```

Material search should support:

```text
name
manufacturer
fiber_type
material_class
areal_density range
thickness range
```

---

### 6.3 Ammunition

```text
GET    /ammunition
POST   /ammunition
GET    /ammunition/{ammunition_id}
PATCH  /ammunition/{ammunition_id}
DELETE /ammunition/{ammunition_id}
```

---

### 6.4 Test Sessions

```text
GET    /test-sessions
POST   /test-sessions
GET    /test-sessions/{test_session_id}
PATCH  /test-sessions/{test_session_id}
DELETE /test-sessions/{test_session_id}
```

---

### 6.5 Armor Panels

```text
GET    /panels
POST   /panels
GET    /panels/{panel_id}
PATCH  /panels/{panel_id}
DELETE /panels/{panel_id}
GET    /panels/{panel_id}/layers
PUT    /panels/{panel_id}/layers
```

---

### 6.6 Shots

```text
GET    /shots
POST   /shots
GET    /shots/{shot_id}
PATCH  /shots/{shot_id}
DELETE /shots/{shot_id}
```

Support filters:

```text
test_session_id
panel_id
ammunition_id
material_id
velocity range
BFD range
penetration yes/no
anomaly yes/no
date range
```

---

### 6.7 Spreadsheet Import

```text
POST /imports/spreadsheet
GET  /imports/{import_id}
POST /imports/{import_id}/map-columns
POST /imports/{import_id}/validate
POST /imports/{import_id}/commit
```

Import workflow:

1. Upload spreadsheet.
2. Parse sheets.
3. Preview columns.
4. User maps spreadsheet columns to database fields.
5. Validate rows.
6. Show errors and warnings.
7. Commit valid rows to database.
8. Store original spreadsheet.

---

### 6.8 Shot Placement Patterns

```text
GET    /shot-patterns
POST   /shot-patterns
GET    /shot-patterns/{shot_pattern_id}
PATCH  /shot-patterns/{shot_pattern_id}
DELETE /shot-patterns/{shot_pattern_id}
GET    /shot-patterns/{shot_pattern_id}/positions
PUT    /shot-patterns/{shot_pattern_id}/positions
```

---

### 6.9 Analytics

```text
GET  /analytics/summary
POST /analytics/anova
POST /analytics/regression
POST /analytics/mixed-effects
POST /analytics/model-diagnostics
```

Example request for ANOVA:

```json
{
  "outcome": "bfd_mm",
  "factors": ["ammunition_id", "material_class", "shot_location"],
  "covariates": ["measured_velocity_fps", "total_areal_density_g_m2"],
  "filters": {
    "penetration": false,
    "anomaly_flag": false
  }
}
```

---

### 6.10 Prediction

```text
POST /predictions/bfd
GET  /predictions/{prediction_id}
GET  /predictions
```

Example prediction request:

```json
{
  "ammunition_id": "uuid",
  "measured_velocity_fps": 1430,
  "vest_type": "soft_armor",
  "shot_location": "center",
  "layers": [
    {
      "material_id": "uuid",
      "layer_count": 12,
      "orientation_degrees": 0
    },
    {
      "material_id": "uuid",
      "layer_count": 12,
      "orientation_degrees": 90
    }
  ],
  "conditioning": "ambient"
}
```

Example response:

```json
{
  "predicted_bfd_mm": 31.8,
  "prediction_interval_low_mm": 24.5,
  "prediction_interval_high_mm": 42.7,
  "probability_bfd_gt_44": 0.08,
  "probability_penetration": 0.03,
  "comparable_shot_count": 42,
  "extrapolation_warning": false,
  "warnings": []
}
```

---

## 7. Modeling Strategy

### 7.1 Start Simple

The first useful model should be interpretable.

Initial model:

```text
bfd_mm ~ measured_velocity_fps
       + ammunition_type
       + shot_location
       + total_areal_density_g_m2
       + total_thickness_mm
       + material_class
```

Use ordinary least squares first, then compare with robust regression.

---

### 7.2 ANOVA

Use ANOVA for structured comparison.

Questions ANOVA can help answer:

1. Does BFD differ by material class?
2. Does BFD differ by ammunition type?
3. Does BFD differ by shot placement?
4. Is there an interaction between ammunition and material class?
5. Is there an interaction between velocity and panel construction?

Example formula:

```text
bfd_mm ~ C(ammunition_type)
       + C(material_class)
       + C(shot_location)
       + measured_velocity_fps
       + total_areal_density_g_m2
       + C(ammunition_type):C(material_class)
```

Use Type II or Type III ANOVA depending on balance and design.

Expect the data to be unbalanced. Ballistic test data is rarely cleanly balanced.

---

### 7.3 Mixed-Effects Model

Because shots are nested within panels and test sessions, use mixed-effects models.

Example:

```text
bfd_mm ~ measured_velocity_fps
       + C(ammunition_type)
       + C(shot_location)
       + total_areal_density_g_m2
       + total_thickness_mm
       + C(primary_material_class)
       + (1 | panel_id)
       + (1 | test_session_id)
```

In Python, use:

```text
statsmodels MixedLM
```

Later consider:

```text
Bambi / PyMC
```

A mixed model is important because multiple shots from the same panel are not independent.

---

### 7.4 Predictive Model

Once enough data exists, compare:

1. Linear regression
2. Mixed-effects regression
3. Random forest
4. Gradient boosting
5. Bayesian hierarchical model

Do not use black-box machine learning as the only model. Ballistic data needs interpretability and uncertainty.

Every prediction should include:

1. Predicted BFD
2. Prediction interval
3. Probability of exceeding a BFD threshold
4. Probability of penetration if data supports it
5. Similar historical tests
6. Extrapolation warning

---

### 7.5 Extrapolation Detection

The app should warn when a user asks for a design outside the tested data space.

Examples:

```text
No prior tests with this ammunition type.
Velocity is above the 95th percentile of training data.
Material class has fewer than 10 historical shots.
Layer count is outside observed range.
Total areal density is below observed range for this threat.
```

Implement a simple first version using min/max/range checks.

Later improve using nearest-neighbor distance in feature space.

---

### 7.6 Penetration Model

BFD and penetration should be modeled separately.

BFD model:

```text
continuous outcome
linear / mixed / gradient model
```

Penetration model:

```text
binary outcome
logistic regression / Bayesian logistic / tree model
```

Example:

```text
penetration ~ velocity
            + ammunition_type
            + total_areal_density
            + material_class
            + shot_location
```

---

## 8. Frontend Pages

### 8.1 Dashboard

Route:

```text
/
```

Show:

- total shots
- total panels
- total materials
- total test sessions
- recent tests
- average BFD
- penetration rate
- flagged anomalies
- charts

Charts:

- BFD over time
- BFD by ammunition
- BFD vs velocity
- penetration rate by ammunition
- BFD by material class

---

### 8.2 Materials Library

Route:

```text
/materials
```

Features:

- searchable material table
- create/edit material
- upload material specification sheet
- view parsed manufacturer
- view thickness, density, areal density
- link material to panels
- flag unknown manufacturer

---

### 8.3 Material Detail

Route:

```text
/materials/:id
```

Show:

- material properties
- linked documents
- panels using this material
- shots involving panels using this material
- observed BFD distribution
- notes and confidence level

---

### 8.4 Test Sessions

Route:

```text
/test-sessions
```

Show:

- session list
- date
- lab
- protocol
- number of panels
- number of shots
- environmental information

---

### 8.5 Panel Builder

Route:

```text
/panels/new
```

Features:

- create a panel
- add material layers
- set layer order
- set orientation
- calculate total thickness
- calculate total areal density
- duplicate existing panel
- save as theoretical or tested panel

---

### 8.6 Panel Detail

Route:

```text
/panels/:id
```

Show:

- panel construction
- layer stack
- total calculated properties
- shots fired into panel
- BFD outcomes
- penetration outcomes
- charts

---

### 8.7 Shot Data

Route:

```text
/shots
```

Features:

- searchable table
- filters
- inline edit
- anomaly flagging
- export CSV

---

### 8.8 Spreadsheet Import

Route:

```text
/import
```

Workflow:

1. Upload file.
2. Select sheet.
3. Preview rows.
4. Map columns.
5. Validate.
6. Review errors.
7. Commit.

Validation examples:

```text
BFD must be numeric.
Velocity must be numeric.
Shot number must be present.
Panel code must be present.
Ammunition must map to known ammunition or create a new record.
Material must map to known material or be flagged.
```

---

### 8.9 Shot Placement Pattern Editor

Route:

```text
/shot-patterns
```

Features:

- create pattern
- define shot positions
- upload diagram image if useful
- click-to-place shot locations on normalized panel
- map shot numbers to coordinates

---

### 8.10 Analytics

Route:

```text
/analytics
```

Tabs:

1. Summary
2. ANOVA
3. Regression
4. Mixed-effects model
5. Model diagnostics

User options:

- choose outcome
- choose factors
- choose covariates
- filter anomalies
- filter ammunition
- filter material class
- export model summary

---

### 8.11 Prediction Sandbox

Route:

```text
/predict
```

This is a core page.

User inputs:

- ammunition
- velocity
- vest/panel type
- shot location
- conditioning
- theoretical layer stack
- material order
- layer count
- orientation

Outputs:

- predicted BFD
- prediction interval
- probability BFD > threshold
- probability penetration
- comparable historical shots
- extrapolation warnings
- model version
- save prediction
- export report

---

### 8.12 Reports

Route:

```text
/reports
```

Generate:

- test session report
- material performance report
- panel performance report
- prediction report
- model validation report

Export formats:

```text
PDF
CSV
XLSX
JSON
```

---

## 9. Spreadsheet Import Requirements

Historical spreadsheets may be inconsistent. Build the importer defensively.

### 9.1 Supported Formats

```text
.xlsx
.xls
.csv
```

### 9.2 Import Steps

1. Save original file.
2. Parse all sheets.
3. Detect likely header rows.
4. Preview data.
5. User maps columns.
6. Validate rows.
7. Commit valid rows.
8. Store invalid rows with error messages.

### 9.3 Common Column Names to Recognize

For shot number:

```text
shot
shot number
shot #
shot_no
impact
```

For BFD:

```text
BFD
backface deformation
back face deformation
deformation
BFD mm
```

For velocity:

```text
velocity
speed
fps
v0
impact velocity
measured velocity
```

For ammunition:

```text
ammo
ammunition
round
caliber
projectile
threat
```

For panel:

```text
panel
vest
sample
sample id
build
construction
```

---

## 10. Derived Variables

The backend should compute derived variables rather than forcing users to enter everything manually.

### 10.1 Material/Panel Derived Variables

For each panel:

```text
total_layers
total_thickness_mm
total_areal_density_g_m2
material_class_counts
primary_material_class
hybrid_material_flag
```

### 10.2 Shot Derived Variables

For each shot:

```text
kinetic_energy_j
momentum_kg_m_s
velocity_m_s
projectile_mass_kg
shot_location_label
center_distance_normalized
```

### 10.3 Useful Physics Calculations

```text
mass_kg = grains * 0.00006479891
velocity_m_s = fps * 0.3048
kinetic_energy_j = 0.5 * mass_kg * velocity_m_s^2
momentum_kg_m_s = mass_kg * velocity_m_s
```

---

## 11. Model Output Requirements

Never show only a single prediction.

Every BFD prediction must show:

```text
predicted BFD
prediction interval
model version
number of similar historical shots
extrapolation warning
input assumptions
date/time generated
```

Recommended format:

```text
Predicted BFD: 31.8 mm
95% prediction interval: 24.5–42.7 mm
Probability BFD > 44 mm: 8%
Probability penetration: 3%
Comparable historical shots: 42
Model version: bfd_mixed_effects_v0.3
Extrapolation warning: No
```

---

## 12. Similar Historical Shots

Each prediction should display similar prior tests.

Use a first version based on simple filters:

```text
same ammunition class
similar velocity ±100 fps
same primary material class
similar total areal density ±20%
same shot location if available
```

Later use nearest-neighbor search.

Display:

```text
test date
panel code
ammunition
velocity
BFD
penetration
distance from requested configuration
```

---

## 13. Security Requirements

This application will contain proprietary R&D data. Treat security as a core requirement.

### 13.1 Authentication

Required:

- login required for all pages
- strong password rules
- session timeout
- secure cookies
- password hashing with bcrypt or argon2

Optional later:

- MFA
- SSO
- IP allowlist
- VPN-only access

### 13.2 Authorization

Role-based access:

```text
admin: full access
researcher: create/edit tests and run models
data_entry: upload and clean data
viewer: read-only dashboards and reports
```

### 13.3 Data Protection

Required:

- no public unauthenticated endpoints
- no test data committed to GitHub
- environment variables for secrets
- database backups
- file upload size limits
- file type validation
- audit log for edits

### 13.4 Audit Logging

Create an audit table:

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id UUID,
    before_json JSONB,
    after_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Track:

```text
material edits
shot edits
panel edits
deleted records
model runs
predictions
imports
```

---

## 14. Repository Structure

Recommended monorepo:

```text
ballistic-analytics-platform/
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   ├── base.py
│   │   │   └── models/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── materials.py
│   │   │       ├── ammunition.py
│   │   │       ├── panels.py
│   │   │       ├── shots.py
│   │   │       ├── imports.py
│   │   │       ├── analytics.py
│   │   │       └── predictions.py
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── import_service.py
│   │   │   ├── material_service.py
│   │   │   ├── analytics_service.py
│   │   │   ├── prediction_service.py
│   │   │   └── report_service.py
│   │   ├── modeling/
│   │   │   ├── features.py
│   │   │   ├── anova.py
│   │   │   ├── regression.py
│   │   │   ├── mixed_effects.py
│   │   │   ├── prediction.py
│   │   │   └── validation.py
│   │   └── tests/
│   └── migrations/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Materials.tsx
│   │   │   ├── MaterialDetail.tsx
│   │   │   ├── TestSessions.tsx
│   │   │   ├── Panels.tsx
│   │   │   ├── PanelBuilder.tsx
│   │   │   ├── Shots.tsx
│   │   │   ├── ImportSpreadsheet.tsx
│   │   │   ├── Analytics.tsx
│   │   │   ├── Predict.tsx
│   │   │   └── Reports.tsx
│   │   ├── routes/
│   │   ├── hooks/
│   │   ├── types/
│   │   └── utils/
├── storage/
│   ├── uploads/
│   ├── material_docs/
│   ├── reports/
│   └── model_artifacts/
└── docs/
    ├── data_dictionary.md
    ├── modeling_plan.md
    └── deployment.md
```

---

## 15. Docker Compose

Create a production-like local environment.

Services:

```text
postgres
backend
frontend
nginx
```

Example `docker-compose.yml` outline:

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ballistic
      POSTGRES_USER: ballistic_user
      POSTGRES_PASSWORD: change_me
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    env_file:
      - .env
    depends_on:
      - postgres
    volumes:
      - ./storage:/app/storage
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    depends_on:
      - backend
    ports:
      - "5173:5173"

volumes:
  postgres_data:
```

For production, put Nginx in front and enable HTTPS.

---

## 16. Environment Variables

Create `.env.example`:

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://ballistic_user:change_me@postgres:5432/ballistic
SECRET_KEY=replace_with_long_random_secret
ACCESS_TOKEN_EXPIRE_MINUTES=60
UPLOAD_DIR=/app/storage/uploads
MATERIAL_DOCS_DIR=/app/storage/material_docs
REPORTS_DIR=/app/storage/reports
MODEL_ARTIFACTS_DIR=/app/storage/model_artifacts
CORS_ORIGINS=http://localhost:5173
```

Never commit the real `.env`.

---

## 17. Initial Development Milestones

### Milestone 1: Skeleton App

Goal:

- React app loads
- FastAPI app loads
- PostgreSQL connects
- Docker Compose works
- User login works

Deliverables:

```text
login page
dashboard shell
database connection
first admin user
```

---

### Milestone 2: Core Data Models

Goal:

- Create database tables
- CRUD for materials, ammunition, test sessions, panels, shots

Deliverables:

```text
materials page
ammunition page
test sessions page
panel detail page
shots table
```

---

### Milestone 3: Spreadsheet Import

Goal:

- Upload `.xlsx` and `.csv`
- Preview data
- Map columns
- Validate rows
- Commit rows

Deliverables:

```text
import wizard
error report
stored original file
committed shots
```

---

### Milestone 4: Analytics

Goal:

- Summary statistics
- Charts
- ANOVA
- Regression

Deliverables:

```text
BFD vs velocity plot
BFD by ammunition
BFD by material class
ANOVA table
regression summary
```

---

### Milestone 5: Prediction Sandbox

Goal:

- Build theoretical panel
- Estimate BFD
- Show uncertainty and warnings

Deliverables:

```text
layer stack builder
calculated areal density
prediction output card
similar historical shots table
model version tracking
```

---

### Milestone 6: Reports and Hardening

Goal:

- Export reports
- Add audit logs
- Improve role permissions
- Backup process

Deliverables:

```text
PDF report
CSV export
audit log page
backup script
deployment docs
```

---

## 18. Backend Implementation Notes

### 18.1 Use Pydantic Schemas

For every entity:

```text
MaterialCreate
MaterialUpdate
MaterialRead
MaterialListItem
```

Do not return raw SQLAlchemy models directly.

---

### 18.2 Use Services

Keep business logic out of route files.

Example:

```text
routes/materials.py calls services/material_service.py
routes/analytics.py calls services/analytics_service.py
routes/predictions.py calls services/prediction_service.py
```

---

### 18.3 Import Service

The import service should:

1. Read spreadsheet.
2. Detect sheets.
3. Return preview.
4. Accept user column mapping.
5. Validate rows.
6. Commit rows in a transaction.
7. Roll back on critical errors.

Use:

```text
pandas
openpyxl
```

---

### 18.4 Analytics Service

Use:

```text
pandas
statsmodels
scipy
numpy
```

Initial ANOVA implementation:

```python
import statsmodels.api as sm
from statsmodels.formula.api import ols

model = ols(formula, data=df).fit()
anova_table = sm.stats.anova_lm(model, typ=2)
```

Mixed effects later:

```python
import statsmodels.formula.api as smf

model = smf.mixedlm(
    formula,
    data=df,
    groups=df["panel_id"]
).fit()
```

---

### 18.5 Prediction Service

First version:

1. Build feature row from user input.
2. Calculate derived variables.
3. Check extrapolation.
4. Load latest approved model.
5. Generate prediction.
6. Estimate prediction interval.
7. Find similar shots.
8. Save prediction.

---

## 19. Frontend Implementation Notes

### 19.1 UI Style

Use a clean technical dashboard style.

Preferred visual style:

```text
white or slate background
cards
tables
clear status badges
minimal color
high information density
```

Use shadcn/ui components:

```text
Card
Button
Input
Select
Table
Tabs
Dialog
Badge
Alert
Form
DropdownMenu
```

---

### 19.2 Important Components

Create reusable components:

```text
DataTable
MaterialSelector
AmmunitionSelector
LayerStackBuilder
ShotPatternViewer
BfdPredictionCard
ExtrapolationWarning
SimilarShotsTable
ModelVersionBadge
FileUploadDropzone
```

---

### 19.3 Charts

Use Recharts or Plotly.

Needed charts:

```text
scatter: BFD vs velocity
boxplot: BFD by ammunition
boxplot: BFD by material class
bar: penetration rate by ammunition
line: test volume over time
histogram: BFD distribution
residual plot
```

Plotly may be better for scientific charting because it supports interactive hover, box plots, and exports.

---

## 20. Data Quality Rules

Flag but do not always block:

```text
missing BFD
missing velocity
unknown ammunition
unknown material
duplicate shot number within panel
BFD below 0
BFD above 100 mm
velocity below expected threat range
velocity above expected threat range
penetration but BFD recorded
no penetration but missing BFD
```

Use severity:

```text
info
warning
error
critical
```

---

## 21. Report Requirements

Prediction reports should include:

```text
input configuration
layer stack
calculated total thickness
calculated total areal density
ammunition
velocity
predicted BFD
prediction interval
penetration probability
model version
comparable historical shots
warnings
disclaimer
```

Disclaimer:

```text
This estimate is for internal research and development use only. It is not a certification result and does not replace formal ballistic testing under applicable standards.
```

---

## 22. Testing Requirements

### Backend Tests

Use:

```text
pytest
```

Test:

```text
material CRUD
ammunition CRUD
panel layer calculations
spreadsheet import validation
ANOVA endpoint
prediction endpoint
auth permissions
```

### Frontend Tests

Use:

```text
Vitest
React Testing Library
Playwright later
```

Test:

```text
login flow
material form
layer builder calculations
spreadsheet import wizard
prediction form
```

---

## 23. Backup Plan

For private R&D data, backups are mandatory.

Minimum:

```text
daily PostgreSQL dump
daily storage folder backup
weekly offsite encrypted backup
restore test monthly
```

Create script:

```text
scripts/backup.sh
```

Backup should include:

```text
database dump
uploaded files
material documents
model artifacts
reports
```

---

## 24. Important Modeling Cautions

1. Do not treat multiple shots on the same panel as fully independent.
2. Do not trust predictions outside the tested material/threat range.
3. Do not combine penetration and BFD into one outcome.
4. Do not ignore velocity.
5. Do not ignore shot placement.
6. Do not use layer count alone; use areal density and thickness.
7. Track model version for every prediction.
8. Store enough metadata to reproduce results.
9. Use prediction intervals, not just fitted means.
10. Keep a human-readable explanation of why a prediction may be unreliable.

---

## 25. Suggested Coding Assistant Prompt

Use the following prompt in Claude, Windsurf, or Cursor:

```text
You are building a private ballistic test analytics platform.

Use this Markdown specification as the source of truth.

Create a monorepo with:
- React + TypeScript + Vite frontend
- Tailwind CSS and shadcn/ui
- Python FastAPI backend
- SQLAlchemy 2.x
- Alembic migrations
- PostgreSQL
- Docker Compose

Start by implementing:
1. Project skeleton
2. Docker Compose
3. Backend database models
4. User authentication
5. CRUD APIs for materials, ammunition, test sessions, panels, panel layers, and shots
6. React routes and pages for dashboard, materials, ammunition, panels, shots, import, analytics, and prediction
7. Basic spreadsheet upload and preview
8. Basic layer-stack calculator

Prioritize clean architecture, type safety, validation, and maintainability.
Do not add fake ballistic claims.
Do not hard-code proprietary data.
Do not expose unauthenticated endpoints.
Use placeholder data only for local development.
```

---

## 26. Suggested First Commands

```bash
mkdir ballistic-analytics-platform
cd ballistic-analytics-platform

mkdir backend frontend storage docs scripts

git init
```

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn sqlalchemy alembic psycopg[binary] pydantic pandas openpyxl statsmodels scikit-learn python-multipart passlib[bcrypt] python-jose
pip freeze > requirements.txt
```

Frontend:

```bash
cd ../frontend
npm create vite@latest . -- --template react-ts
npm install
npm install @tanstack/react-query @tanstack/react-table react-router-dom zod react-hook-form @hookform/resolvers recharts lucide-react
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

---

## 27. Minimal Viable Product Definition

The MVP is complete when a user can:

1. Log in.
2. Create materials.
3. Create ammunition records.
4. Create a test session.
5. Create a panel with layers.
6. Enter shot data manually.
7. Upload a spreadsheet and preview rows.
8. View BFD vs velocity.
9. Run a basic ANOVA.
10. Build a theoretical layer stack.
11. Receive a basic BFD prediction with warnings.
12. Export a simple report.

---

## 28. Future Enhancements

Possible later features:

```text
PDF parsing for material specification sheets
automatic manufacturer extraction
image-based shot placement maps
Bayesian hierarchical modeling
active learning test recommendations
report templates
material similarity search
model comparison dashboard
NIJ-style protocol templates
multi-lab support
barcode / QR code labels for panels
chain-of-custody logs
electronic lab notebook integration
Google Drive read-only integration
Gmail attachment ingestion
role-specific dashboards
```

---

## 29. Product Philosophy

The platform should not be a spreadsheet replacement only.

It should become:

```text
a structured ballistic test database
a material intelligence system
a statistical analysis tool
a predictive R&D sandbox
a reproducible reporting engine
```

The most important design principle is traceability.

Every result should answer:

```text
What data was used?
What model was used?
What assumptions were made?
How uncertain is the result?
Is this prediction inside or outside the tested data range?
Can we reproduce this later?
```
