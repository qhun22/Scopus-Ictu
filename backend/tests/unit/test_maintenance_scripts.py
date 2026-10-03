from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from scripts import benchmark_m2_6a_10k, run_m2_6a_acceptance
from scripts.clean_orphan_lecturers import (
    DISPOSABLE_SOURCE_PREFIX,
    DISPOSABLE_SOURCE_SYSTEM,
    disposable_lecturer_ids,
    has_disposable_provenance,
)


def test_lecturer_provenance_requires_explicit_disposable_marker() -> None:
    assert has_disposable_provenance(
        DISPOSABLE_SOURCE_SYSTEM,
        f"{DISPOSABLE_SOURCE_PREFIX}fixture-1",
    )
    assert not has_disposable_provenance("ICTU", "https://ictu.edu.vn/lecturers/1")
    assert not has_disposable_provenance("TEST", "test://other/fixture-1")


def test_disposable_selection_requires_provenance_and_protects_relationships() -> None:
    class RecordingSession:
        def scalars(self, statement):
            self.statement = statement
            return []

    session = RecordingSession()
    assert disposable_lecturer_ids(session, [uuid4()]) == []

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "lecturer_source_snapshots.source_system" in sql
    assert "lecturer_source_snapshots.source_url" in sql
    assert "users" in sql
    assert "lecturer_scopus_identities" in sql
    assert "lecturer_known_publications" in sql


def test_acceptance_refuses_prod_before_parsing(monkeypatch) -> None:
    monkeypatch.setattr(run_m2_6a_acceptance.settings, "environment", "prod")
    monkeypatch.setattr(sys, "argv", ["run_m2_6a_acceptance.py"])

    with pytest.raises(SystemExit, match="ENVIRONMENT=prod"):
        run_m2_6a_acceptance.main()


def test_acceptance_reports_missing_dataset(monkeypatch) -> None:
    monkeypatch.setattr(run_m2_6a_acceptance.settings, "environment", "local")
    missing_dataset = Path("definitely-missing-m2-6a-dataset.csv")
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_m2_6a_acceptance.py", "--dataset", str(missing_dataset)],
    )

    with pytest.raises(SystemExit, match="Dataset file not found"):
        run_m2_6a_acceptance.main()


def test_benchmark_refuses_prod_before_database_setup(monkeypatch) -> None:
    monkeypatch.setattr(benchmark_m2_6a_10k.settings, "environment", "prod")

    with pytest.raises(SystemExit, match="ENVIRONMENT=prod"):
        benchmark_m2_6a_10k.main()
