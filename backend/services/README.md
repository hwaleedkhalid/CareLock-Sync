# CareLock CDC Pipeline (out-of-process services)

The CDC pipeline is split into three independent processes plus the API.
Each process can be deployed and scaled separately.

```
   source DBs ───► CDC Worker(s) ───► Ingestion Service ───► cdc_inbox ───► ETL Worker(s) ───► shared (FHIR) DB
                       │                    │                                   │
                  watermark+              :8004                               :9201/healthz
                  LISTEN+poll            /healthz /metrics
```

## Services

| Service | Module | Default port | Notes |
|---|---|---|---|
| API | `api/main.py` | 8003 | READ + CONTROL only — no CDC startup, no scheduler |
| Ingestion | `services.ingestion.app` | 8004 | FastAPI; HMAC-validated `POST /api/v1/cdc/ingest` |
| CDC Worker | `services.cdc_worker` | — (admin :9101) | One CLI per source DB; reuses `connector.cdc_monitor.CDCMonitor` |
| ETL Worker | `services.etl_worker` | — (admin :9201) | One or more CLI replicas; reuses `etl.incremental_sync.IncrementalSync` |

Schema lives in `services/sql/schema.sql` and is applied idempotently on
service startup.

## Required environment

```
# Shared DB
INGESTION_DB_URL=postgresql://carelock:***@shared:5432/carelock_shared
ETL_SHARED_DB_URL=postgresql://carelock:***@shared:5432/carelock_shared

# Ingestion HMAC keys (one per source)
CDC_HMAC_KEYS=hospital_a:CHANGE_ME_LONG_RANDOM_SECRET

# CDC Worker (must match the key above for its source)
CDC_HMAC_KEY_HOSPITAL_A=CHANGE_ME_LONG_RANDOM_SECRET

# Optional toggles
CDC_AUTO_SETUP=false
CDC_REGISTRY_AUTO_STUB=false
CDC_NEW_TABLE_POLICY=require_config
CDC_SOURCES_FILE=config/cdc_sources.yaml
INGESTION_BACKPRESSURE_THRESHOLD=100000
ETL_BATCH_SIZE=200
ETL_MAX_ATTEMPTS=8
ETL_CLAIM_TIMEOUT_SECONDS=120
ETL_FK_MAX_WAIT_SECONDS=300
```

## Run

From `backend/`:

```
# 1. Backend (READ + CONTROL)
uvicorn api.main:app --host 0.0.0.0 --port 8003

# 2. Ingestion
uvicorn services.ingestion.app:app --host 0.0.0.0 --port 8004

# 3. CDC Worker — one per source DB
python -m services.cdc_worker --source hospital_a            # normal
python -m services.cdc_worker --source hospital_a --setup    # one-shot trigger install

# 4. ETL Worker — scale horizontally
python -m services.etl_worker
python -m services.etl_worker          # second replica processes a different partition
```

See `config/cdc_sources.yaml.example` for source configuration.
