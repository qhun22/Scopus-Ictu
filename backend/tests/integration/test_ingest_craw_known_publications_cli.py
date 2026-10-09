"""Task 09: Craw -> known-publication ingestion CLI (isolated test DB only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.master_lecturer import Lecturer
from scripts import generate_matching_candidates as guards
from scripts import ingest_craw_known_publications as cli

BASE = "https://repository.ictu.edu.vn"


def _write(directory: Path, lecturers, publications, links) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "lecturers.json").write_text(json.dumps(lecturers), encoding="utf-8")
    (directory / "publications.json").write_text(json.dumps(publications), encoding="utf-8")
    (directory / "lecturer_publication_links.json").write_text(json.dumps(links), encoding="utf-8")
    return directory


def _lec(slug):
    return {"source_id": f"{BASE}/giang-vien/{slug}/", "full_name": slug.title(), "profile_url": f"{BASE}/giang-vien/{slug}/"}


def _pub(slug, title, doi=None, year="2020"):
    return {"source_id": f"{BASE}/bai-bao/{slug}/", "title": title, "doi": doi, "year": year}


def _link(lec, pub):
    return {
        "lecturer_source_id": f"{BASE}/giang-vien/{lec}/",
        "target_source_id": f"{BASE}/bai-bao/{pub}/",
        "relationship_source": "ictu_lecturer_profile",
        "discovery_provenance": {"category": "publication"},
    }


@pytest.fixture
def craw(tmp_path):
    lecturers = [_lec("a"), _lec("b"), _lec("ghost")]  # "ghost" has no link -> must not be ingested
    publications = [
        _pub("p1", "Paper one", "10.1/one"),
        _pub("p2", "Paper two", None, "n/a"),
        _pub("p1-2", "Paper one again", "10.1/ONE"),
    ]
    links = [_link("a", "p1"), _link("a", "p2"), _link("b", "p1"), _link("a", "p1-2")]
    return _write(tmp_path / "craw", lecturers, publications, links)


@pytest.fixture
def env(isolated_db_engine, craw, tmp_path):
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL database available.")
    Base.metadata.create_all(bind=isolated_db_engine)
    with Session(isolated_db_engine) as s:
        for table in (
            "lecturer_scopus_candidate_evidence",
            "lecturer_scopus_candidate_observations",
            "lecturer_scopus_candidates",
            "candidate_generation_runs",
            "lecturer_known_publications",
            "lecturer_source_snapshots",
            "lecturers",
        ):
            s.execute(text(f"TRUNCATE {table} CASCADE"))
        s.add_all(
            Lecturer(full_name=n.title(), full_name_normalized=n, repository_profile_url=f"{BASE}/giang-vien/{n}/")
            for n in ("a", "b", "ghost")
        )
        s.commit()
    reader = guards.make_read_only_engine(isolated_db_engine.url)
    writer = create_engine(isolated_db_engine.url)
    yield {
        "engine": isolated_db_engine,
        "reader": reader,
        "writer": writer,
        "craw": craw,
        "manifest": tmp_path / "kp.json",
        "db": isolated_db_engine.url.database,
    }
    reader.dispose()
    writer.dispose()


def test_conversion_uses_only_existing_links_and_keeps_provenance(craw) -> None:
    data = cli.build_sources(craw)
    assert data.stats["craw_links"] == 4
    assert data.stats["lecturers_with_links"] == 2
    assert data.stats["links_unresolved"] == 0
    assert [s.craw_source_id for s in data.sources] == [f"{BASE}/giang-vien/a/", f"{BASE}/giang-vien/b/"]
    a = data.sources[0]
    assert {x.source_publication_url for x in a.publication_attributions} == {
        f"{BASE}/bai-bao/{p}/" for p in ("p1", "p2", "p1-2")
    }
    by_title = {x.title_raw: x for x in a.publication_attributions}
    assert by_title["Paper two"].published_year is None and by_title["Paper two"].doi_raw is None
    assert by_title["Paper one"].published_year == 2020 and by_title["Paper one"].doi_raw == "10.1/one"
    prov = a.raw_payload["_known_publication_links"]
    assert len(prov["links"]) == 3 and prov["links"][0]["relationship_source"] == "ictu_lecturer_profile"
    assert set(prov["source_files"]) == set(cli.CRAW_FILES)


def test_unresolvable_links_are_reported_not_dropped_silently(tmp_path) -> None:
    craw = _write(
        tmp_path / "c",
        [_lec("a")],
        [_pub("p1", "T")],
        [_link("a", "p1"), _link("zzz", "p1"), _link("a", "missing")],
    )
    data = cli.build_sources(craw)
    assert {p["code"] for p in data.problems} == {"LINK_UNKNOWN_LECTURER", "LINK_UNKNOWN_PUBLICATION"}
    assert data.stats["links_resolved"] == 1 and data.stats["links_unresolved"] == 2


def _counts(engine):
    tables = (
        "lecturers",
        "lecturer_source_snapshots",
        "lecturer_known_publications",
        "lecturer_scopus_candidates",
        "lecturer_scopus_identities",
        "publications",
        "scopus_authors",
    )
    with engine.connect() as conn:
        out = {t: conn.execute(text(f"select count(*) from {t}")).scalar_one() for t in tables}
        conn.rollback()
    return out


def test_preview_is_read_only_and_apply_is_idempotent(env) -> None:
    data = cli.build_sources(env["craw"])
    before = cli.table_counts(env["reader"])
    preview = cli.run_preview(env["reader"], data)
    assert (preview.mapped_lecturer_count, preview.unmapped_lecturer_count, preview.invalid_records) == (2, 0, 0)
    assert (preview.snapshots_to_create, preview.known_publications_to_create) == (2, 4)
    assert cli.table_counts(env["reader"]) == before
    assert cli.blocking_problems(data, preview) == []

    first = cli.apply_ingestion(env["reader"], env["writer"], data, env["manifest"], env["db"])
    assert first["snapshots_created"] == 2 and first["snapshots_reused"] == 0
    # p1 and p1-2 share a DOI (case-insensitive) for lecturer a -> collapsed by the service, URLs preserved
    assert first["known_publications_created"] == 3 and first["known_publications_reused"] == 1
    assert first["table_deltas"] == {"lecturer_source_snapshots": 2, "lecturer_known_publications": 3}
    assert json.loads(env["manifest"].read_text(encoding="utf-8"))["status"] == "COMPLETED"

    counts = _counts(env["engine"])
    again = cli.apply_ingestion(env["reader"], env["writer"], data, env["manifest"], env["db"])
    assert again["snapshots_created"] == 0 and again["known_publications_created"] == 0 and again["table_deltas"] == {}
    assert _counts(env["engine"]) == counts

    with Session(env["engine"]) as s:
        orphan_sql = (
            "select count(*) from lecturer_known_publications k left join lecturer_source_snapshots n "
            "on n.id=k.snapshot_id and n.lecturer_id=k.lecturer_id where n.id is null"
        )
        assert s.execute(text(orphan_sql)).scalar_one() == 0
        errors = s.execute(
            text("select validation_errors from lecturer_source_snapshots where jsonb_array_length(validation_errors) > 0")
        ).scalars().all()
        assert len(errors) == 1 and errors[0][0]["code"] == "SOURCE_URL_COLLISION"
        assert set(errors[0][0]["source_publication_urls"]) == {f"{BASE}/bai-bao/p1/", f"{BASE}/bai-bao/p1-2/"}
        with_links = (
            "select count(*) from lecturer_source_snapshots where source_system = 'ictu_craw' "
            "and jsonb_exists(raw_payload, '_known_publication_links')"
        )
        assert s.execute(text(with_links)).scalar_one() == 2
    # known publications are evidence only: no candidate, identity or master/canonical change
    assert counts["lecturer_scopus_candidates"] == 0
    assert counts["lecturer_scopus_identities"] == 0
    assert counts["lecturers"] == 3


def test_unmapped_lecturer_blocks_apply_and_writes_nothing(env, tmp_path) -> None:
    craw = _write(
        tmp_path / "c2",
        [_lec("a"), _lec("nobody")],
        [_pub("p1", "T", "10.1/x")],
        [_link("a", "p1"), _link("nobody", "p1")],
    )
    data = cli.build_sources(craw)
    counts = _counts(env["engine"])
    with pytest.raises(guards.CliRefused, match="unmapped"):
        cli.apply_ingestion(env["reader"], env["writer"], data, env["manifest"], env["db"])
    assert _counts(env["engine"]) == counts
    assert not env["manifest"].exists()


def test_main_guards(env, monkeypatch) -> None:
    from app.core.config import settings

    craw = str(env["craw"])
    monkeypatch.setattr(settings, "db_port", 5432)
    assert cli.main(["--dry-run", "--craw-dir", craw, "--expected-database", settings.db_name]) == guards.EXIT_REFUSED
    monkeypatch.setattr(settings, "db_port", env["engine"].url.port)
    assert cli.main(["--dry-run", "--craw-dir", craw, "--expected-database", "wrong"]) == guards.EXIT_REFUSED
    assert cli.main(["--apply", "--craw-dir", craw, "--expected-database", settings.db_name]) == guards.EXIT_REFUSED
