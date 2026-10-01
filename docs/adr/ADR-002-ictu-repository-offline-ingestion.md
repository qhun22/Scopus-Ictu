# ADR-002 — ICTU Repository Offline Ingestion

Status: ACCEPTED (Architecture v1.1)

## Context

The ICTU Repository is treated as an **institutional master-data source**,
not as ground truth. We must integrate with it without:

- coupling runtime business requests to its availability,
- depending on its HTTP uptime at request time,
- forcing the institution to support an API for our project.

## Decision

Repository ingestion is **strictly OFFLINE**:

```
ICTU Repository
  → crawler (script)
  → NDJSON snapshot (data/snapshots/)
  → validation
  → normalization
  → database import
```

- The crawler lives in `backend/scripts/crawl_dspace_snapshot.py` and runs
  only as a CLI.
- The import path consumes the local NDJSON snapshot only.
- No FastAPI route, background task, or service may issue a live HTTP call
  to the ICTU Repository.

## Consequences

- Runtime business requests are decoupled from ICTU uptime.
- Snapshot files become a reproducible, auditable artifact.
- Snapshot freshness is an operational concern, not a code concern.

## Prohibited

- HTTP calls to the ICTU Repository from API/services.
- Importing directly from a live URL.
- Caching ICTU responses in memory at request time.