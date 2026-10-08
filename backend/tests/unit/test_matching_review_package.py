"""Unit tests for the human matching review package — C3-A2.

No live database or external service required.
"""

from __future__ import annotations

import ast
import csv
import importlib.util
import inspect
import io
import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.matching import review_package as rp
from app.services.matching.candidate_types import (
    CandidateEvidence,
    EnrichedLecturerScopusCandidate,
    PublicationEvidence,
    PublicationEvidenceConflict,
)
from app.services.matching.evaluation import parse_reference_csv
from app.services.matching.review_package import (
    CANDIDATE_REVIEW_COLUMNS,
    LABELING_SHEET_COLUMNS,
    MANIFEST_FIELDS,
    OfficialLecturer,
    ReviewPackageError,
    build_review_package,
    compute_publication_conflicts,
    parse_official_lecturers,
    parse_source_id_file,
    resolve_canonical_ids,
    select_lecturers,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NOW = datetime(2026, 10, 8, 0, 0, 0, tzinfo=timezone.utc)

SRC_A = "https://example.com/a/"
SRC_B = "https://example.com/b/"
SRC_C = "https://example.com/c/"

_SECRET_NORMALIZED = "NORMALIZED-COMPARISON-VALUE"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dataset_bytes(rows: list[dict]) -> bytes:
    return json.dumps({"lecturers": rows}, ensure_ascii=False).encode("utf-8")


def _official(*ids: str) -> tuple[OfficialLecturer, ...]:
    return tuple(OfficialLecturer(s, f"Name {s[-2]}", f"{s[-2]}@ictu.edu.vn") for s in ids)


def _evidence(rule_id: str = "RULE_EXACT_N0", surface: str = "Nguyen A") -> CandidateEvidence:
    return CandidateEvidence(
        rule_id=rule_id,
        lecturer_source_value="Nguyen A",
        lecturer_comparison_value=_SECRET_NORMALIZED,
        scopus_surface_type="PREFERRED_NAME",
        scopus_surface_value=surface,
        scopus_comparison_value=_SECRET_NORMALIZED,
    )


def _pub_evidence(lecturer_uuid: uuid.UUID, eid: str = "2-s2.0-1", rule: str = "RULE_KNOWN_PUBLICATION_DOI_EXACT"):
    return PublicationEvidence(
        rule_id=rule,
        known_publication_id=uuid.uuid4(),
        lecturer_id=lecturer_uuid,
        lecturer_snapshot_id=uuid.uuid4(),
        canonical_publication_id=uuid.uuid4(),
        canonical_publication_eid=eid,
        candidate_scopus_author_id=uuid.uuid4(),
        known_publication_doi_normalized="10.1/x",
        known_publication_title_normalized="a title",
        canonical_publication_doi="10.1/x",
        canonical_publication_title="A Title",
        reconciliation="DOI_EXACT" if "DOI" in rule else "TITLE_EXACT",
    )


def _candidate(
    lecturer_uuid: uuid.UUID,
    scopus_id: str,
    *,
    rules: tuple[str, ...] = ("RULE_EXACT_N0",),
    pubs: tuple = (),
    name: str = "Preferred Name",
) -> EnrichedLecturerScopusCandidate:
    return EnrichedLecturerScopusCandidate(
        lecturer_id=lecturer_uuid,
        scopus_author_id=uuid.uuid4(),
        scopus_id=scopus_id,
        preferred_name=name,
        evidence=tuple(_evidence(rule) for rule in rules),
        publication_evidence=pubs,
    )


def _conflict(lecturer_uuid: uuid.UUID, reason: str = "TITLE_AMBIGUOUS") -> PublicationEvidenceConflict:
    return PublicationEvidenceConflict(
        known_publication_id=uuid.uuid4(),
        lecturer_id=lecturer_uuid,
        lecturer_snapshot_id=uuid.uuid4(),
        reason=reason,
        doi_publication_ids=(uuid.uuid4(),),
        title_publication_ids=(uuid.uuid4(), uuid.uuid4()),
    )


def _build(
    selected,
    canonical,
    candidates=(),
    conflicts=(),
    dataset: bytes = b"{}",
    selection: bytes | None = None,
):
    return build_review_package(
        selected=selected,
        canonical_ids=canonical,
        enriched_candidates=candidates,
        conflicts=conflicts,
        official_dataset_bytes=dataset,
        source_id_file_bytes=selection,
        rule_set_id="M2.7A_CANDIDATE_GENERATOR",
        rule_set_version="M2.7A-2",
        generated_at=_NOW,
    )


def _rows(csv_bytes: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))


# ===========================================================================
# OFFICIAL DATASET / SELECTION
# ===========================================================================


class TestOfficialDatasetAndSelection:
    def _rows(self, *ids: str) -> list[dict]:
        return [{"source_id": s, "full_name": f"Name {s}", "institutional_email": None} for s in ids]

    def test_all_official_lecturers_selected_by_default_in_sorted_order(self):
        official = parse_official_lecturers(_dataset_bytes(self._rows("z", "a", "m")))
        selected = select_lecturers(official, None)
        assert [l.source_id for l in selected] == ["a", "m", "z"]

    def test_subset_file_selects_only_requested(self):
        official = parse_official_lecturers(_dataset_bytes(self._rows("a", "b", "c")))
        requested = parse_source_id_file(b"c\na\n")
        assert [l.source_id for l in select_lecturers(official, requested)] == ["a", "c"]

    def test_blank_lines_and_comments_allowed(self):
        assert parse_source_id_file(b"# header\n\nA\n   \n# note\nB\n") == ("A", "B")

    def test_duplicate_requested_source_id_rejected(self):
        with pytest.raises(ReviewPackageError):
            parse_source_id_file(b"A\nA\n")

    def test_unknown_requested_source_id_rejected(self):
        official = parse_official_lecturers(_dataset_bytes(self._rows("a")))
        with pytest.raises(ReviewPackageError):
            select_lecturers(official, ("a", "nope"))

    def test_empty_effective_subset_rejected(self):
        with pytest.raises(ReviewPackageError):
            parse_source_id_file(b"# only comments\n\n")

    def test_duplicate_official_source_id_rejected(self):
        with pytest.raises(ReviewPackageError):
            parse_official_lecturers(_dataset_bytes(self._rows("a", "a")))

    def test_zero_candidate_lecturers_are_still_selected(self):
        official = parse_official_lecturers(_dataset_bytes(self._rows("a", "b")))
        assert len(select_lecturers(official, None)) == 2


# ===========================================================================
# CANONICAL RESOLUTION
# ===========================================================================


class TestCanonicalResolution:
    def test_exactly_one_succeeds(self):
        lid = uuid.uuid4()
        assert resolve_canonical_ids(_official(SRC_A), [(SRC_A, lid)]) == {SRC_A: lid}

    def test_zero_rows_fails(self):
        with pytest.raises(ReviewPackageError):
            resolve_canonical_ids(_official(SRC_A), [])

    def test_multiple_rows_fails(self):
        with pytest.raises(ReviewPackageError):
            resolve_canonical_ids(_official(SRC_A), [(SRC_A, uuid.uuid4()), (SRC_A, uuid.uuid4())])

    def test_no_silent_skip_when_one_of_several_unresolved(self):
        with pytest.raises(ReviewPackageError):
            resolve_canonical_ids(_official(SRC_A, SRC_B), [(SRC_A, uuid.uuid4())])


# ===========================================================================
# CANDIDATE ROWS
# ===========================================================================


class TestCandidateRows:
    def test_one_candidate_one_row(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la}, [_candidate(la, "S1")])
        rows = _rows(pkg.candidate_review_csv)
        assert len(rows) == 1
        assert rows[0]["suggestion_status"] == "CANDIDATE"
        assert rows[0]["candidate_count"] == "1"
        assert rows[0]["candidate_scopus_id"] == "S1"

    def test_multiple_candidates_one_row_each_with_repeated_count(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la}, [_candidate(la, "S2"), _candidate(la, "S1")])
        rows = _rows(pkg.candidate_review_csv)
        assert [r["candidate_scopus_id"] for r in rows] == ["S1", "S2"]
        assert {r["candidate_count"] for r in rows} == {"2"}

    def test_zero_candidate_lecturer_gets_exactly_one_marker_row(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la})
        rows = _rows(pkg.candidate_review_csv)
        assert len(rows) == 1
        row = rows[0]
        assert row["suggestion_status"] == "NO_CANDIDATE_GENERATED"
        assert row["candidate_count"] == "0"
        for column in (
            "candidate_scopus_id",
            "candidate_preferred_name",
            "name_rule_ids",
            "name_evidence_json",
            "publication_evidence_count",
            "publication_rule_ids",
            "publication_evidence_json",
        ):
            assert row[column] == ""

    def test_zero_candidate_never_produces_no_match(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la})
        assert b"NO_MATCH" not in pkg.candidate_review_csv
        assert b"MATCH" not in pkg.candidate_review_csv.replace(b"NO_CANDIDATE_GENERATED", b"")

    def test_exact_columns(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la})
        header = pkg.candidate_review_csv.decode("utf-8").splitlines()[0]
        assert header.split(",") == list(CANDIDATE_REVIEW_COLUMNS)

    def test_labeling_fields_never_derived_from_candidates(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la}, [_candidate(la, "S1")])
        sheet = _rows(pkg.reference_labeling_sheet_csv)
        assert sheet[0]["expected_scopus_id"] == ""
        assert b"S1" not in pkg.reference_labeling_sheet_csv


# ===========================================================================
# ORDER / NO RANKING
# ===========================================================================


class TestOrderAndNoRanking:
    def test_lecturer_rows_sorted_by_source_id(self):
        ids = {SRC_C: uuid.uuid4(), SRC_A: uuid.uuid4(), SRC_B: uuid.uuid4()}
        pkg = _build(_official(SRC_C, SRC_A, SRC_B), ids)
        assert [r["lecturer_source_id"] for r in _rows(pkg.candidate_review_csv)] == [SRC_A, SRC_B, SRC_C]

    def test_candidate_with_more_evidence_does_not_move_ahead(self):
        la = uuid.uuid4()
        rich = _candidate(
            la,
            "S-B",
            rules=("RULE_EXACT_N0", "RULE_TITLE_STRIPPED_N0"),
            pubs=(_pub_evidence(la, "e1"), _pub_evidence(la, "e2")),
        )
        poor = _candidate(la, "S-A")
        pkg = _build(_official(SRC_A), {SRC_A: la}, [rich, poor])
        assert [r["candidate_scopus_id"] for r in _rows(pkg.candidate_review_csv)] == ["S-A", "S-B"]

    def test_publication_evidence_count_does_not_affect_order(self):
        la = uuid.uuid4()
        a = _candidate(la, "S-1", pubs=())
        b = _candidate(la, "S-2", pubs=(_pub_evidence(la),))
        for candidates in ([a, b], [b, a]):
            pkg = _build(_official(SRC_A), {SRC_A: la}, candidates)
            assert [r["candidate_scopus_id"] for r in _rows(pkg.candidate_review_csv)] == ["S-1", "S-2"]

    def test_conflict_count_does_not_affect_lecturer_order(self):
        la, lb = uuid.uuid4(), uuid.uuid4()
        conflicts = [_conflict(lb), _conflict(lb), _conflict(lb)]
        pkg = _build(_official(SRC_A, SRC_B), {SRC_A: la, SRC_B: lb}, conflicts=conflicts)
        assert [r["lecturer_source_id"] for r in _rows(pkg.candidate_review_csv)] == [SRC_A, SRC_B]

    def test_no_ranking_scoring_fields_anywhere(self):
        forbidden = ("rank", "score", "confidence", "probability", "threshold", "best", "top", "recommend")
        for column in (*CANDIDATE_REVIEW_COLUMNS, *LABELING_SHEET_COLUMNS, *MANIFEST_FIELDS):
            for word in forbidden:
                assert word not in column.lower(), f"{column} contains {word}"


# ===========================================================================
# NAME EVIDENCE SAFETY
# ===========================================================================


class TestNameEvidenceSafety:
    def _row(self, rules=("RULE_TITLE_STRIPPED_N2", "RULE_EXACT_N0", "RULE_EXACT_N0")):
        la = uuid.uuid4()
        cand = _candidate(la, "S1", rules=tuple(dict.fromkeys(rules)))
        pkg = _build(_official(SRC_A), {SRC_A: la}, [cand])
        return _rows(pkg.candidate_review_csv)[0], la, cand

    def test_rule_ids_unique_and_sorted(self):
        row, *_ = self._row()
        assert json.loads(row["name_rule_ids"]) == ["RULE_EXACT_N0", "RULE_TITLE_STRIPPED_N2"]

    def test_json_compact_and_deterministic(self):
        row1, *_ = self._row()
        row2, *_ = self._row()
        assert row1["name_evidence_json"] == row2["name_evidence_json"]
        assert ", " not in row1["name_evidence_json"] and ": " not in row1["name_evidence_json"]

    def test_only_whitelisted_fields(self):
        row, *_ = self._row()
        for item in json.loads(row["name_evidence_json"]):
            assert set(item) == {
                "rule_id",
                "lecturer_source_value",
                "scopus_surface_type",
                "scopus_surface_value",
            }

    def test_no_comparison_values_or_uuids_leak(self):
        row, la, cand = self._row()
        blob = json.dumps(row)
        assert _SECRET_NORMALIZED not in blob
        assert str(la) not in blob
        assert str(cand.scopus_author_id) not in blob

    def test_no_generic_asdict_in_source(self):
        tree = ast.parse(inspect.getsource(rp))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                assert name not in {"asdict", "astuple"}
            if isinstance(node, ast.ImportFrom):
                assert all(alias.name != "asdict" for alias in node.names)


# ===========================================================================
# PUBLICATION EVIDENCE SAFETY
# ===========================================================================


class TestPublicationEvidenceSafety:
    def _row(self):
        la = uuid.uuid4()
        pubs = (
            _pub_evidence(la, "e2", "RULE_KNOWN_PUBLICATION_TITLE_EXACT"),
            _pub_evidence(la, "e1", "RULE_KNOWN_PUBLICATION_DOI_EXACT"),
            _pub_evidence(la, "e3", "RULE_KNOWN_PUBLICATION_DOI_EXACT"),
        )
        cand = _candidate(la, "S1", pubs=pubs)
        pkg = _build(_official(SRC_A), {SRC_A: la}, [cand])
        return _rows(pkg.candidate_review_csv)[0], pubs, la

    def test_count_and_sorted_unique_rules(self):
        row, *_ = self._row()
        assert row["publication_evidence_count"] == "3"
        assert json.loads(row["publication_rule_ids"]) == [
            "RULE_KNOWN_PUBLICATION_DOI_EXACT",
            "RULE_KNOWN_PUBLICATION_TITLE_EXACT",
        ]

    def test_items_sorted_by_eid_and_whitelisted(self):
        row, *_ = self._row()
        items = json.loads(row["publication_evidence_json"])
        assert [i["canonical_publication_eid"] for i in items] == ["e1", "e2", "e3"]
        for item in items:
            assert set(item) == {
                "rule_id",
                "reconciliation",
                "canonical_publication_eid",
                "canonical_publication_doi",
                "canonical_publication_title",
            }

    def test_no_internal_uuid_leak(self):
        row, pubs, la = self._row()
        blob = json.dumps(row)
        assert str(la) not in blob
        for pub in pubs:
            for value in (
                pub.known_publication_id,
                pub.lecturer_snapshot_id,
                pub.canonical_publication_id,
                pub.candidate_scopus_author_id,
            ):
                assert str(value) not in blob


# ===========================================================================
# FULL-SELECTED-SET PUBLICATION CONFLICTS
# ===========================================================================


class TestFullSetPublicationConflicts:
    def test_zero_candidate_lecturer_still_reports_conflict(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la}, conflicts=[_conflict(la, "TITLE_AMBIGUOUS")])
        row = _rows(pkg.candidate_review_csv)[0]
        assert row["suggestion_status"] == "NO_CANDIDATE_GENERATED"
        assert row["candidate_count"] == "0"
        assert int(row["lecturer_publication_conflict_count"]) > 0
        assert json.loads(row["lecturer_publication_conflict_reasons"]) == ["TITLE_AMBIGUOUS"]

    def test_conflict_for_lecturer_with_candidates_repeated_on_each_row(self):
        la = uuid.uuid4()
        pkg = _build(
            _official(SRC_A),
            {SRC_A: la},
            [_candidate(la, "S1"), _candidate(la, "S2")],
            [_conflict(la, "DOI_AMBIGUOUS")],
        )
        rows = _rows(pkg.candidate_review_csv)
        assert {r["lecturer_publication_conflict_count"] for r in rows} == {"1"}

    def test_count_is_descriptors_and_reasons_unique_sorted(self):
        la = uuid.uuid4()
        conflicts = [
            _conflict(la, "TITLE_AMBIGUOUS"),
            _conflict(la, "DOI_AMBIGUOUS"),
            _conflict(la, "TITLE_AMBIGUOUS"),
        ]
        row = _rows(_build(_official(SRC_A), {SRC_A: la}, conflicts=conflicts).candidate_review_csv)[0]
        assert row["lecturer_publication_conflict_count"] == "3"
        assert json.loads(row["lecturer_publication_conflict_reasons"]) == [
            "DOI_AMBIGUOUS",
            "TITLE_AMBIGUOUS",
        ]

    def test_no_uuid_fields_serialized(self):
        la = uuid.uuid4()
        conflict = _conflict(la)
        pkg = _build(_official(SRC_A), {SRC_A: la}, conflicts=[conflict])
        blob = (pkg.candidate_review_csv + pkg.manifest_json).decode("utf-8")
        for value in (
            conflict.known_publication_id,
            conflict.lecturer_snapshot_id,
            *conflict.doi_publication_ids,
            *conflict.title_publication_ids,
            la,
        ):
            assert str(value) not in blob

    def test_conflict_neither_creates_nor_removes_candidates(self):
        la, lb = uuid.uuid4(), uuid.uuid4()
        cand = _candidate(la, "S1")
        pkg = _build(
            _official(SRC_A, SRC_B),
            {SRC_A: la, SRC_B: lb},
            [cand],
            [_conflict(la), _conflict(lb)],
        )
        rows = _rows(pkg.candidate_review_csv)
        by_lecturer = {r["lecturer_source_id"]: r for r in rows}
        assert by_lecturer[SRC_A]["candidate_scopus_id"] == "S1"
        assert by_lecturer[SRC_B]["candidate_scopus_id"] == ""
        assert len(rows) == 2

    def test_conflict_never_populates_labels(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la}, conflicts=[_conflict(la)])
        sheet = _rows(pkg.reference_labeling_sheet_csv)[0]
        assert sheet["decision"] == "" and sheet["expected_scopus_id"] == ""

    def test_reconciliation_helper_finds_conflict_without_any_candidate(self):
        lecturer = uuid.uuid4()
        snapshot = SimpleNamespace(id=uuid.uuid4(), lecturer_id=lecturer)
        known = SimpleNamespace(
            id=uuid.uuid4(),
            snapshot_id=snapshot.id,
            lecturer_id=lecturer,
            doi_normalized=None,
            title_normalized="same title",
        )
        pubs = [
            SimpleNamespace(id=uuid.uuid4(), eid=f"e{i}", doi=None, title_normalized="same title", title="T")
            for i in range(2)
        ]
        conflicts = compute_publication_conflicts([known], [snapshot], pubs)
        assert [c.reason for c in conflicts] == ["TITLE_AMBIGUOUS"]
        assert conflicts[0].lecturer_id == lecturer

    def test_generate_review_inputs_covers_zero_candidate_lecturers(self, monkeypatch):
        lecturer = uuid.uuid4()
        snapshot = SimpleNamespace(id=uuid.uuid4(), lecturer_id=lecturer)
        known = SimpleNamespace(
            id=uuid.uuid4(),
            snapshot_id=snapshot.id,
            lecturer_id=lecturer,
            doi_normalized=None,
            title_normalized="same title",
        )
        pubs = [
            SimpleNamespace(id=uuid.uuid4(), eid=f"e{i}", doi=None, title_normalized="same title", title="T")
            for i in range(2)
        ]

        class _Session:
            def __init__(self):
                self._queue = [[known], [snapshot], pubs]

            def scalars(self, _stmt):
                return self._queue.pop(0)

        import app.services.matching.candidate_generator as cg
        import app.services.matching.publication_evidence_enricher as pe

        class _Gen:
            def __init__(self, _s):
                pass

            def generate_all(self):
                return ()

        class _Enr:
            def __init__(self, _s):
                pass

            def enrich(self, candidates):
                return SimpleNamespace(candidates=tuple(candidates), conflicts=())

        monkeypatch.setattr(cg, "CandidateGenerator", _Gen)
        monkeypatch.setattr(pe, "PublicationEvidenceEnricher", _Enr)

        enriched, conflicts = rp.generate_review_inputs({SRC_A: lecturer}, _Session())
        assert enriched == ()
        assert [c.reason for c in conflicts] == ["TITLE_AMBIGUOUS"]

    def test_generation_path_does_not_use_persisted_candidates(self):
        source = inspect.getsource(rp.generate_review_inputs)
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert "CandidateGenerator" in imported
        assert "PublicationEvidenceEnricher" in imported
        for forbidden in (
            "LecturerScopusCandidate",
            "LecturerScopusCandidateObservation",
            "LecturerScopusCandidateEvidence",
            "CandidateGenerationRun",
        ):
            assert forbidden not in imported
        assert "CandidatePersistenceService" not in inspect.getsource(rp)


# ===========================================================================
# LABELING SHEET
# ===========================================================================


class TestLabelingSheet:
    def test_header_equals_a1_template(self):
        template = (_REPO_ROOT / "data/matching/reference/reference_template.csv").read_text(encoding="utf-8")
        pkg = _build(_official(SRC_A), {SRC_A: uuid.uuid4()})
        header = pkg.reference_labeling_sheet_csv.decode("utf-8").splitlines()[0]
        assert header == template.strip().splitlines()[0]
        assert tuple(header.split(",")) == LABELING_SHEET_COLUMNS

    def test_one_row_per_selected_lecturer_with_blank_label_fields(self):
        ids = {SRC_A: uuid.uuid4(), SRC_B: uuid.uuid4()}
        cands = [_candidate(ids[SRC_A], "S1"), _candidate(ids[SRC_A], "S2")]
        pkg = _build(_official(SRC_A, SRC_B), ids, cands, [_conflict(ids[SRC_B])])
        rows = _rows(pkg.reference_labeling_sheet_csv)
        assert [r["lecturer_source_id"] for r in rows] == [SRC_A, SRC_B]
        for row in rows:
            assert row["lecturer_full_name"] and row["institutional_email"]
            for column in ("decision", "expected_scopus_id", "confirmation_source", "confirmed_at", "notes"):
                assert row[column] == ""

    def test_review_only_columns_absent(self):
        pkg = _build(_official(SRC_A), {SRC_A: uuid.uuid4()})
        header = pkg.reference_labeling_sheet_csv.decode("utf-8").splitlines()[0]
        for column in ("suggestion_status", "candidate_count", "conflict", "evidence"):
            assert column not in header
        assert b"MATCH" not in pkg.reference_labeling_sheet_csv

    def test_filled_sheet_is_a1_compatible(self):
        pkg = _build(_official(SRC_A), {SRC_A: uuid.uuid4()})
        rows = _rows(pkg.reference_labeling_sheet_csv)
        rows[0].update(
            decision="NO_MATCH",
            confirmation_source="Supervisor",
            confirmed_at="2026-10-01T10:00:00Z",
        )
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=list(LABELING_SHEET_COLUMNS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        records = parse_reference_csv(out.getvalue())
        assert records[0].decision.decision == "NO_MATCH"


# ===========================================================================
# MANIFEST
# ===========================================================================


class TestManifest:
    def test_exact_field_set(self):
        pkg = _build(_official(SRC_A), {SRC_A: uuid.uuid4()})
        assert set(pkg.manifest) == set(MANIFEST_FIELDS)
        assert json.loads(pkg.manifest_json) == pkg.manifest

    def test_hashes_use_exact_bytes(self):
        dataset = b'{"lecturers": []}\n'
        selection = b"# c\nA\n"
        pkg = _build(_official(SRC_A), {SRC_A: uuid.uuid4()}, dataset=dataset, selection=selection)
        import hashlib

        assert pkg.manifest["official_lecturer_dataset_sha256"] == hashlib.sha256(dataset).hexdigest()
        assert pkg.manifest["source_id_file_sha256"] == hashlib.sha256(selection).hexdigest()
        assert pkg.manifest["candidate_review_sha256"] == hashlib.sha256(pkg.candidate_review_csv).hexdigest()
        assert (
            pkg.manifest["reference_labeling_sheet_sha256"]
            == hashlib.sha256(pkg.reference_labeling_sheet_csv).hexdigest()
        )

    def test_no_selection_file_hash_is_null(self):
        pkg = _build(_official(SRC_A), {SRC_A: uuid.uuid4()})
        assert pkg.manifest["source_id_file_sha256"] is None

    def test_counts_and_ambiguous_definition(self):
        ids = {s: uuid.uuid4() for s in (SRC_A, SRC_B, SRC_C)}
        d = _official(SRC_A, SRC_B, SRC_C)
        cands = [
            _candidate(ids[SRC_B], "S1"),
            _candidate(ids[SRC_C], "S1"),
            _candidate(ids[SRC_C], "S2"),
            _candidate(ids[SRC_C], "S3"),
        ]
        m = _build(d, ids, cands).manifest
        assert m["selected_lecturer_count"] == 3
        assert m["lecturers_with_candidates"] == 2
        assert m["lecturers_without_candidates"] == 1
        assert m["candidate_pair_count"] == 4
        # 0 candidates -> not ambiguous, 1 -> not ambiguous, 2+ -> ambiguous
        assert m["ambiguous_lecturer_count"] == 1

    def test_two_candidates_is_ambiguous(self):
        la = uuid.uuid4()
        m = _build(_official(SRC_A), {SRC_A: la}, [_candidate(la, "S1"), _candidate(la, "S2")]).manifest
        assert m["ambiguous_lecturer_count"] == 1

    def test_conflict_count_counts_descriptors_once(self):
        la = uuid.uuid4()
        cands = [_candidate(la, "S1"), _candidate(la, "S2"), _candidate(la, "S3")]
        pkg = _build(_official(SRC_A), {SRC_A: la}, cands, [_conflict(la), _conflict(la)])
        assert pkg.manifest["publication_conflict_count"] == 2
        assert len(_rows(pkg.candidate_review_csv)) == 3  # cells repeat; count must not

    def test_conflicts_of_unselected_lecturers_not_counted(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la}, conflicts=[_conflict(uuid.uuid4())])
        assert pkg.manifest["publication_conflict_count"] == 0

    def test_no_operational_info_or_uuids(self):
        la = uuid.uuid4()
        pkg = _build(_official(SRC_A), {SRC_A: la}, [_candidate(la, "S1")], [_conflict(la)])
        text = pkg.manifest_json.decode("utf-8").lower()
        for word in ("postgres", "password", "host", "port", "database", "token", "secret", str(la)):
            assert word not in text
        assert pkg.manifest["candidate_rule_set_id"] == "M2.7A_CANDIDATE_GENERATOR"
        assert pkg.manifest["candidate_rule_set_version"] == "M2.7A-2"

    def test_determinism(self):
        la = uuid.uuid4()
        cands = [_candidate(la, "S2"), _candidate(la, "S1", rules=("RULE_EXACT_N0", "RULE_TITLE_STRIPPED_N0"))]
        a = _build(_official(SRC_A), {SRC_A: la}, cands, [_conflict(la)])
        b = _build(_official(SRC_A), {SRC_A: la}, list(reversed(cands)), [_conflict(la)])
        assert a.candidate_review_csv == b.candidate_review_csv
        assert a.reference_labeling_sheet_csv == b.reference_labeling_sheet_csv


# ===========================================================================
# CLI SAFETY
# ===========================================================================


class TestBuildCli:
    _SECRETS = ("internal-db", "DO_NOT_LEAK", "secret_db")

    def _load_cli(self):
        script = Path(__file__).resolve().parents[2] / "scripts" / "build_matching_review_package.py"
        spec = importlib.util.spec_from_file_location("build_matching_review_package_cli", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _dataset(self) -> tuple[Path, Path]:
        td = Path(tempfile.mkdtemp())
        dataset = td / "lecturers.json"
        dataset.write_bytes(
            _dataset_bytes([{"source_id": SRC_A, "full_name": "Name A", "institutional_email": "a@ictu.edu.vn"}])
        )
        return dataset, Path(tempfile.mkdtemp())

    def _args(self, dataset: Path, out: Path, *extra: str) -> list[str]:
        return ["--lecturer-dataset", str(dataset), "--output-dir", str(out), *extra]

    def _env(self, monkeypatch, environment: str = "local"):
        from app.core.config import settings

        monkeypatch.setattr(settings, "environment", environment)

    def _sensitive_error(self):
        from sqlalchemy.exc import OperationalError

        return OperationalError(
            "SELECT 1", {}, Exception("host=internal-db password=DO_NOT_LEAK database=secret_db")
        )

    def _fake_db(self, monkeypatch, execute_error=None):
        import sqlalchemy
        import sqlalchemy.orm

        state = SimpleNamespace(disposed=False, created=False)

        class _Engine:
            def dispose(self):
                state.disposed = True

        class _Session:
            def __init__(self, *_a, **_k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def execute(self, *_a, **_k):
                if execute_error is not None:
                    raise execute_error

        def _create(*_a, **_k):
            state.created = True
            return _Engine()

        monkeypatch.setattr(sqlalchemy, "create_engine", _create)
        monkeypatch.setattr(sqlalchemy.orm, "Session", _Session)
        return state

    def _assert_redacted(self, capsys, phrase: str):
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        for secret in self._SECRETS:
            assert secret not in combined
        assert "OperationalError" not in combined and "Traceback" not in combined
        assert phrase in combined

    def test_prod_refused_before_any_database_connection(self, monkeypatch, capsys):
        cli = self._load_cli()
        self._env(monkeypatch, "prod")
        state = self._fake_db(monkeypatch)
        dataset, out = self._dataset()
        assert cli.main(self._args(dataset, out)) != 0
        assert state.created is False
        assert "prod" in capsys.readouterr().err

    def test_read_only_failure_fails_closed_and_is_redacted(self, monkeypatch, capsys):
        cli = self._load_cli()
        self._env(monkeypatch)
        state = self._fake_db(monkeypatch, execute_error=self._sensitive_error())
        dataset, out = self._dataset()
        assert cli.main(self._args(dataset, out)) != 0
        assert state.disposed is True
        assert not any((out / name).exists() for name in cli._PACKAGE_FILES)
        self._assert_redacted(capsys, "read-only database transaction")

    def test_sqlalchemy_error_during_generation_is_redacted_and_engine_disposed(self, monkeypatch, capsys):
        cli = self._load_cli()
        self._env(monkeypatch)
        state = self._fake_db(monkeypatch)
        error = self._sensitive_error()

        def _boom(*_a, **_k):
            raise error

        monkeypatch.setattr(rp, "resolve_canonical_lecturers_from_db", _boom)
        dataset, out = self._dataset()
        assert cli.main(self._args(dataset, out)) != 0
        assert state.disposed is True
        self._assert_redacted(capsys, "failed safely")

    def test_cli_source_never_binds_database_exceptions(self):
        script = Path(__file__).resolve().parents[2] / "scripts" / "build_matching_review_package.py"
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                if ast.unparse(node.type) in {"Exception", "SQLAlchemyError"}:
                    assert node.name is None

    def _patch_pipeline(self, monkeypatch):
        lecturer = uuid.uuid4()
        monkeypatch.setattr(rp, "resolve_canonical_lecturers_from_db", lambda selected, _s: {SRC_A: lecturer})
        monkeypatch.setattr(rp, "generate_review_inputs", lambda _ids, _s: ((_candidate(lecturer, "S1"),), ()))

    def test_overwrite_protection_and_scoped_overwrite(self, monkeypatch, capsys):
        cli = self._load_cli()
        self._env(monkeypatch)
        self._fake_db(monkeypatch)
        self._patch_pipeline(monkeypatch)
        dataset, out = self._dataset()

        assert cli.main(self._args(dataset, out)) == 0
        capsys.readouterr()
        for name in cli._PACKAGE_FILES:
            assert (out / name).is_file()

        human_work = out / "human_notes.txt"
        human_work.write_text("keep me", encoding="utf-8")
        sheet = out / "reference_labeling_sheet.csv"
        sheet.write_text("HUMAN EDITED", encoding="utf-8")

        assert cli.main(self._args(dataset, out)) != 0  # no --overwrite
        assert sheet.read_text(encoding="utf-8") == "HUMAN EDITED"
        capsys.readouterr()

        assert cli.main(self._args(dataset, out, "--overwrite")) == 0
        assert sheet.read_text(encoding="utf-8") != "HUMAN EDITED"
        assert human_work.read_text(encoding="utf-8") == "keep me"
        assert sorted(p.name for p in out.iterdir()) == sorted([*cli._PACKAGE_FILES, "human_notes.txt"])

    def test_generated_package_has_blank_labels(self, monkeypatch, capsys):
        cli = self._load_cli()
        self._env(monkeypatch)
        self._fake_db(monkeypatch)
        self._patch_pipeline(monkeypatch)
        dataset, out = self._dataset()
        assert cli.main(self._args(dataset, out)) == 0
        rows = _rows((out / "reference_labeling_sheet.csv").read_bytes())
        assert len(rows) == 1
        assert all(rows[0][c] == "" for c in ("decision", "expected_scopus_id", "confirmation_source", "confirmed_at", "notes"))
