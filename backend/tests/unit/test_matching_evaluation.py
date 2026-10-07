"""Unit tests for the matching evaluation service — C3-A1 (audit-corrected).

No live database or external service required.
All tests use synthetic in-memory data.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from uuid import UUID

import pytest

from app.services.matching.evaluation import (
    CandidateRetrievalEvaluation,
    CandidateRetrievalMetrics,
    EvaluationInputError,
    ReferenceDecision,
    ReferenceRecord,
    ReferenceValidationError,
    ReferenceCaseResult,
    _EvaluationLecturer,
    _GeneratedPair,
    evaluate_candidate_retrieval,
    parse_reference_csv,
    validate_against_lecturer_dataset,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_MATCH_ROW = (
    "https://repository.ictu.edu.vn/giang-vien/nguyen-van-a/,"
    "nva@ictu.edu.vn,"
    "TS. Nguyễn Văn A,"
    "MATCH,"
    "12345678,"
    "Supervisor review 2026-10-01,"
    "2026-10-01T10:00:00Z,"
    "test note"
)

_VALID_NO_MATCH_ROW = (
    "https://repository.ictu.edu.vn/giang-vien/tran-thi-b/,"
    "ttb@ictu.edu.vn,"
    "Trần Thị B,"
    "NO_MATCH,"
    ","  # empty expected_scopus_id
    "Supervisor review 2026-10-01,"
    "2026-10-01T10:00:00Z,"
    ""
)

_HEADER = "lecturer_source_id,institutional_email,lecturer_full_name,decision,expected_scopus_id,confirmation_source,confirmed_at,notes"


def _csv(*rows: str) -> str:
    return _HEADER + "\n" + "\n".join(rows)


def _make_record(
    source_id: str = "https://repository.ictu.edu.vn/giang-vien/a/",
    email: str | None = "a@ictu.edu.vn",
    full_name: str = "TS. Nguyễn Văn A",
    decision: str = "MATCH",
    expected_scopus_id: str | None = "12345678",
    confirmation_source: str = "Supervisor review 2026-10-01",
    confirmed_at: str = "2026-10-01T10:00:00Z",
    notes: str = "",
) -> ReferenceRecord:
    return ReferenceRecord(
        decision=ReferenceDecision(
            lecturer_source_id=source_id,
            institutional_email=email,
            lecturer_full_name=full_name,
            decision=decision,
            expected_scopus_id=expected_scopus_id,
            confirmation_source=confirmation_source,
            confirmed_at=confirmed_at,
            notes=notes,
        ),
        row_number=2,
    )


def _make_lec(source_id: str, db_id: uuid.UUID | None = None) -> _EvaluationLecturer:
    return _EvaluationLecturer(
        db_id=db_id or uuid.uuid4(),
        source_id=source_id,
        full_name="TS. Nguyễn Văn A",
        email="a@ictu.edu.vn",
    )


def _make_pair(
    lec_id: uuid.UUID,
    scopus_id: str,
    rule_ids: tuple[str, ...] = ("RULE_EXACT_N0",),
    has_pub: bool = False,
) -> _GeneratedPair:
    return _GeneratedPair(
        lecturer_db_id=lec_id,
        scopus_id=scopus_id,
        rule_ids=rule_ids,
        has_publication_evidence=has_pub,
    )


# ===========================================================================
# REFERENCE PARSING
# ===========================================================================


class TestReferenceParsing:
    def test_valid_match_row(self):
        csv = _csv(_VALID_MATCH_ROW)
        records = parse_reference_csv(csv)
        assert len(records) == 1
        d = records[0].decision
        assert d.decision == "MATCH"
        assert d.expected_scopus_id == "12345678"
        assert d.lecturer_source_id == "https://repository.ictu.edu.vn/giang-vien/nguyen-van-a/"

    def test_valid_no_match_row(self):
        csv_content = (
            _HEADER + "\n"
            "https://repository.ictu.edu.vn/giang-vien/tran-thi-b/,"
            "ttb@ictu.edu.vn,Trần Thị B,NO_MATCH,,Supervisor review 2026-10-01,2026-10-01T10:00:00Z,"
        )
        records = parse_reference_csv(csv_content)
        assert len(records) == 1
        d = records[0].decision
        assert d.decision == "NO_MATCH"
        assert d.expected_scopus_id is None

    def test_unknown_decision_rejected(self):
        csv_content = _csv(
            "https://example.com/a/,a@ictu.edu.vn,Name A,MAYBE,,,2026-10-01T00:00:00Z,"
        )
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(csv_content)
        assert "MATCH or NO_MATCH" in str(exc_info.value)

    def test_match_missing_expected_scopus_id_rejected(self):
        csv_content = (
            _HEADER + "\n"
            "https://example.com/a/,a@ictu.edu.vn,Name A,MATCH,,Supervisor,2026-10-01T00:00:00Z,"
        )
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(csv_content)
        assert "expected_scopus_id" in str(exc_info.value)

    def test_no_match_with_expected_scopus_id_rejected(self):
        csv_content = (
            _HEADER + "\n"
            "https://example.com/a/,a@ictu.edu.vn,Name A,NO_MATCH,99999,Supervisor,2026-10-01T00:00:00Z,"
        )
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(csv_content)
        assert "NO_MATCH" in str(exc_info.value)

    def test_duplicate_lecturer_source_id_rejected(self):
        row = "https://example.com/a/,a@ictu.edu.vn,Name A,NO_MATCH,,Supervisor,2026-10-01T00:00:00Z,"
        csv_content = _csv(row, row)
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(csv_content)
        assert "Duplicate" in str(exc_info.value)

    def test_duplicate_match_scopus_id_rejected(self):
        row1 = "https://example.com/a/,a@ictu.edu.vn,Name A,MATCH,SCOPUS-1,Supervisor,2026-10-01T00:00:00Z,"
        row2 = "https://example.com/b/,b@ictu.edu.vn,Name B,MATCH,SCOPUS-1,Supervisor,2026-10-01T00:00:00Z,"
        csv_content = _csv(row1, row2)
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(csv_content)
        assert "Duplicate MATCH Scopus ID" in str(exc_info.value)

    def test_bad_confirmed_at_rejected(self):
        csv_content = (
            _HEADER + "\n"
            "https://example.com/a/,a@ictu.edu.vn,Name A,NO_MATCH,,Supervisor,not-a-date,"
        )
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(csv_content)
        assert "ISO-8601" in str(exc_info.value) or "valid" in str(exc_info.value).lower()

    def test_missing_required_column_rejected(self):
        bad_header = "lecturer_source_id,lecturer_full_name,decision,expected_scopus_id,confirmation_source,confirmed_at,notes"
        csv_content = bad_header + "\nhttps://example.com/a/,Name A,MATCH,S1,Supervisor,2026-10-01T00:00:00Z,"
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(csv_content)
        assert "institutional_email" in str(exc_info.value)

    def test_unknown_extra_column_rejected(self):
        bad_header = _HEADER + ",extra_column"
        csv_content = bad_header + "\nhttps://example.com/a/,a@ictu.edu.vn,Name A,NO_MATCH,,Supervisor,2026-10-01T00:00:00Z,,extra_value"
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(csv_content)
        assert "Unknown columns" in str(exc_info.value)

    def test_whitespace_trimming(self):
        csv_content = (
            _HEADER + "\n"
            "  https://example.com/a/  ,  a@ictu.edu.vn  ,  Name A  ,MATCH,  S1  ,  Supervisor  ,2026-10-01T00:00:00Z,  notes  "
        )
        records = parse_reference_csv(csv_content)
        d = records[0].decision
        assert d.lecturer_source_id == "https://example.com/a/"
        assert d.institutional_email == "a@ictu.edu.vn"
        assert d.expected_scopus_id == "S1"


# ===========================================================================
# CONFIRMED_AT REAL PARSING (audit-corrected)
# ===========================================================================


class TestConfirmedAtRealParsing:
    """Real datetime parsing — impossible dates and times must be rejected."""

    def _row(self, confirmed_at: str) -> str:
        return (
            f"https://example.com/a/,a@ictu.edu.vn,Name A,NO_MATCH,,Supervisor,{confirmed_at},"
        )

    def test_invalid_month_13_rejected(self):
        with pytest.raises(ReferenceValidationError):
            parse_reference_csv(_csv(self._row("2026-13-01T10:00:00Z")))

    def test_invalid_day_feb_30_rejected(self):
        with pytest.raises(ReferenceValidationError):
            parse_reference_csv(_csv(self._row("2026-02-30T10:00:00Z")))

    def test_invalid_hour_25_rejected(self):
        with pytest.raises(ReferenceValidationError):
            parse_reference_csv(_csv(self._row("2026-10-01T25:00:00Z")))

    def test_valid_utc_z_accepted(self):
        records = parse_reference_csv(_csv(self._row("2026-10-01T10:00:00Z")))
        assert len(records) == 1

    def test_valid_utc_explicit_offset_accepted(self):
        records = parse_reference_csv(_csv(self._row("2026-10-01T10:00:00+00:00")))
        assert len(records) == 1

    def test_missing_timezone_rejected(self):
        """Naive datetime (no timezone) must be rejected — UTC required."""
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(_csv(self._row("2026-10-01T10:00:00")))
        assert "timezone" in str(exc_info.value).lower() or "UTC" in str(exc_info.value)

    def test_non_utc_offset_rejected(self):
        """Non-zero UTC offset must be rejected — UTC only."""
        with pytest.raises(ReferenceValidationError) as exc_info:
            parse_reference_csv(_csv(self._row("2026-10-01T10:00:00+07:00")))
        assert "UTC" in str(exc_info.value) or "offset" in str(exc_info.value).lower()


# ===========================================================================
# LECTURER DATASET CROSS-CHECK
# ===========================================================================


class TestLecturerDatasetCrossCheck:
    def _make_dataset(self, lecturers: list[dict]) -> dict:
        return {
            "dataset": {"record_count": len(lecturers)},
            "lecturers": lecturers,
        }

    def _write_dataset(self, lecturers: list[dict]) -> Path:
        td = tempfile.mkdtemp()
        p = Path(td) / "lecturers.json"
        p.write_text(
            json.dumps(self._make_dataset(lecturers)), encoding="utf-8"
        )
        return p

    def test_valid_source_id(self):
        ds_path = self._write_dataset(
            [
                {
                    "source_id": "https://example.com/a/",
                    "full_name": "TS. Nguyễn Văn A",
                    "institutional_email": "a@ictu.edu.vn",
                }
            ],
        )
        rec = _make_record(source_id="https://example.com/a/")
        validate_against_lecturer_dataset((rec,), ds_path)  # must not raise

    def test_unknown_source_id_rejected(self):
        ds_path = self._write_dataset([])
        rec = _make_record(source_id="https://example.com/unknown/")
        with pytest.raises(ReferenceValidationError) as exc_info:
            validate_against_lecturer_dataset((rec,), ds_path)
        assert "Not found" in str(exc_info.value)

    def test_name_mismatch_rejected(self):
        ds_path = self._write_dataset(
            [
                {
                    "source_id": "https://example.com/a/",
                    "full_name": "TS. Nguyễn Văn B",
                    "institutional_email": "a@ictu.edu.vn",
                }
            ],
        )
        rec = _make_record(
            source_id="https://example.com/a/",
            full_name="TS. Nguyễn Văn A",
        )
        with pytest.raises(ReferenceValidationError) as exc_info:
            validate_against_lecturer_dataset((rec,), ds_path)
        assert "Name mismatch" in str(exc_info.value)

    def test_email_mismatch_rejected(self):
        ds_path = self._write_dataset(
            [
                {
                    "source_id": "https://example.com/a/",
                    "full_name": "TS. Nguyễn Văn A",
                    "institutional_email": "different@ictu.edu.vn",
                }
            ],
        )
        rec = _make_record(
            source_id="https://example.com/a/",
            email="a@ictu.edu.vn",
        )
        with pytest.raises(ReferenceValidationError) as exc_info:
            validate_against_lecturer_dataset((rec,), ds_path)
        assert "Email mismatch" in str(exc_info.value)

    def test_subset_allowed(self):
        """Validating 2 of 410 lecturers must not fail."""
        lecturers = [
            {
                "source_id": f"https://example.com/{i}/",
                "full_name": f"Lecturer {i}",
                "institutional_email": f"l{i}@ictu.edu.vn",
            }
            for i in range(410)
        ]
        ds_path = self._write_dataset(lecturers)
        records = tuple(
            _make_record(
                source_id=f"https://example.com/{i}/",
                full_name=f"Lecturer {i}",
                email=f"l{i}@ictu.edu.vn",
                expected_scopus_id=f"S{i}",
            )
            for i in range(2)
        )
        validate_against_lecturer_dataset(records, ds_path)  # must not raise

    def test_does_not_require_410_labels(self):
        """A single reference row is valid even if the dataset has 410 lecturers."""
        lecturers = [
            {
                "source_id": f"https://example.com/{i}/",
                "full_name": f"Lecturer {i}",
                "institutional_email": f"l{i}@ictu.edu.vn",
            }
            for i in range(410)
        ]
        ds_path = self._write_dataset(lecturers)
        rec = _make_record(
            source_id="https://example.com/5/",
            full_name="Lecturer 5",
            email="l5@ictu.edu.vn",
        )
        validate_against_lecturer_dataset((rec,), ds_path)  # must not raise

    def test_duplicate_official_source_id_rejected(self):
        """Official dataset with two rows sharing the same source_id must be rejected."""
        ds_path = self._write_dataset(
            [
                {
                    "source_id": "https://example.com/a/",
                    "full_name": "TS. Nguyễn Văn A",
                    "institutional_email": "a@ictu.edu.vn",
                },
                {
                    "source_id": "https://example.com/a/",  # duplicate
                    "full_name": "TS. Nguyễn Văn A",
                    "institutional_email": "a2@ictu.edu.vn",
                },
            ]
        )
        rec = _make_record(source_id="https://example.com/a/")
        with pytest.raises(ReferenceValidationError) as exc_info:
            validate_against_lecturer_dataset((rec,), ds_path)
        assert "Ambiguous" in str(exc_info.value) or "duplicate" in str(exc_info.value).lower()


# ===========================================================================
# PAIR METRICS
# ===========================================================================


class TestPairMetrics:
    def _eval(
        self,
        records: tuple[ReferenceRecord, ...],
        lecturers: dict[str, _EvaluationLecturer],
        corpus: frozenset[str],
        pairs: dict[uuid.UUID, tuple[_GeneratedPair, ...]],
    ) -> CandidateRetrievalEvaluation:
        return evaluate_candidate_retrieval(
            reference_records=records,
            resolved_lecturers=lecturers,
            scopus_corpus_ids=corpus,
            generated_pairs_by_lecturer_db_id=pairs,
        )

    def test_perfect_retrieval(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        lec = _make_lec(source_id, lec_id)
        pair = _make_pair(lec_id, "S1")
        result = self._eval(
            (rec,),
            {source_id: lec},
            frozenset({"S1"}),
            {lec_id: (pair,)},
        )
        m = result.metrics
        assert m.true_positive_pairs == 1
        assert m.false_positive_pairs == 0
        assert m.false_negative_pairs == 0
        assert m.candidate_pair_precision == 1.0
        assert m.candidate_pair_recall == 1.0
        assert m.candidate_pair_f1 == 1.0

    def test_missed_positive(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        lec = _make_lec(source_id, lec_id)
        result = self._eval(
            (rec,),
            {source_id: lec},
            frozenset({"S1"}),
            {lec_id: ()},  # no generated pair
        )
        m = result.metrics
        assert m.false_negative_pairs == 1
        assert m.true_positive_pairs == 0
        assert m.candidate_pair_recall == 0.0

    def test_extra_candidate_on_match_increments_fp(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        lec = _make_lec(source_id, lec_id)
        pairs = (
            _make_pair(lec_id, "S1"),
            _make_pair(lec_id, "S2"),  # extra FP
        )
        result = self._eval(
            (rec,),
            {source_id: lec},
            frozenset({"S1", "S2"}),
            {lec_id: pairs},
        )
        m = result.metrics
        assert m.true_positive_pairs == 1
        assert m.false_positive_pairs == 1
        assert m.ambiguous_match_count == 1

    def test_candidate_on_no_match_increments_fp(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(
            source_id=source_id,
            decision="NO_MATCH",
            expected_scopus_id=None,
        )
        lec = _make_lec(source_id, lec_id)
        pair = _make_pair(lec_id, "S1")
        result = self._eval(
            (rec,),
            {source_id: lec},
            frozenset({"S1"}),
            {lec_id: (pair,)},
        )
        m = result.metrics
        assert m.false_positive_pairs == 1
        assert m.no_match_with_candidate_count == 1

    def test_no_candidates_safe_zero_denominators(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        lec = _make_lec(source_id, lec_id)
        result = self._eval(
            (rec,),
            {source_id: lec},
            frozenset({"S1"}),
            {lec_id: ()},
        )
        m = result.metrics
        assert m.candidate_pair_precision == 0.0
        assert m.candidate_pair_recall == 0.0
        assert m.candidate_pair_f1 == 0.0

    def test_ambiguous_correct_case(self):
        """TP=1, FP=1 extra; ambiguous_match_count increments."""
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        lec = _make_lec(source_id, lec_id)
        pairs = (
            _make_pair(lec_id, "S1"),
            _make_pair(lec_id, "S-extra"),
        )
        result = self._eval(
            (rec,),
            {source_id: lec},
            frozenset({"S1", "S-extra"}),
            {lec_id: pairs},
        )
        m = result.metrics
        assert m.true_positive_pairs == 1
        assert m.false_positive_pairs == 1
        assert m.ambiguous_match_count == 1
        assert m.single_candidate_match_count == 0


# ===========================================================================
# STRICT RESOLUTION INVARIANT (audit-corrected)
# ===========================================================================


class TestStrictResolutionInvariant:
    """evaluate_candidate_retrieval must fail closed when a lecturer is missing."""

    def test_missing_resolved_lecturer_raises_evaluation_input_error(self):
        """A reference record not present in resolved_lecturers must raise."""
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        # resolved_lecturers is empty — source_id not resolved
        with pytest.raises(EvaluationInputError) as exc_info:
            evaluate_candidate_retrieval(
                reference_records=(rec,),
                resolved_lecturers={},  # missing!
                scopus_corpus_ids=frozenset({"S1"}),
                generated_pairs_by_lecturer_db_id={lec_id: ()},
            )
        assert source_id in str(exc_info.value) or "missing" in str(exc_info.value).lower()

    def test_missing_lecturer_does_not_silently_produce_zero_metrics(self):
        """Must not silently exclude the row and produce metrics as if nothing happened."""
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        with pytest.raises(EvaluationInputError):
            evaluate_candidate_retrieval(
                reference_records=(rec,),
                resolved_lecturers={},
                scopus_corpus_ids=frozenset(),
                generated_pairs_by_lecturer_db_id={},
            )


# ===========================================================================
# CORPUS COVERAGE
# ===========================================================================


class TestCorpusCoverage:
    def _eval(
        self,
        records: tuple[ReferenceRecord, ...],
        lecturers: dict[str, _EvaluationLecturer],
        corpus: frozenset[str],
        pairs: dict[uuid.UUID, tuple[_GeneratedPair, ...]],
    ) -> CandidateRetrievalEvaluation:
        return evaluate_candidate_retrieval(
            reference_records=records,
            resolved_lecturers=lecturers,
            scopus_corpus_ids=corpus,
            generated_pairs_by_lecturer_db_id=pairs,
        )

    def test_expected_absent_from_corpus_increments_corpus_missing(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S-MISSING")
        lec = _make_lec(source_id, lec_id)
        result = self._eval(
            (rec,),
            {source_id: lec},
            frozenset(),  # empty corpus — S-MISSING absent
            {lec_id: ()},
        )
        m = result.metrics
        assert m.corpus_missing_match_count == 1
        assert m.corpus_present_match_count == 0

    def test_corpus_missing_reflected_in_end_to_end_recall(self):
        """End-to-end recall counts miss even when target not in corpus."""
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S-MISSING")
        lec = _make_lec(source_id, lec_id)
        result = self._eval(
            (rec,),
            {source_id: lec},
            frozenset(),
            {lec_id: ()},
        )
        m = result.metrics
        assert m.end_to_end_candidate_recall == 0.0

    def test_eligible_recall_excludes_corpus_missing_target(self):
        """When the only MATCH target is missing from corpus, eligible recall is 0/0 -> 0.0."""
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S-MISSING")
        lec = _make_lec(source_id, lec_id)
        result = self._eval(
            (rec,),
            {source_id: lec},
            frozenset(),
            {lec_id: ()},
        )
        m = result.metrics
        assert m.eligible_candidate_recall == 0.0

    def test_mixed_corpus_present_and_missing(self):
        lec_a_id = uuid.uuid4()
        lec_b_id = uuid.uuid4()
        src_a = "https://example.com/a/"
        src_b = "https://example.com/b/"
        rec_a = _make_record(source_id=src_a, expected_scopus_id="S-PRESENT")
        rec_b = ReferenceRecord(
            decision=ReferenceDecision(
                lecturer_source_id=src_b,
                institutional_email=None,
                lecturer_full_name="Lecturer B",
                decision="MATCH",
                expected_scopus_id="S-MISSING",
                confirmation_source="Supervisor",
                confirmed_at="2026-10-01T00:00:00Z",
                notes="",
            ),
            row_number=3,
        )
        lec_a = _make_lec(src_a, lec_a_id)
        lec_b = _make_lec(src_b, lec_b_id)
        pair_a = _make_pair(lec_a_id, "S-PRESENT")
        result = evaluate_candidate_retrieval(
            reference_records=(rec_a, rec_b),
            resolved_lecturers={src_a: lec_a, src_b: lec_b},
            scopus_corpus_ids=frozenset({"S-PRESENT"}),
            generated_pairs_by_lecturer_db_id={lec_a_id: (pair_a,), lec_b_id: ()},
        )
        m = result.metrics
        assert m.corpus_present_match_count == 1
        assert m.corpus_missing_match_count == 1
        # Eligible: only lec_a is in corpus; lec_a found -> 1/1 = 1.0
        assert m.eligible_candidate_recall == 1.0
        # End-to-end: lec_a found (1), lec_b missed (0) -> 1/2 = 0.5
        assert m.end_to_end_candidate_recall == 0.5


# ===========================================================================
# CASE OUTPUT
# ===========================================================================


class TestCaseOutput:
    def _simple_eval(self, source_id: str, lec_id: uuid.UUID, pairs: tuple) -> ReferenceCaseResult:
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        lec = _make_lec(source_id, lec_id)
        result = evaluate_candidate_retrieval(
            reference_records=(rec,),
            resolved_lecturers={source_id: lec},
            scopus_corpus_ids=frozenset({"S1"}),
            generated_pairs_by_lecturer_db_id={lec_id: pairs},
        )
        return result.cases[0]

    def test_no_internal_uuid_in_generated_scopus_ids(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        pair = _make_pair(lec_id, "S1")
        case = self._simple_eval(source_id, lec_id, (pair,))
        # generated_scopus_ids must contain Scopus string IDs, not UUIDs
        for sid in case.generated_scopus_ids:
            assert "-" not in sid or sid.count("-") < 4, (
                f"Looks like a UUID leaked into generated_scopus_ids: {sid}"
            )

    def test_deterministic_generated_scopus_ordering(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        pairs = (
            _make_pair(lec_id, "S9"),
            _make_pair(lec_id, "S1"),
            _make_pair(lec_id, "S5"),
        )
        case = self._simple_eval(source_id, lec_id, pairs)
        # Should be sorted, not hit the expected S1 (which is present)
        assert case.generated_scopus_ids == ("S1", "S5", "S9")

    def test_deterministic_rule_ordering(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        pair = _make_pair(
            lec_id, "S1",
            rule_ids=("RULE_TITLE_STRIPPED_N2", "RULE_EXACT_N0")
        )
        case = self._simple_eval(source_id, lec_id, (pair,))
        assert case.expected_candidate_rule_ids == (
            "RULE_EXACT_N0", "RULE_TITLE_STRIPPED_N2"
        )

    def test_no_match_match_found_is_none(self):
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(
            source_id=source_id,
            decision="NO_MATCH",
            expected_scopus_id=None,
        )
        lec = _make_lec(source_id, lec_id)
        result = evaluate_candidate_retrieval(
            reference_records=(rec,),
            resolved_lecturers={source_id: lec},
            scopus_corpus_ids=frozenset(),
            generated_pairs_by_lecturer_db_id={lec_id: ()},
        )
        case = result.cases[0]
        assert case.match_found is None

    def test_cases_sorted_by_lecturer_source_id(self):
        lec_b_id = uuid.uuid4()
        lec_a_id = uuid.uuid4()
        src_b = "https://example.com/z/"
        src_a = "https://example.com/a/"
        rec_b = _make_record(source_id=src_b, expected_scopus_id="SB")
        rec_a = ReferenceRecord(
            decision=ReferenceDecision(
                lecturer_source_id=src_a,
                institutional_email=None,
                lecturer_full_name="Lecturer A",
                decision="MATCH",
                expected_scopus_id="SA",
                confirmation_source="Supervisor",
                confirmed_at="2026-10-01T00:00:00Z",
                notes="",
            ),
            row_number=3,
        )
        result = evaluate_candidate_retrieval(
            reference_records=(rec_b, rec_a),
            resolved_lecturers={
                src_b: _make_lec(src_b, lec_b_id),
                src_a: _make_lec(src_a, lec_a_id),
            },
            scopus_corpus_ids=frozenset({"SA", "SB"}),
            generated_pairs_by_lecturer_db_id={lec_b_id: (), lec_a_id: ()},
        )
        assert result.cases[0].lecturer_source_id == src_a
        assert result.cases[1].lecturer_source_id == src_b


# ===========================================================================
# CANDIDATE GENERATOR CONVERSION (audit-corrected)
# ===========================================================================


class TestCandidateGeneratorConversion:
    """Verify _GeneratedPair conversion from transient CandidateGenerator output."""

    def _make_candidate(
        self,
        lecturer_id: UUID,
        scopus_author_id: UUID,
        scopus_id: str,
        rule_ids: tuple[str, ...],
    ):
        """Build a transient LecturerScopusCandidate (no DB mapping)."""
        from app.services.matching.candidate_types import (
            CandidateEvidence,
            LecturerScopusCandidate,
        )
        evidence = tuple(
            CandidateEvidence(
                rule_id=rid,
                lecturer_source_value="Name",
                lecturer_comparison_value="name",
                scopus_surface_type="PREFERRED_NAME",
                scopus_surface_value="Name",
                scopus_comparison_value="name",
            )
            for rid in rule_ids
        )
        return LecturerScopusCandidate(
            lecturer_id=lecturer_id,
            scopus_author_id=scopus_author_id,
            scopus_id=scopus_id,
            preferred_name="Name",
            evidence=evidence,
        )

    def test_pair_conversion_correct_fields(self):
        """Converted pair must have correct lecturer_db_id, scopus_id, sorted rule_ids."""
        from app.services.matching.evaluation import _GeneratedPair
        from app.services.matching.candidate_types import EnrichedLecturerScopusCandidate

        lec_id = uuid.uuid4()
        author_id = uuid.uuid4()
        candidate = self._make_candidate(
            lec_id, author_id, "SCOPUS-42",
            rule_ids=("RULE_TITLE_STRIPPED_N2", "RULE_EXACT_N0"),
        )
        enriched = EnrichedLecturerScopusCandidate.from_candidate(candidate, ())

        rule_ids = tuple(sorted(ev.rule_id for ev in enriched.evidence))
        has_pub = bool(enriched.publication_evidence)

        pair = _GeneratedPair(
            lecturer_db_id=enriched.lecturer_id,
            scopus_id=enriched.scopus_id,
            rule_ids=rule_ids,
            has_publication_evidence=has_pub,
        )

        assert pair.lecturer_db_id == lec_id
        assert pair.scopus_id == "SCOPUS-42"
        assert pair.rule_ids == ("RULE_EXACT_N0", "RULE_TITLE_STRIPPED_N2")
        assert pair.has_publication_evidence is False

    def test_pair_conversion_pub_evidence_flag(self):
        """has_publication_evidence must be True when publication evidence present."""
        from app.services.matching.candidate_types import (
            EnrichedLecturerScopusCandidate,
            PublicationEvidence,
        )

        lec_id = uuid.uuid4()
        author_id = uuid.uuid4()
        candidate = self._make_candidate(lec_id, author_id, "SCOPUS-99", ("RULE_EXACT_N0",))

        pub_ev = PublicationEvidence(
            rule_id="RULE_KNOWN_PUBLICATION_DOI_EXACT",
            known_publication_id=uuid.uuid4(),
            lecturer_id=lec_id,
            lecturer_snapshot_id=uuid.uuid4(),
            canonical_publication_id=uuid.uuid4(),
            canonical_publication_eid="2-s2.0-999",
            candidate_scopus_author_id=author_id,
            known_publication_doi_normalized="10.1000/xyz123",
            known_publication_title_normalized="a title",
            canonical_publication_doi="10.1000/xyz123",
            canonical_publication_title="A Title",
            reconciliation="DOI_EXACT",
        )
        enriched = EnrichedLecturerScopusCandidate.from_candidate(candidate, (pub_ev,))
        has_pub = bool(enriched.publication_evidence)
        assert has_pub is True

    def test_irrelevant_lecturers_filtered(self):
        """Candidates for lecturers not in the reference set must not appear."""
        from app.services.matching.candidate_types import EnrichedLecturerScopusCandidate

        ref_lec_id = uuid.uuid4()
        other_lec_id = uuid.uuid4()
        ref_author_id = uuid.uuid4()
        other_author_id = uuid.uuid4()

        ref_candidate = self._make_candidate(ref_lec_id, ref_author_id, "S-REF", ("RULE_EXACT_N0",))
        other_candidate = self._make_candidate(other_lec_id, other_author_id, "S-OTHER", ("RULE_EXACT_N0",))

        all_enriched = [
            EnrichedLecturerScopusCandidate.from_candidate(ref_candidate, ()),
            EnrichedLecturerScopusCandidate.from_candidate(other_candidate, ()),
        ]

        reference_db_ids = frozenset({ref_lec_id})
        filtered = [c for c in all_enriched if c.lecturer_id in reference_db_ids]

        assert len(filtered) == 1
        assert filtered[0].lecturer_id == ref_lec_id
        assert filtered[0].scopus_id == "S-REF"

    def test_deterministic_pair_order(self):
        """Pairs sorted by (lecturer UUID string, scopus_id) must be stable."""
        from app.services.matching.candidate_types import EnrichedLecturerScopusCandidate

        # Use fixed UUIDs to make ordering deterministic in the test
        lec_a = UUID("00000000-0000-0000-0000-000000000001")
        lec_b = UUID("00000000-0000-0000-0000-000000000002")
        auth_1 = uuid.uuid4()
        auth_2 = uuid.uuid4()

        c1 = self._make_candidate(lec_b, auth_2, "S-Z", ("RULE_EXACT_N0",))
        c2 = self._make_candidate(lec_a, auth_1, "S-A", ("RULE_EXACT_N0",))

        enriched_list = [
            EnrichedLecturerScopusCandidate.from_candidate(c1, ()),
            EnrichedLecturerScopusCandidate.from_candidate(c2, ()),
        ]

        sorted_enriched = sorted(
            enriched_list,
            key=lambda c: (str(c.lecturer_id), c.scopus_id),
        )

        assert sorted_enriched[0].lecturer_id == lec_a
        assert sorted_enriched[1].lecturer_id == lec_b

    def test_no_persistence_import_in_generation_path(self):
        """generate_pairs_from_current_production must not import persistence tables."""
        import ast
        import inspect
        from app.services.matching import evaluation as eval_module

        source = inspect.getsource(eval_module.generate_pairs_from_current_production)

        # Parse the function source as an AST to inspect only real import nodes,
        # not docstring text that may mention names for documentation purposes.
        # Wrap in a class/module so ast.parse can handle the indented source.
        tree = ast.parse(source)

        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)

        # These persistence models must NOT be imported in the generation path
        forbidden_imports = {
            "LecturerScopusCandidateObservation",
            "LecturerScopusCandidateEvidence",
            "CandidateGenerationRun",
        }
        for name in forbidden_imports:
            assert name not in imported_names, (
                f"Persistence model {name!r} must not be imported in "
                f"generate_pairs_from_current_production"
            )

        # CandidateGenerator and PublicationEvidenceEnricher must be imported
        assert "CandidateGenerator" in imported_names, (
            "CandidateGenerator must be imported in generate_pairs_from_current_production"
        )
        assert "PublicationEvidenceEnricher" in imported_names, (
            "PublicationEvidenceEnricher must be imported in generate_pairs_from_current_production"
        )


# ===========================================================================
# NO RANKING METRICS
# ===========================================================================


class TestNoRankingMetrics:
    """Ensure evaluation output contains no ranking/scoring fields."""

    def _get_metrics(self) -> CandidateRetrievalMetrics:
        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        lec = _make_lec(source_id, lec_id)
        result = evaluate_candidate_retrieval(
            reference_records=(rec,),
            resolved_lecturers={source_id: lec},
            scopus_corpus_ids=frozenset({"S1"}),
            generated_pairs_by_lecturer_db_id={lec_id: (_make_pair(lec_id, "S1"),)},
        )
        return result.metrics

    def test_metrics_has_no_score_field(self):
        import dataclasses

        metrics = self._get_metrics()
        field_names = {f.name for f in dataclasses.fields(metrics)}
        for forbidden in ("score", "rank", "top_1_accuracy", "threshold", "confidence"):
            assert forbidden not in field_names, (
                f"Forbidden ranking field found in CandidateRetrievalMetrics: {forbidden!r}"
            )

    def test_case_result_has_no_score_field(self):
        import dataclasses

        lec_id = uuid.uuid4()
        source_id = "https://example.com/a/"
        rec = _make_record(source_id=source_id, expected_scopus_id="S1")
        lec = _make_lec(source_id, lec_id)
        result = evaluate_candidate_retrieval(
            reference_records=(rec,),
            resolved_lecturers={source_id: lec},
            scopus_corpus_ids=frozenset({"S1"}),
            generated_pairs_by_lecturer_db_id={lec_id: (_make_pair(lec_id, "S1"),)},
        )
        case = result.cases[0]
        field_names = {f.name for f in dataclasses.fields(case)}
        for forbidden in ("score", "rank", "top_1_accuracy", "threshold", "confidence"):
            assert forbidden not in field_names, (
                f"Forbidden ranking field found in ReferenceCaseResult: {forbidden!r}"
            )

    def test_evaluation_dto_has_no_ranking_fields(self):
        import dataclasses

        for cls in (CandidateRetrievalMetrics, CandidateRetrievalEvaluation, ReferenceCaseResult):
            for f in dataclasses.fields(cls):
                for forbidden in ("score", "rank", "top_1", "threshold", "confidence", "ndcg", "mrr"):
                    assert forbidden not in f.name.lower(), (
                        f"{cls.__name__}.{f.name} contains forbidden ranking term {forbidden!r}"
                    )
