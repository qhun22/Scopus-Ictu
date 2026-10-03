"""Measured disposable 10k-row PostgreSQL benchmark for M2.6A.

The query count is reported as evidence, not a performance claim.
PERFORMANCE_OPTIMIZATION_DEBT: review per-record lookup/query volume before
scaling normalization beyond the measured workload.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, event, insert, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - register the complete metadata
from app.core.config import settings
from app.models.base import Base
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.normalization.scopus_normalizer import normalize_import

ROWS = 10_000
BATCH_SIZE = 500


def main() -> None:
    if settings.environment.lower() == "prod":
        raise SystemExit("Refusing benchmark execution in ENVIRONMENT=prod.")
    schema = f"bench_m26a_{uuid.uuid4().hex}"
    admin_engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    query_count = 0

    def count_query(*_args) -> None:
        nonlocal query_count
        query_count += 1

    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        import_id = uuid.uuid4()
        now = datetime.now(UTC)
        with factory() as db:
            db.add(
                ScopusImport(
                    id=import_id,
                    file_name="m2_6a_benchmark_10000.csv",
                    file_sha256=hashlib.sha256(import_id.bytes).hexdigest(),
                    total_records=ROWS,
                    valid_records=ROWS,
                    invalid_records=0,
                    status="STAGED",
                    error_summary=None,
                    normalization_summary=None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()
            for offset in range(0, ROWS, 1_000):
                values = [
                    {
                        "id": uuid.uuid4(),
                        "import_id": import_id,
                        "row_number": number + 1,
                        "row_hash": hashlib.sha256(
                            f"benchmark-{number}".encode("ascii")
                        ).hexdigest(),
                        "eid_raw": f"2-s2.0-BENCH-{number:010d}",
                        "doi_raw": None,
                        "raw_payload": {"Title": f"Benchmark publication {number}"},
                        "validation_status": "VALID",
                        "validation_errors": None,
                        "created_at": now,
                    }
                    for number in range(offset, min(offset + 1_000, ROWS))
                ]
                db.execute(insert(RawScopusRecord), values)
                db.commit()

            event.listen(engine, "before_cursor_execute", count_query)
            started = time.perf_counter()
            counters = normalize_import(
                db,
                import_id,
                cancel_check_interval=BATCH_SIZE,
            )
            duration = time.perf_counter() - started
            event.remove(engine, "before_cursor_execute", count_query)

            print(
                json.dumps(
                    {
                        "rows": ROWS,
                        "batch_size": BATCH_SIZE,
                        "batches": ROWS // BATCH_SIZE,
                        "duration_seconds": round(duration, 3),
                        "query_count": query_count,
                        "performance_optimization_debt": (
                            "PERFORMANCE_OPTIMIZATION_DEBT"
                            if query_count > ROWS
                            else None
                        ),
                        "counts": counters.to_dict(),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


if __name__ == "__main__":
    main()
