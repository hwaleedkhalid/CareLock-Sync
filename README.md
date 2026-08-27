# CareLock Sync

<div align="center">

**Intelligent Hospital Database Synchronization with Real-Time CDC & AI-Powered FHIR Mapping**

> Final Year Project — BS Computer Science  
> Bahria University Lahore Campus  
> **Team:** Waleed Khalid · Muhammad Mohsin · Shahmeer Nadeem  
> **Supervisor:** Dr. Muhammad Saqib Sohail

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Status](https://img.shields.io/badge/status-Complete-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![React](https://img.shields.io/badge/React-19-61DAFB)
![FHIR](https://img.shields.io/badge/FHIR-R4-orange)

</div>

---

## Table of Contents

1. [Project Overview](#-project-overview)
2. [Architecture](#-architecture)
3. [Tech Stack](#-tech-stack)
4. [File Structure](#-file-structure)
5. [Prerequisites](#-prerequisites)
6. [How to Run](#-how-to-run)
7. [Environment Variables](#-environment-variables)
8. [API Reference](#-api-reference)
9. [Frontend Pages & Dashboards](#-frontend-pages--dashboards)
10. [RAG Pipeline](#-rag-pipeline)
11. [CDC Pipeline](#-cdc-pipeline)
12. [Demo Credentials](#-demo-credentials)
13. [Team](#-team)

---

## Project Overview

CareLock Sync is a full-stack healthcare data integration platform. Hospitals connect their existing databases and the system automatically:

- **Discovers** the database schema without any manual configuration
- **Captures changes** in real-time using PostgreSQL CDC (Change Data Capture) triggers
- **Maps fields** to FHIR R4 using a local AI engine powered by Ollama + ChromaDB
- **Synchronises** data into a tenant-isolated central FHIR database
- **Presents** data through 4 role-based dashboards (Super Admin, Hospital, Doctor, Analyst)

All of this happens continuously and automatically after a hospital completes the 5-step onboarding wizard.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Hospital Database  (:5435)                       │
│              PostgreSQL — patients, encounters, lab_results,         │
│                         medications tables                           │
└───────────────────────┬─────────────────────────────────────────────┘
                        │  INSERT / UPDATE / DELETE
                        ▼
               CDC Triggers fire
               → writes to data_change_log
                        │
                        ▼
        ┌───────────────────────────────┐
        │     CDC Worker  (:9101)       │  polls data_change_log
        │  LISTEN/NOTIFY + polling      │  every 5s or on notify
        │  HMAC-signs each batch        │
        └───────────────┬───────────────┘
                        │  HMAC-signed HTTP POST
                        ▼
        ┌───────────────────────────────┐
        │   Ingestion Service  (:8004)  │  verifies HMAC signature
        │   FastAPI microservice        │  writes to cdc_inbox
        └───────────────┬───────────────┘
                        │
                        ▼
                   cdc_inbox table
               (shared PostgreSQL :5433)
                        │
                        ▼
        ┌───────────────────────────────┐
        │    ETL Worker  (:9201)        │  FOR UPDATE SKIP LOCKED
        │  claim → apply → mark done    │  exponential backoff
        │  IncrementalSync handlers     │  dead-letter queue
        └───────────────┬───────────────┘
                        │  FHIR Mapping Engine
                        ▼
        ┌───────────────────────────────────────────────────┐
        │           Shared FHIR Database  (:5433)           │
        │   fhir_patient  fhir_encounter  fhir_observation   │
        │   fhir_medication   (per-tenant RLS enforced)      │
        └───────────────────────┬───────────────────────────┘
                                │
                                ▼
             ┌──────────────────────────────────┐
             │      API Server  (:8003)          │
             │   FastAPI — 40+ REST endpoints    │
             │   Auth, FHIR queries, sync ctrl   │
             └──────────────────┬───────────────┘
                                │
                                ▼
             ┌──────────────────────────────────┐
             │   React Frontend  (:5173 dev)     │
             │  4 role dashboards + public pages │
             └──────────────────────────────────┘
```

---

## Tech Stack

### Backend
| Component | Technology |
|---|---|
| API Framework | Python 3.10, FastAPI 0.104, Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Validation | Pydantic 2.5 |
| Databases | PostgreSQL 15 (hospital `:5435`, shared `:5433`) |
| CDC | PostgreSQL triggers + `data_change_log` table |
| Auth | JWT-based authentication |
| Encryption | AES-256 (PHI fields), HMAC-SHA256 (CDC signing) |
| Multi-DB | PostgreSQL, MySQL, MongoDB, SQL Server, Oracle adapters |

### AI / RAG System
| Component | Technology |
|---|---|
| Vector Database | ChromaDB 0.4.22 (HNSW cosine index, persistent) |
| Embedding Model | `nomic-embed-text` via Ollama |
| Embedding Fallback | SHA-512 deterministic hash (works offline, 768-dim) |
| Mapping LLM | `llama3.2:3b` via Ollama (temperature 0.05) |
| Chatbot LLM | `phi3` via Ollama |
| Cloud Backup | Google Gemini API (`gemini-2.5-flash`) |
| Orchestration | 100% custom — direct HTTP to Ollama REST, no LangChain |
| Knowledge Base | 163+ hand-crafted FHIR R4 ground-truth mappings |

### Frontend
| Component | Technology |
|---|---|
| Framework | React 19, TypeScript 5.9, Vite 7 |
| Routing | React Router DOM v7 |
| Data Fetching | TanStack Query v5 + custom `apiClient` |
| Charts | Recharts 3 |
| Forms | React Hook Form 7 |
| Icons | Lucide React |
| Styling | Custom dark glassmorphism design system + Tailwind CSS 4 |

---

## File Structure

```
CareLock-Sync/
│
├── README.md
├── docker-compose.yml              ← Production compose
├── docker-compose-demo.yml         ← Demo environment
├── docker/
│   └── docker-compose.dev.yml      ← Development databases only
│
├── start_all_services.bat          ← Start all 4 backend services (Windows)
├── START_SERVICES.ps1              ← PowerShell alternative
├── STOP_SERVICES.ps1               ← Stop all services
├── START_DEMO.bat                  ← Quick demo launcher
│
├── config/
│   ├── cdc_sources.yaml            ← CDC source definitions (hospital connections)
│   ├── cdc_sources.yaml.example    ← Template for adding new hospitals
│   └── sync_config.json            ← Sync scheduling configuration
│
├── certs/
│   ├── server.crt                  ← TLS certificate
│   └── server.key                  ← TLS private key
│
├── databases/
│   ├── hospital-dbs/
│   │   ├── 01_schema.sql           ← Hospital DB schema (patients, encounters, labs, meds)
│   │   └── fix_cdc_tenant.sql      ← CDC trigger fix migration
│   ├── shared-db/
│   │   ├── 01_fhir_schema.sql      ← FHIR output tables
│   │   ├── 01_init_schema.sql      ← Core shared DB schema
│   │   ├── p1_tables.sql           ← cdc_inbox, cdc_dead_letter, cdc_watermarks
│   │   ├── p1_step1_triggers.sql   ← Trigger setup
│   │   ├── p1_step4_rls.sql        ← Row-Level Security policies
│   │   ├── sprint3_api_keys.sql    ← API key management
│   │   └── sprint5_sync_idempotency.sql
│   └── chroma/                     ← ChromaDB vector store (auto-created)
│
├── docs/
│   ├── README_CDC_V3.md
│   ├── SPRINT4_V2_GUIDE.md
│   └── security/
│       └── INCIDENT_RESPONSE_PLAN.md
│
│
├── backend/
│   ├── run_server.py               ← Entry point: starts API on :8003
│   ├── requirements.txt            ← Python dependencies
│   ├── .env                        ← Backend environment variables
│   │
│   ├── api/
│   │   ├── main.py                 ← FastAPI app factory + startup hooks
│   │   ├── dependencies.py         ← Shared DI: DB sessions, auth
│   │   └── routes/
│   │       ├── auth.py             ← POST /api/v1/auth/login, /me, /logout
│   │       ├── patients.py         ← GET/POST /api/v1/patients
│   │       ├── sync.py             ← GET/POST /api/v1/sync/*
│   │       ├── status.py           ← GET /api/v1/system/status, /metrics
│   │       ├── rag.py              ← POST /api/v1/rag/suggest/*, /chat
│   │       ├── connector.py        ← GET /api/v1/connector/schema, /health
│   │       ├── fhir_routes.py      ← FHIR resource endpoints
│   │       └── dashboard_routes.py ← Dashboard aggregation endpoints
│   │
│   ├── common/
│   │   ├── models.py               ← SQLAlchemy models (Patient, Encounter, LabResult, Medication)
│   │   ├── models_multitenant.py   ← Multi-tenant FHIR output models
│   │   ├── schemas.py              ← Pydantic request/response schemas
│   │   ├── database.py             ← DB engine factory, session management
│   │   ├── auth.py                 ← JWT creation, verification
│   │   ├── config.py               ← Settings from env vars
│   │   ├── sync_store.py           ← sync_runs table read/write
│   │   ├── tenant_context.py       ← RLS tenant context setter
│   │   ├── tenant_manager.py       ← Tenant CRUD operations
│   │   └── event_log.py            ← Audit event logging
│   │
│   ├── rag/
│   │   ├── mapping_suggester.py    ← Main RAG orchestrator
│   │   ├── vector_store.py         ← ChromaDB wrapper (add/query mappings)
│   │   ├── ollama_client.py        ← Ollama HTTP client + 4-strategy JSON parser
│   │   ├── gemini_client.py        ← Google Gemini fallback client
│   │   ├── fhir_knowledge.py       ← 163+ ground-truth FHIR training mappings
│   │   └── tenant_aware_vector_store.py  ← Per-tenant vector isolation
│   │
│   ├── etl/
│   │   ├── incremental_sync.py     ← Per-record FHIR write handlers
│   │   ├── pipeline.py             ← Full sync pipeline
│   │   └── multi_db_pipeline.py    ← Multi-database ETL pipeline
│   │
│   ├── schema_mapper/
│   │   ├── mapping_service.py      ← Orchestrates hospital→FHIR mapping
│   │   ├── data_transformer.py     ← FHIRMapper: applies field transformations
│   │   ├── mapping_config.py       ← Loads fhir_mappings.json
│   │   └── fhir_mappings.json      ← Field mapping rules (Patient/Encounter/Observation/Medication)
│   │
│   ├── cdc/
│   │   ├── cdc_agent.py            ← CDC polling agent
│   │   ├── base_adapter.py         ← Abstract CDC adapter interface
│   │   ├── adapter_factory.py      ← Returns correct adapter by DB type
│   │   ├── postgresql_adapter.py   ← PostgreSQL LISTEN/NOTIFY + trigger adapter
│   │   ├── mysql_adapter.py        ← MySQL binlog adapter
│   │   ├── mongodb_adapter.py      ← MongoDB change streams adapter
│   │   ├── sqlserver_adapter.py    ← SQL Server CDC adapter
│   │   └── oracle_adapter.py       ← Oracle LogMiner adapter
│   │
│   ├── connector/
│   │   ├── schema_discovery.py     ← Auto-discovers tables & columns
│   │   ├── cdc_monitor.py          ← Connection health monitoring
│   │   └── hospital_schema.json    ← Cached schema snapshot
│   │
│   ├── services/
│   │   ├── cdc_worker/
│   │   │   ├── __main__.py         ← Entry: python -m services.cdc_worker --source hospital_a
│   │   │   ├── worker.py           ← CDC polling loop (reads data_change_log)
│   │   │   └── admin.py            ← Admin HTTP server on :9101
│   │   │
│   │   ├── etl_worker/
│   │   │   ├── __main__.py         ← Entry: python -m services.etl_worker
│   │   │   ├── worker.py           ← ETL claim loop (FOR UPDATE SKIP LOCKED)
│   │   │   └── admin.py            ← Admin HTTP server on :9201
│   │   │
│   │   ├── ingestion/
│   │   │   ├── app.py              ← FastAPI ingestion service on :8004
│   │   │   └── routes.py           ← POST /api/v1/cdc/ingest, GET /healthz
│   │   │
│   │   ├── common/
│   │   │   ├── backoff.py          ← Exponential backoff with jitter
│   │   │   ├── config.py           ← Shared service config (DB URLs)
│   │   │   ├── hmac_sign.py        ← HMAC-SHA256 signing & verification
│   │   │   └── schema.py           ← Shared Pydantic schemas for CDC events
│   │   │
│   │   └── cdc_metrics.py          ← CDC stats: error_rate, throughput, queue_depth
│   │
│   ├── security/
│   │   ├── encryption.py           ← AES-256 PHI field encryption
│   │   ├── enhanced_encryption.py  ← Enhanced encryption utilities
│   │   ├── mfa.py                  ← TOTP-based MFA
│   │   ├── rate_limiter.py         ← API rate limiting
│   │   ├── tls_config.py           ← TLS configuration
│   │   └── production_encryption.py
│   │
│   ├── scheduler/
│   │   └── sync_scheduler.py       ← Cron-based sync scheduling
│   │
│   ├── migrations/
│   │   ├── add_multi_tenancy.py    ← Multi-tenancy migration script
│   │   └── add_encryption_columns.py
│   │
│   └── scripts/
│       ├── seed_all_dbs.py         ← Seed hospital DB with sample data
│       ├── full_benchmark.py       ← Performance benchmark suite
│       ├── full_system_benchmark.py
│       ├── verify_adapters.py      ← Verify DB adapter connections
│       └── verify_load_data.py     ← Verify seeded data
│
│
└── frontend-app/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── .env                        ← VITE_API_BASE_URL etc.
    │
    └── src/
        ├── App.tsx                 ← Root router (all routes defined here)
        ├── main.tsx                ← React entry point
        ├── index.css               ← Global styles + design system tokens
        │
        ├── public-site/
        │   └── pages/
        │       └── HomePage.tsx    ← Landing page (route: /)
        │
        ├── pages/
        │   ├── HospitalOnboardingPage.tsx  ← 5-step onboarding wizard (route: /onboarding)
        │   ├── SystemDemoPage.tsx          ← Legacy demo page (route: /demo)
        │   ├── AIMappingPage.tsx
        │   ├── ChatPage.tsx
        │   ├── DashboardPage.tsx
        │   ├── DataQualityPage.tsx
        │   ├── EncountersPage.tsx
        │   ├── LoginPage.tsx
        │   ├── MonitoringPage.tsx
        │   ├── PatientDetailPage.tsx
        │   ├── PatientsPage.tsx
        │   ├── ResearchPage.tsx
        │   ├── SecurityDashboardPage.tsx
        │   └── SimulationLabPage.tsx
        │
        ├── auth-portal/
        │   ├── RoleSelectorPage.tsx  ← Role selection (route: /auth/role)
        │   └── LoginPage.tsx         ← Login form (route: /auth/login)
        │
        ├── dashboards/
        │   │
        │   ├── admin/                ← Super Admin dashboard (route: /admin/*)
        │   │   ├── AdminLayout.tsx
        │   │   ├── components/
        │   │   │   ├── ActivityPanel.tsx
        │   │   │   ├── AdminActions.tsx
        │   │   │   ├── AdminCharts.tsx
        │   │   │   ├── CDCSourcesGrid.tsx
        │   │   │   ├── DataQualityPanel.tsx
        │   │   │   ├── KpiCard.tsx
        │   │   │   ├── SyncOperationsTable.tsx
        │   │   │   ├── SyncStatusPanel.tsx
        │   │   │   ├── SystemHealthPanel.tsx
        │   │   │   ├── SystemInsights.tsx
        │   │   │   └── TenantTable.tsx
        │   │   ├── hooks/
        │   │   │   └── useDashboardData.ts
        │   │   └── pages/
        │   │       ├── AdminDashboard.tsx      ← /admin/system-health
        │   │       ├── SyncAnalyticsPage.tsx   ← /admin/sync-analytics
        │   │       ├── TenantManagementPage.tsx ← /admin/tenants
        │   │       ├── MappingReviewPage.tsx   ← /admin/mapping
        │   │       ├── SecurityCenterPage.tsx  ← /admin/security
        │   │       ├── BenchmarkCenterPage.tsx ← /admin/benchmark
        │   │       ├── AuditLogsPage.tsx
        │   │       ├── ChatPage.tsx
        │   │       ├── DataQualityPage.tsx
        │   │       ├── MonitoringPage.tsx
        │   │       ├── ResearchPage.tsx
        │   │       ├── AdminSettingsPage.tsx
        │   │       └── SimulationPage.tsx
        │   │
        │   ├── hospital/             ← Hospital Admin dashboard (route: /hospital/*)
        │   │   ├── HospitalLayout.tsx
        │   │   └── pages/
        │   │       ├── HospitalDashboard.tsx   ← /hospital/dashboard
        │   │       ├── DataSourcesPage.tsx     ← /hospital/data-sources
        │   │       ├── SyncReportPage.tsx      ← /hospital/sync-report
        │   │       ├── MappingReviewPage.tsx   ← /hospital/mapping
        │   │       ├── PatientsPage.tsx        ← /hospital/patients
        │   │       └── EncountersPage.tsx      ← /hospital/encounters
        │   │
        │   ├── doctor/               ← Doctor dashboard (route: /doctor/*)
        │   │   ├── DoctorLayout.tsx
        │   │   └── pages/
        │   │       ├── DoctorDashboard.tsx     ← /doctor/dashboard
        │   │       ├── PatientsPage.tsx        ← /doctor/patients
        │   │       ├── PatientDetailPage.tsx   ← /doctor/patients/:id
        │   │       ├── EncountersPage.tsx      ← /doctor/encounters
        │   │       └── ChatPage.tsx            ← /doctor/chat  (AI assistant)
        │   │
        │   └── analyst/              ← Analyst dashboard (route: /analyst/*)
        │       ├── AnalystLayout.tsx
        │       └── pages/
        │           ├── AnalystDashboard.tsx    ← /analyst/dashboard
        │           ├── DataQualityPage.tsx     ← /analyst/data-quality
        │           ├── ResearchPage.tsx        ← /analyst/research
        │           └── ChatPage.tsx            ← /analyst/chat  (AI assistant)
        │
        └── shared/
            ├── components/
            │   ├── AuthGuard.tsx
            │   ├── GlobalErrorBoundary.tsx
            │   └── ErrorFallback.tsx
            ├── constants/
            │   └── routes.ts           ← All route constants (PUBLIC_ROUTES, NAV_BUTTONS)
            ├── context/
            │   ├── AuthContext.tsx     ← JWT auth state + login/logout
            │   ├── ThemeContext.tsx    ← Light/dark theme toggle
            │   └── BackendStatusContext.tsx  ← API health banner
            ├── hooks/
            │   ├── index.ts
            │   ├── useApiData.ts       ← Generic data fetch hook with SWR pattern
            │   └── useTimeSeries.ts    ← Time-series chart data hook
            ├── services/
            │   ├── apiClient.ts        ← Fetch-based HTTP client with auto auth headers
            │   └── api.ts              ← Typed API function wrappers
            ├── types/
            │   └── index.ts            ← Shared TypeScript interfaces
            ├── ui/
            │   ├── ErrorBanner.tsx
            │   ├── LoadingSpinner.tsx
            │   ├── MetricsBadgeSummary.tsx
            │   ├── StatCard.tsx
            │   ├── SuspenseFallback.tsx
            │   └── ThemeToggle.tsx
            └── utils/
                ├── apiNormalizers.ts   ← Normalize inconsistent API responses
                ├── formatters.ts       ← Date, number, duration formatters
                └── mappers.ts          ← Map API responses to UI models
```

---

## Prerequisites

Before running the project, install the following:

| Requirement | Version | Download |
|---|---|---|
| Python | 3.10+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| Docker Desktop | Latest | https://docker.com |
| Ollama | Latest | https://ollama.com |
| Git | Any | https://git-scm.com |

> **Windows users:** All commands below are for PowerShell or Command Prompt.

---

## How to Run

### Step 1 — Clone the Repository

```bash
git clone <repo-url>
cd CareLock-Sync
```

---

### Step 2 — Start the Databases

The project uses two PostgreSQL instances managed by Docker.

```powershell
docker-compose -f docker/docker-compose.dev.yml up -d
```

This starts:
| Container | Port | Purpose |
|---|---|---|
| `hospital_db` | `5435` | Hospital source database (patients, encounters, labs, medications) |
| `carelock_shared` | `5433` | Shared FHIR output database (cdc_inbox, fhir_* tables) |
| `pgAdmin` | `5050` | Database management UI |

Verify containers are running:
```powershell
docker ps
```

---

### Step 3 — Set Up Python Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.\venv\Scripts\activate.bat

# Install dependencies
pip install -r backend/requirements.txt
```

---

### Step 4 — Configure Environment Variables

Copy the example env file and update values:

```powershell
copy backend\.env.example backend\.env
```

The default `backend/.env` should contain:

```env
# Database connections
HOSPITAL_DB_URL=postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db
SHARED_DB_URL=postgresql://shared_user:shared_pass@localhost:5433/carelock_shared

# JWT Auth
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# CDC HMAC Authentication
CDC_HMAC_KEYS=hospital_a:carelock-cdc-2024
CDC_HMAC_KEY_HOSPITAL_A=carelock-cdc-2024
CDC_REGISTRY_AUTO_STUB=true

# AI / RAG
OLLAMA_BASE_URL=http://localhost:11434
MAPPING_MODEL=llama3.2:3b
CHAT_MODEL=phi3
CHROMA_PATH=./databases/chroma

# Optional: Google Gemini fallback
GEMINI_API_KEY=

# Logging
LOG_LEVEL=INFO
```

---

### Step 5 — Initialize the Databases

Run the schema SQL files to create all tables:

```powershell
# Hospital DB schema (patients, encounters, lab_results, medications, CDC tables)
docker exec -i hospital_db psql -U hospital_user -d hospital_db < databases/hospital-dbs/01_schema.sql

# Shared FHIR DB schema (cdc_inbox, fhir_patient, fhir_encounter, etc.)
docker exec -i carelock_shared psql -U shared_user -d carelock_shared < databases/shared-db/01_init_schema.sql
docker exec -i carelock_shared psql -U shared_user -d carelock_shared < databases/shared-db/01_fhir_schema.sql
docker exec -i carelock_shared psql -U shared_user -d carelock_shared < databases/shared-db/p1_tables.sql
docker exec -i carelock_shared psql -U shared_user -d carelock_shared < databases/shared-db/p1_step4_rls.sql
```

Seed the hospital database with sample data:

```powershell
cd backend
python scripts/seed_all_dbs.py
```

---

### Step 6 — Pull Ollama Models (for AI/RAG features)

```powershell
# Embedding model
ollama pull nomic-embed-text

# Mapping LLM (field-to-FHIR suggestions)
ollama pull llama3.2:3b

# Chatbot LLM (FHIR Q&A assistant)
ollama pull phi3
```

Verify Ollama is running:
```powershell
curl http://localhost:11434/api/tags
```

> **Note:** If you skip this step, the system still works — the RAG engine will use SHA-512 hash embeddings as a fallback and will skip LLM generation. All other features remain fully functional.

---

### Step 7 — Start All Backend Services

**Option A — Recommended (one command, opens 4 terminal windows):**

```powershell
.\start_all_services.bat
```

**Option B — Start each service manually in separate terminals:**

```powershell
# Terminal 1 — API Server (port 8003)
cd backend
set HOSPITAL_DB_URL=postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db
set SHARED_DB_URL=postgresql://shared_user:shared_pass@localhost:5433/carelock_shared
python run_server.py

# Terminal 2 — CDC Ingestion Service (port 8004)
cd backend
set HOSPITAL_DB_URL=postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db
set SHARED_DB_URL=postgresql://shared_user:shared_pass@localhost:5433/carelock_shared
set CDC_HMAC_KEYS=hospital_a:carelock-cdc-2024
python -m uvicorn services.ingestion.app:app --host 0.0.0.0 --port 8004

# Terminal 3 — CDC Worker (monitors hospital_a database)
cd backend
set HOSPITAL_DB_URL=postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db
set SHARED_DB_URL=postgresql://shared_user:shared_pass@localhost:5433/carelock_shared
set CDC_HMAC_KEY_HOSPITAL_A=carelock-cdc-2024
set CDC_REGISTRY_AUTO_STUB=true
python -m services.cdc_worker --source hospital_a

# Terminal 4 — ETL Worker (processes cdc_inbox, writes FHIR)
cd backend
set HOSPITAL_DB_URL=postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db
set SHARED_DB_URL=postgresql://shared_user:shared_pass@localhost:5433/carelock_shared
python -m services.etl_worker
```

**Verify all services are up:**

```powershell
# API Server
curl http://localhost:8003/api/v1/system/status

# Ingestion Service
curl http://localhost:8004/healthz

# CDC Worker
curl http://localhost:9101/status

# ETL Worker
curl http://localhost:9201/status
```

---

### Step 8 — Start the Frontend

```powershell
cd frontend-app

# Install dependencies (first time only)
npm install

# Start development server
npm run dev
```

Frontend available at: **http://localhost:5173**

To build for production:
```powershell
npm run build
npm run preview    # preview production build locally
```

---

### All Running Services Summary

| Service | URL | Description |
|---|---|---|
| Frontend | http://localhost:5173 | React app |
| API Server | http://localhost:8003 | FastAPI REST API |
| API Docs | http://localhost:8003/docs | Swagger interactive docs |
| CDC Ingestion | http://localhost:8004/healthz | CDC event receiver |
| CDC Worker Admin | http://localhost:9101/status | CDC worker status |
| ETL Worker Admin | http://localhost:9201/status | ETL worker status |
| pgAdmin | http://localhost:5050 | Database management UI |

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `HOSPITAL_DB_URL` | `postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db` | Hospital source database |
| `SHARED_DB_URL` | `postgresql://shared_user:shared_pass@localhost:5433/carelock_shared` | Shared FHIR database |
| `SECRET_KEY` | *(set this)* | JWT signing secret |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT token expiry |
| `CDC_HMAC_KEYS` | `hospital_a:carelock-cdc-2024` | Ingestion service HMAC keys |
| `CDC_HMAC_KEY_HOSPITAL_A` | `carelock-cdc-2024` | CDC worker HMAC key for hospital_a |
| `CDC_REGISTRY_AUTO_STUB` | `true` | Auto-create registry entries for new tables |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `MAPPING_MODEL` | `llama3.2:3b` | LLM for field mapping suggestions |
| `CHAT_MODEL` | `phi3` | LLM for FHIR chatbot |
| `CHROMA_PATH` | `./databases/chroma` | ChromaDB persistence path |
| `GEMINI_API_KEY` | *(optional)* | Google Gemini API key (cloud backup) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ETL_BATCH_SIZE` | `200` | ETL rows claimed per batch |
| `ETL_MAX_ATTEMPTS` | `8` | Max retry attempts before DLQ |
| `ETL_CLAIM_TIMEOUT_SECONDS` | `120` | Reclaim stuck rows after N seconds |

### Frontend (`frontend-app/.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8003` | Backend API base URL |

---

## API Reference

### Authentication
```
POST  /api/v1/auth/login          Body: { username, password }  → { access_token }
GET   /api/v1/auth/me             → Current user info
POST  /api/v1/auth/logout
```

### System
```
GET   /api/v1/system/status       → DB connections, record counts, uptime
GET   /api/v1/system/metrics      → CDC throughput, error_rate, queue_depth, active_sources
```

### Sync
```
GET   /api/v1/sync/status         → is_syncing, progress, total_syncs
POST  /api/v1/sync/trigger        → Manually trigger a sync run
GET   /api/v1/sync/history        → List of past sync runs with duration & record counts
```

### Clinical Data
```
GET   /api/v1/patients            → Paginated patient list  (?limit=&offset=)
GET   /api/v1/patients/{id}       → Single patient detail
POST  /api/v1/patients            → Create patient

GET   /api/v1/encounters          → Paginated encounter list
GET   /api/v1/encounters/{id}

GET   /api/v1/lab-results         → Paginated lab results
GET   /api/v1/medications         → Paginated medications
```

### FHIR
```
GET   /api/v1/fhir/patient/{id}   → FHIR R4 Patient resource (JSON)
GET   /api/v1/fhir/bundle/{id}    → Full FHIR Bundle for patient (all resources)
```

### Tenants (Hospital Onboarding)
```
GET   /api/v1/tenants             → List all hospital tenants
POST  /api/v1/tenants             → Onboard new hospital
GET   /api/v1/tenants/{id}
```

### Connector
```
GET   /api/v1/connector/health    → Hospital DB connection health
GET   /api/v1/connector/schema    → Auto-detect hospital DB schema (tables + columns)
```

### RAG (AI Mapping)
```
POST  /api/v1/rag/suggest/field   → AI mapping for a single field
      Body: { field_name, field_type, fhir_resource, sample_values? }

POST  /api/v1/rag/suggest/schema  → AI mapping for a full table schema
      Body: { table_name, columns: [{name, type}], fhir_resource }

POST  /api/v1/rag/mappings/confirm-batch  → Save confirmed mappings to vector store
POST  /api/v1/rag/chat            → FHIR Q&A chatbot
      Body: { question, context? }

GET   /api/v1/rag/status          → RAG engine state (uninitialized|initializing|ready|error)
GET   /api/v1/rag/knowledge/stats → Knowledge base stats (total mappings, resources covered)
```

---

## Frontend Pages & Dashboards

### Public (no login required)

| Route | Page | Description |
|---|---|---|
| `/` | Landing Page | Marketing homepage with features, Get Started CTA |
| `/onboarding` | Hospital Onboarding | 5-step wizard: hospital info → DB connection → schema detection → AI mapping → launch |

### Authentication

| Route | Page |
|---|---|
| `/auth/role` | Role selector (Admin / Hospital / Doctor / Analyst) |
| `/auth/login` | Login form |

### Super Admin Dashboard (`/admin/*`)

| Route | Page | Key Features |
|---|---|---|
| `/admin/system-health` | System Health | DB status, CDC metrics, KPI cards, activity feed |
| `/admin/sync-analytics` | Sync Analytics | Sync history charts, throughput, error rate, duration trends |
| `/admin/tenants` | Tenant Management | Hospital list, onboard wizard, CDC status per hospital |
| `/admin/mapping` | Mapping Review | Review & confirm AI-generated FHIR field mappings |
| `/admin/security` | Security Center | Encryption status, audit logs, rate limiting |
| `/admin/benchmark` | Benchmark Center | Performance benchmarks, throughput testing |

### Hospital Admin Dashboard (`/hospital/*`)

| Route | Page | Key Features |
|---|---|---|
| `/hospital/dashboard` | Hospital Dashboard | Connected DB status, sync status, patient counts |
| `/hospital/data-sources` | Data Sources | DB connection details, CDC trigger status |
| `/hospital/sync-report` | Sync Report | Per-table sync history and error details |
| `/hospital/mapping` | Mapping Review | Field mapping status for this hospital |
| `/hospital/patients` | Patients | Paginated patient list with FHIR data |
| `/hospital/encounters` | Encounters | Patient encounter records |

### Doctor Dashboard (`/doctor/*`)

| Route | Page |
|---|---|
| `/doctor/dashboard` | Overview with recent patients and activity |
| `/doctor/patients` | Patient list with search |
| `/doctor/patients/:id` | Full patient detail with FHIR data |
| `/doctor/encounters` | Encounter records |
| `/doctor/chat` | AI assistant (phi3-powered FHIR Q&A) |

### Analyst Dashboard (`/analyst/*`)

| Route | Page |
|---|---|
| `/analyst/dashboard` | Data quality overview |
| `/analyst/data-quality` | FHIR completeness metrics, anomaly detection |
| `/analyst/research` | Cross-hospital aggregate queries |
| `/analyst/chat` | AI research assistant |

---

## RAG Pipeline

The AI mapping engine is built from scratch — no LangChain or LlamaIndex. It runs entirely locally via Ollama.

```
POST /api/v1/rag/suggest/field
        │
        ▼
1. EMBED the field name
   "date_of_birth" → POST http://localhost:11434/api/embeddings
                        model: nomic-embed-text
                     → 768-dim float vector
                     (fallback: SHA-512 hash embedding if Ollama is offline)
        │
        ▼
2. VECTOR SEARCH in ChromaDB
   query_embeddings=[...] WHERE fhir_resource = "Patient"
   → top-5 results by cosine similarity
        │
        ├── similarity >= 0.88?
        │   YES → return ChromaDB result directly  (LLM skipped — fast path)
        │
        └── similarity < 0.88?
            YES → call LLM
                │
                ▼
3. LLM GENERATION
   POST http://localhost:11434/api/generate
        model: llama3.2:3b
        temperature: 0.05
        prompt: "Map column date_of_birth (date) to FHIR R4 Patient.
                 Known mappings: dob → Patient.birthDate
                 OUTPUT: {target_path, confidence, reasoning, transformation}"
        │
        ▼
4. JSON PARSING (4-strategy fault tolerance)
   Strategy 1: json.loads(raw)
   Strategy 2: regex find {…} in prose
   Strategy 3: balanced brace extraction
   Strategy 4: regex key-value extraction
   All fail → return top ChromaDB result as fallback
        │
        ▼
5. RETURN  { target_path, confidence, reasoning, transformation, status: "pending_review" }
```

**Human-in-the-loop**: All suggestions are marked `pending_review`. An admin must confirm them from the Mapping Review page before they are saved to the vector store.

---

## CDC Pipeline

Every `INSERT`, `UPDATE`, or `DELETE` on a hospital table flows through this pipeline automatically:

```
1. PostgreSQL trigger fires on patients/encounters/lab_results/medications
   → Inserts row into data_change_log

2. CDC Worker (runs every 5s or on LISTEN/NOTIFY)
   → Reads new rows from data_change_log
   → Bundles up to 500 rows per batch
   → Signs batch with HMAC-SHA256
   → POST to http://localhost:8004/api/v1/cdc/ingest

3. Ingestion Service
   → Verifies HMAC signature
   → Writes each event to cdc_inbox with status='pending'

4. ETL Worker
   → Claims batch: FOR UPDATE SKIP LOCKED (PostgreSQL advisory lock)
   → Calls IncrementalSync handler for each event
   → Handler reads the full record from hospital DB
   → Maps to FHIR using schema_mapper
   → UPSERTs into fhir_patient / fhir_encounter / etc.
   → Marks row 'done'
   → On error: exponential backoff → retry up to 8× → dead-letter queue

5. Dead-letter queue (cdc_dead_letter)
   → Permanently failed events stored for manual review
   → Visible in the Admin Sync Analytics dashboard
```

---

## Demo Credentials

| Role | Username | Password |
|---|---|---|
| Super Admin | `admin` | `admin123` |
| Hospital Admin | `hospital` | `hospital123` |
| Doctor | `doctor` | `doctor123` |
| Analyst | `analyst` | `analyst123` |

**pgAdmin:**
- URL: http://localhost:5050
- Email: `admin@carelock.com`
- Password: `admin123`

---

## Team

| Name | Role |
|---|---|
| **Waleed Khalid** | Backend, CDC Pipeline, ETL Worker, System Architecture, Documentation, Supervision |
| **Muhammad Mohsin** | RAG System, FHIR Mapping Engine, AI Integration |
| **Shahmeer Nadeem** | Frontend, React Dashboards, UI/UX Design |

**Supervisor:** Dr. Muhammad Saqib Sohail  
**Institution:** Bahria University Lahore Campus  
**Program:** BS Computer Science — Final Year Project (2026)

---

## License

This project is developed for educational purposes as a Final Year Project.  
© 2026 Team CareLock Sync — Bahria University Lahore Campus
