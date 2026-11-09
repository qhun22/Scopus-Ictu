"""Publications store the canonical DOI; the raw payload keeps what Scopus sent."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.services.lecturer_dataset.known_publication_ingestion import normalize_doi_n0
from app.services.normalization.scopus_normalizer import (
    compare_metadata,
    create_publication_from_raw,
)
from app.services.normalization_compare import _status

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "b3d91f4c7a20_canonical_publication_doi.py"
)

CASES = [
    ("10.1016/J.Example.2025.1", "10.1016/j.example.2025.1"),
    ("  10.1000/abc  ", "10.1000/abc"),
    ("https://doi.org/10.1000/ABC", "10.1000/abc"),
    ("HTTP://DX.DOI.ORG/10.1000/ABC", "10.1000/abc"),
    ("DOI:10.1000/ABC", "10.1000/abc"),
    ("10.1000/already-canonical", "10.1000/already-canonical"),
    ("not-a-doi-Keep-It", "not-a-doi-keep-it"),
    ("https://doi.org/", None),
]


def _migration():
    spec = importlib.util.spec_from_file_location("canonical_doi_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _raw(doi: str | None) -> MagicMock:
    raw = MagicMock()
    raw.eid_raw = "2-s2.0-123"
    raw.raw_payload = {"Title": "Synthetic Paper", "DOI": doi}
    return raw


@pytest.mark.parametrize(("value", "expected"), CASES)
def test_a_new_publication_stores_the_canonical_doi(value, expected) -> None:
    assert create_publication_from_raw(_raw(value)).doi == expected


def test_the_raw_payload_keeps_the_doi_as_received() -> None:
    raw = _raw("https://doi.org/10.1000/ABC")
    create_publication_from_raw(raw)
    assert raw.raw_payload["DOI"] == "https://doi.org/10.1000/ABC"


@pytest.mark.parametrize("stored", ["10.1000/ABC", "10.1000/abc", "https://doi.org/10.1000/abc"])
def test_the_same_doi_in_another_spelling_is_not_a_metadata_change(stored) -> None:
    existing = MagicMock(doi=stored)
    assert "doi" not in compare_metadata(existing, {}, {"DOI": "10.1000/ABC"})


def test_a_different_doi_is_still_a_metadata_change() -> None:
    existing = MagicMock(doi="10.1000/OLD")
    assert "doi" in compare_metadata(existing, {}, {"DOI": "10.1000/new"})


def test_compare_shows_a_canonicalized_doi_as_cleaned_not_changed() -> None:
    assert _status("10.1000/ABC", "10.1000/abc", "10.1000/abc") == "CLEANED"


def test_compare_still_flags_a_stored_value_that_is_not_the_canonical_form() -> None:
    assert _status("10.1000/ABC", "10.1000/other", "10.1000/abc") == "CHANGED"


@pytest.mark.parametrize(("value", "expected"), CASES)
def test_the_migration_applies_the_same_rule_as_the_application(value, expected) -> None:
    assert _migration()._canonical_doi(value) == expected == normalize_doi_n0(value)


def test_the_migration_rewrites_only_rows_that_are_not_canonical() -> None:
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    publications = sa.Table(
        "publications",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("doi", sa.String, nullable=True),
        sa.Column("label", sa.String, nullable=False),
    )
    metadata.create_all(engine)
    seeded = {
        "mixed": "10.1016/J.Example",
        "url": "https://doi.org/10.1000/ABC",
        "clean": "10.1000/clean",
        "none": None,
        "empty": "https://doi.org/",
    }
    with engine.begin() as conn:
        conn.execute(
            publications.insert(),
            [
                {"id": str(uuid.uuid4()), "doi": doi, "label": label}
                for label, doi in seeded.items()
            ],
        )
        module = _migration()
        select_all = sa.select(publications.c.label, publications.c.doi)
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            first = {row.label: row.doi for row in conn.execute(select_all)}
            module.upgrade()  # Re-running changes nothing.
            second = {row.label: row.doi for row in conn.execute(select_all)}

    assert first == {
        "mixed": "10.1016/j.example",
        "url": "10.1000/abc",
        "clean": "10.1000/clean",
        "none": None,
        "empty": None,
    }
    assert second == first
