"""Unit tests for the verified matching-quality evaluation — C3-A3.

Synthetic fixtures only.  No real human labels, no live database, no
dependency on local Git history (the Git runner is injected).
"""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import inspect
import io
import json
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.matching import evaluation as a1
from app.services.matching import verified_evaluation as ve
from app.services.matching.candidate_persistence import (
    CANDIDATE_RULE_SET_ID,
    CANDIDATE_RULE_SET_VERSION,
)
from app.services.matching.review_package import (
    LABELING_SHEET_COLUMNS,
    OfficialLecturer,
    build_review_package,
    parse_official_lecturers,
)
from app.services.matching.verified_evaluation import (
    COHORT_ALGORITHM,
    COHORT_SEED,
    COHORT_SIZE,
    FROZEN_A2_SHA,
    FROZEN_MATCHING_BLOBS,
    VerificationError,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
_SECRET_SOURCE = "Reviewer Nguyen SECRET-REVIEWER-ID"
_SECRET_NOTE = "PRIVATE-NOTE-DO-NOT-PUBLISH"


# ---------------------------------------------------------------------------
# Synthetic fixture: dataset -> cohort -> real A2 package -> confirmed copy
# ---------------------------------------------------------------------------


def _dataset_rows(n: int = 60) -> list[dict]:
    return [
        {
            "source_id": f"https://repo.example/giang-vien/l{i:03d}/",
            "full_name": f"TS. Lecturer {i:03d}",
            "institutional_email": f"l{i:03d}@ictu.edu.vn",
        }
        for i in range(n)
    ]


def _dataset_bytes(rows: list[dict]) -> bytes:
    return json.dumps({"lecturers": rows}, ensure_ascii=False).encode("utf-8")


def _sheet_rows(sheet_bytes: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(sheet_bytes.decode("utf-8"))))


def _write_sheet(rows: list[dict[str, str]], columns=LABELING_SHEET_COLUMNS) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(columns), lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def _fill(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    filled = []
    for i, row in enumerate(rows):
        row = dict(row)
        if i == 0:
            row.update(decision="MATCH", expected_scopus_id="57000000001")
        else:
            row.update(decision="NO_MATCH", expected_scopus_id="")
        row.update(
            confirmation_source=_SECRET_SOURCE,
            confirmed_at="2026-10-08T09:00:00Z",
            notes=_SECRET_NOTE if i == 1 else "",
        )
        filled.append(row)
    return filled


class _Fixture:
    def __init__(self, n: int = 60):
        self.rows = _dataset_rows(n)
        self.dataset = _dataset_bytes(self.rows)
        td = Path(tempfile.mkdtemp())
        self.dataset_path = td / "lecturers.json"
        self.dataset_path.write_bytes(self.dataset)
        self.cohort = ve.select_primary_cohort(self.dataset)
        self.cohort_bytes = ve.render_cohort_file(self.cohort)
        official = {l.source_id: l for l in parse_official_lecturers(self.dataset)}
        selected = tuple(official[s] for s in self.cohort)
        self.canonical = {s: uuid.uuid4() for s in self.cohort}
        pkg = build_review_package(
            selected=selected,
            canonical_ids=self.canonical,
            enriched_candidates=(),
            conflicts=(),
            official_dataset_bytes=self.dataset,
            source_id_file_bytes=self.cohort_bytes,
            rule_set_id=CANDIDATE_RULE_SET_ID,
            rule_set_version=CANDIDATE_RULE_SET_VERSION,
            generated_at=_NOW,
        )
        self.candidate_review = pkg.candidate_review_csv
        self.sheet = pkg.reference_labeling_sheet_csv
        self.manifest = dict(pkg.manifest)
        self.confirmed = _write_sheet(_fill(_sheet_rows(self.sheet)))

    def manifest_bytes(self, **overrides) -> bytes:
        return json.dumps({**self.manifest, **overrides}).encode("utf-8")

    def kwargs(self, **overrides):
        base = dict(
            candidate_review_bytes=self.candidate_review,
            labeling_sheet_bytes=self.sheet,
            manifest_bytes=self.manifest_bytes(),
            confirmed_bytes=self.confirmed,
            dataset_bytes=self.dataset,
            dataset_path=self.dataset_path,
            source_id_file_bytes=self.cohort_bytes,
            committed_cohort_bytes=self.cohort_bytes,
            repo_root=_REPO_ROOT,
            runner=_git_runner(),
        )
        base.update(overrides)
        return base


def _git_runner(current: dict[str, str] | None = None, frozen: dict[str, str] | None = None, fail: bool = False):
    anchors = dict(FROZEN_MATCHING_BLOBS)
    calls: list[list[str]] = []

    def run(cmd, **kwargs):
        calls.append(list(cmd))
        assert isinstance(cmd, list) and kwargs.get("shell") is not True
        if fail:
            raise FileNotFoundError("git")
        if cmd[1] == "rev-parse":
            path = cmd[2].split(":", 1)[1]
            blob = (frozen or {}).get(path, anchors[path])
        else:
            path = cmd[-1]
            blob = (current or {}).get(path, anchors[path])
        return subprocess.CompletedProcess(cmd, 0, stdout=blob + "\n", stderr="")

    run.calls = calls
    return run


@pytest.fixture()
def fx() -> _Fixture:
    return _Fixture()


# ===========================================================================
# COHORT SELECTION
# ===========================================================================


class TestCohortSelection:
    def test_fixed_algorithm_seed_size(self):
        assert (COHORT_ALGORITHM, COHORT_SEED, COHORT_SIZE) == (
            "SHA256_SEED_RANK_V1",
            "C3-A3-ICTU-PRIMARY-2026-V1",
            50,
        )

    def test_matches_reference_definition(self):
        rows = _dataset_rows(80)
        ids = [r["source_id"] for r in rows]
        digest = lambda s: hashlib.sha256(COHORT_SEED.encode() + b"\x00" + s.encode()).hexdigest()
        expected = tuple(sorted(sorted(ids, key=lambda s: (digest(s), s))[:50]))
        assert ve.select_primary_cohort(_dataset_bytes(rows)) == expected

    def test_deterministic_unique_sorted_and_order_independent(self):
        rows = _dataset_rows(80)
        a = ve.select_primary_cohort(_dataset_bytes(rows))
        b = ve.select_primary_cohort(_dataset_bytes(list(reversed(rows))))
        assert a == b == ve.select_primary_cohort(_dataset_bytes(rows))
        assert len(a) == len(set(a)) == 50
        assert list(a) == sorted(a)

    def test_depends_only_on_source_ids(self):
        rows = _dataset_rows(80)
        noisy = [
            {**r, "full_name": "X", "candidate_count": 9, "publication_conflicts": 3, "scopus_id": "1"}
            for r in rows
        ]
        assert ve.select_primary_cohort(_dataset_bytes(rows)) == ve.select_primary_cohort(_dataset_bytes(noisy))

    def test_output_file_format(self):
        content = ve.render_cohort_file(("a", "b"))
        assert content == b"a\nb\n"

    def test_too_few_official_rows_fails_closed(self):
        with pytest.raises(VerificationError):
            ve.select_primary_cohort(_dataset_bytes(_dataset_rows(49)))

    def test_duplicate_official_source_id_rejected(self):
        rows = _dataset_rows(60)
        rows.append(dict(rows[0]))
        with pytest.raises(VerificationError):
            ve.select_primary_cohort(_dataset_bytes(rows))

    def test_committed_cohort_reproduces_from_official_dataset(self):
        dataset = (_REPO_ROOT / "data/lecturers/ictu_lecturers.json").read_bytes()
        committed = (_REPO_ROOT / "data/matching/evaluation/primary_cohort_source_ids.txt").read_bytes()
        assert tuple(committed.decode("utf-8").splitlines()) == ve.select_primary_cohort(dataset)


# ===========================================================================
# REVIEW MANIFEST / PACKAGE / DATASET / COHORT
# ===========================================================================


class TestManifestAndHashes:
    def test_valid_fixture_passes(self, fx):
        verified = ve.verify_offline_inputs(**fx.kwargs())
        assert len(verified.records) == 50

    def test_missing_field_rejected(self, fx):
        manifest = dict(fx.manifest)
        del manifest["publication_rule_set_id"]
        with pytest.raises(VerificationError):
            ve.parse_review_manifest(json.dumps(manifest).encode())

    @pytest.mark.parametrize(
        "field,value",
        [
            ("selected_lecturer_count", "50"),
            ("selected_lecturer_count", True),
            ("candidate_review_sha256", "abc"),
            ("schema_version", ""),
            ("source_id_file_sha256", 5),
        ],
    )
    def test_malformed_types_rejected(self, fx, field, value):
        with pytest.raises(VerificationError):
            ve.parse_review_manifest(fx.manifest_bytes(**{field: value}))

    def test_not_json_rejected(self):
        with pytest.raises(VerificationError):
            ve.parse_review_manifest(b"not json")

    def test_candidate_review_hash_mismatch(self, fx):
        with pytest.raises(VerificationError, match="candidate_review"):
            ve.verify_offline_inputs(**fx.kwargs(candidate_review_bytes=fx.candidate_review + b"x"))

    def test_blank_sheet_hash_mismatch(self, fx):
        with pytest.raises(VerificationError, match="reference_labeling_sheet"):
            ve.verify_offline_inputs(**fx.kwargs(labeling_sheet_bytes=fx.sheet + b"\n"))

    def test_dataset_sha_mismatch(self, fx):
        with pytest.raises(VerificationError, match="dataset"):
            ve.verify_offline_inputs(**fx.kwargs(dataset_bytes=fx.dataset + b" "))

    def test_source_id_sha_mismatch(self, fx):
        other = fx.cohort_bytes.replace(b"\n", b"\r\n")
        with pytest.raises(VerificationError, match="Source-id"):
            ve.verify_offline_inputs(**fx.kwargs(source_id_file_bytes=other, committed_cohort_bytes=other))

    def test_supplied_file_must_equal_committed_cohort(self, fx):
        with pytest.raises(VerificationError, match="committed"):
            ve.verify_offline_inputs(**fx.kwargs(committed_cohort_bytes=b"other\n"))

    def test_null_source_id_hash_rejected(self, fx):
        with pytest.raises(VerificationError):
            ve.verify_offline_inputs(**fx.kwargs(manifest_bytes=fx.manifest_bytes(source_id_file_sha256=None)))

    def test_selected_count_not_50_rejected(self, fx):
        with pytest.raises(VerificationError):
            ve.verify_offline_inputs(**fx.kwargs(manifest_bytes=fx.manifest_bytes(selected_lecturer_count=49)))

    def test_crlf_checkout_of_cohort_accepted_when_hashes_consistent(self, fx):
        crlf = fx.cohort_bytes.replace(b"\n", b"\r\n")
        manifest = dict(fx.manifest, source_id_file_sha256=hashlib.sha256(crlf).hexdigest())
        cohort = ve.verify_dataset_and_cohort(manifest, fx.dataset, crlf, crlf)
        assert cohort == fx.cohort

    def test_non_official_cohort_rejected_even_with_consistent_hashes(self, fx):
        bad = ve.render_cohort_file(tuple(sorted(r["source_id"] for r in fx.rows[:50])))
        if tuple(bad.decode().splitlines()) == fx.cohort:
            pytest.skip("synthetic coincidence")
        manifest = dict(fx.manifest, source_id_file_sha256=hashlib.sha256(bad).hexdigest())
        with pytest.raises(VerificationError, match="SHA256_SEED_RANK_V1"):
            ve.verify_dataset_and_cohort(manifest, fx.dataset, bad, bad)


# ===========================================================================
# RULE PROVENANCE
# ===========================================================================


class TestRuleProvenance:
    def test_all_six_match(self, fx):
        assert ve.verify_rule_provenance(fx.manifest) == ve.current_rule_provenance()

    @pytest.mark.parametrize(
        "field",
        [
            "candidate_rule_set_id",
            "candidate_rule_set_version",
            "publication_rule_set_id",
            "publication_rule_set_version",
            "generation_rule_set_id",
            "generation_rule_set_version",
        ],
    )
    def test_any_mismatch_fails(self, fx, field):
        with pytest.raises(VerificationError, match=field):
            ve.verify_rule_provenance({**fx.manifest, field: fx.manifest[field] + "-changed"})


# ===========================================================================
# FROZEN CODE BLOBS
# ===========================================================================


class TestFrozenCode:
    def test_anchors(self):
        assert dict(FROZEN_MATCHING_BLOBS) == {
            "backend/app/services/matching/candidate_generator.py": "2e98f87d9d2f6b2709c4fd0aa061c7da8046d556",
            "backend/app/services/matching/publication_evidence_enricher.py": "0c855f9834e271b765ceac57f6c7578ab89ab475",
            "backend/app/services/matching/candidate_types.py": "57f1a5a7e74fdcbe063fb111b19fd609ccab629a",
        }
        assert FROZEN_A2_SHA == "a1e761c21622280845fd9f4958493d4acfe86dde"

    def test_all_blobs_match(self):
        runner = _git_runner()
        provenance = ve.verify_frozen_code(_REPO_ROOT, runner=runner)
        assert [p["expected_frozen_blob_sha"] for p in provenance] == [p["current_blob_sha"] for p in provenance]
        assert any(c[:2] == ["git", "hash-object"] for c in runner.calls)
        assert any(c[:2] == ["git", "rev-parse"] and c[2].startswith(FROZEN_A2_SHA + ":") for c in runner.calls)

    @pytest.mark.parametrize("path", [p for p, _ in FROZEN_MATCHING_BLOBS])
    def test_changed_working_tree_file_fails(self, path):
        with pytest.raises(VerificationError, match="changed"):
            ve.verify_frozen_code(_REPO_ROOT, runner=_git_runner(current={path: "f" * 40}))

    def test_frozen_anchor_mismatch_fails(self):
        path = FROZEN_MATCHING_BLOBS[0][0]
        with pytest.raises(VerificationError):
            ve.verify_frozen_code(_REPO_ROOT, runner=_git_runner(frozen={path: "e" * 40}))

    def test_git_unavailable_fails_closed(self):
        with pytest.raises(VerificationError, match="unavailable"):
            ve.verify_frozen_code(_REPO_ROOT, runner=_git_runner(fail=True))

    def test_git_error_fails_closed(self):
        def run(cmd, **_k):
            return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="fatal")

        with pytest.raises(VerificationError):
            ve.verify_frozen_code(_REPO_ROOT, runner=run)

    def test_no_shell_true(self):
        tree = ast.parse(inspect.getsource(ve))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "shell":
                pytest.fail("shell= must not be used")


# ===========================================================================
# BLANK SHEET
# ===========================================================================


class TestBlankSheet:
    def test_valid(self, fx):
        assert len(ve.verify_blank_sheet(fx.sheet, fx.cohort)) == 50

    def test_wrong_schema(self, fx):
        rows = _sheet_rows(fx.sheet)
        cols = list(LABELING_SHEET_COLUMNS)
        cols[3], cols[4] = cols[4], cols[3]
        with pytest.raises(VerificationError, match="8-column"):
            ve.verify_blank_sheet(_write_sheet(rows, cols), fx.cohort)

    def test_not_50_rows(self, fx):
        with pytest.raises(VerificationError, match="50"):
            ve.verify_blank_sheet(_write_sheet(_sheet_rows(fx.sheet)[:49]), fx.cohort)

    def test_duplicate_source_id(self, fx):
        rows = _sheet_rows(fx.sheet)
        rows[1] = dict(rows[0])
        with pytest.raises(VerificationError, match="duplicate"):
            ve.verify_blank_sheet(_write_sheet(rows), fx.cohort)

    @pytest.mark.parametrize("column", ["decision", "expected_scopus_id", "confirmation_source", "confirmed_at", "notes"])
    def test_any_nonblank_label_rejected(self, fx, column):
        rows = _sheet_rows(fx.sheet)
        rows[7][column] = "x"
        with pytest.raises(VerificationError, match="edited"):
            ve.verify_blank_sheet(_write_sheet(rows), fx.cohort)


# ===========================================================================
# CONFIRMED IDENTITY IMMUTABILITY
# ===========================================================================


class TestConfirmedIdentity:
    def _check(self, fx, rows):
        index = ve.verify_blank_sheet(fx.sheet, fx.cohort)
        ve.verify_confirmed_identity(index, _write_sheet(rows).decode("utf-8"))

    def test_identical_and_reordered_pass(self, fx):
        rows = _fill(_sheet_rows(fx.sheet))
        self._check(fx, rows)
        self._check(fx, list(reversed(rows)))

    def test_whitespace_and_email_case_tolerated(self, fx):
        rows = _fill(_sheet_rows(fx.sheet))
        rows[0]["lecturer_source_id"] = "  " + rows[0]["lecturer_source_id"] + " "
        rows[1]["institutional_email"] = " " + rows[1]["institutional_email"].upper() + " "
        rows[2]["lecturer_full_name"] = " " + rows[2]["lecturer_full_name"] + "  "
        self._check(fx, rows)

    @pytest.mark.parametrize(
        "column,mutate",
        [
            ("lecturer_full_name", str.upper),
            ("lecturer_full_name", lambda v: v + " X"),
            ("institutional_email", lambda v: "other." + v),
            ("lecturer_source_id", lambda v: v + "x"),
        ],
    )
    def test_identity_changes_rejected(self, fx, column, mutate):
        rows = _fill(_sheet_rows(fx.sheet))
        rows[3][column] = mutate(rows[3][column])
        with pytest.raises(VerificationError):
            self._check(fx, rows)

    def test_added_removed_duplicate_rejected(self, fx):
        rows = _fill(_sheet_rows(fx.sheet))
        extra = dict(rows[0], lecturer_source_id="https://repo.example/new/")
        for bad in (rows + [extra], rows[:-1], rows[:-1] + [dict(rows[0])], rows[1:] + [extra]):
            with pytest.raises(VerificationError):
                self._check(fx, bad)


# ===========================================================================
# FULL COHORT LABEL COMPLETENESS
# ===========================================================================


class TestLabelCompleteness:
    def _run(self, fx, rows):
        return ve.verify_offline_inputs(**fx.kwargs(confirmed_bytes=_write_sheet(rows)))

    def test_all_50_valid_and_notes_optional(self, fx):
        rows = _fill(_sheet_rows(fx.sheet))
        assert all(r["notes"] == "" for r in rows[2:])
        assert len(self._run(fx, rows).records) == 50

    def test_excel_bom_accepted(self, fx):
        rows = _fill(_sheet_rows(fx.sheet))
        assert len(ve.verify_offline_inputs(**fx.kwargs(confirmed_bytes=b"\xef\xbb\xbf" + _write_sheet(rows))).records) == 50

    @pytest.mark.parametrize(
        "updates",
        [
            {"decision": ""},
            {"decision": "MATCH", "expected_scopus_id": ""},
            {"decision": "NO_MATCH", "expected_scopus_id": "123"},
            {"confirmation_source": ""},
            {"confirmed_at": ""},
            {"confirmed_at": "2026-10-08T09:00:00+07:00"},
        ],
    )
    def test_one_incomplete_row_fails_whole_run(self, fx, updates):
        rows = _fill(_sheet_rows(fx.sheet))
        rows[25].update(updates)
        with pytest.raises(VerificationError, match="incomplete or invalid"):
            self._run(fx, rows)

    def test_error_message_does_not_echo_reviewer_text(self, fx):
        rows = _fill(_sheet_rows(fx.sheet))
        rows[25]["decision"] = ""
        with pytest.raises(VerificationError) as exc_info:
            self._run(fx, rows)
        assert _SECRET_SOURCE not in str(exc_info.value) and _SECRET_NOTE not in str(exc_info.value)


# ===========================================================================
# SAFE RESULT
# ===========================================================================


def _a1_result(fx, verified):
    resolved = {
        r.decision.lecturer_source_id: a1._EvaluationLecturer(
            db_id=fx.canonical[r.decision.lecturer_source_id],
            source_id=r.decision.lecturer_source_id,
            full_name=r.decision.lecturer_full_name,
            email=r.decision.institutional_email,
        )
        for r in verified.records
    }
    first = verified.records[0].decision.lecturer_source_id
    pairs = {
        fx.canonical[first]: (
            a1._GeneratedPair(fx.canonical[first], "57000000001", ("RULE_EXACT_N0",), False),
            a1._GeneratedPair(fx.canonical[first], "57000000009", ("RULE_EXACT_N0",), False),
        )
    }
    return a1.evaluate_candidate_retrieval(verified.records, resolved, frozenset({"57000000001"}), pairs)


class TestSafeResult:
    def test_result_contract(self, fx):
        verified = ve.verify_offline_inputs(**fx.kwargs())
        evaluation = _a1_result(fx, verified)
        result = ve.build_result(verified, evaluation, _NOW)

        assert result["reference_confirmed_sha256"] == hashlib.sha256(fx.confirmed).hexdigest()
        assert result["review_manifest_sha256"] == hashlib.sha256(fx.manifest_bytes()).hexdigest()
        assert result["cohort_selection"] == {
            "algorithm": "SHA256_SEED_RANK_V1",
            "seed": "C3-A3-ICTU-PRIMARY-2026-V1",
            "requested_size": 50,
            "selected_count": 50,
        }
        assert result["rule_provenance"] == ve.current_rule_provenance()
        assert len(result["code_provenance"]) == 3
        assert all(p["expected_frozen_blob_sha"] == p["current_blob_sha"] for p in result["code_provenance"])
        assert (result["reference_row_count"], result["reference_match_count"], result["reference_no_match_count"]) == (50, 1, 49)
        assert result["metrics"]["true_positive_pairs"] == evaluation.metrics.true_positive_pairs == 1
        assert result["metrics"]["false_positive_pairs"] == 1
        assert result["metrics"]["candidate_pair_precision"] == evaluation.metrics.candidate_pair_precision
        assert len(result["cases"]) == 50
        assert result["cases"][0]["lecturer_source_id"] == evaluation.cases[0].lecturer_source_id

    def test_result_has_no_reviewer_text_uuids_or_db_info(self, fx):
        verified = ve.verify_offline_inputs(**fx.kwargs())
        text = json.dumps(ve.build_result(verified, _a1_result(fx, verified), _NOW))
        assert _SECRET_SOURCE not in text and _SECRET_NOTE not in text
        assert "confirmation_source" not in text and '"notes"' not in text
        for lecturer_uuid in fx.canonical.values():
            assert str(lecturer_uuid) not in text
        for word in ("postgres", "password", "db_host", "username", "database_url"):
            assert word not in text.lower()

    def test_no_ranking_fields(self, fx):
        verified = ve.verify_offline_inputs(**fx.kwargs())
        result = ve.build_result(verified, _a1_result(fx, verified), _NOW)
        keys = set(result) | set(result["metrics"]) | set(result["cases"][0])
        for word in ("rank", "score", "confidence", "probability", "threshold", "top_", "mrr", "ndcg"):
            assert not any(word in k for k in keys)


# ===========================================================================
# CLI / DB SAFETY
# ===========================================================================


class TestCli:
    _SECRETS = ("internal-db", "DO_NOT_LEAK", "secret_db")

    def _load(self):
        script = _REPO_ROOT / "backend/scripts/run_matching_quality_evaluation.py"
        spec = importlib.util.spec_from_file_location("run_matching_quality_evaluation_cli", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _setup(self, monkeypatch, fx, db_name="scopus_m12_test", environment="local"):
        from app.core.config import settings

        cli = self._load()
        td = Path(tempfile.mkdtemp())
        review = td / "review"
        review.mkdir()
        (review / "candidate_review.csv").write_bytes(fx.candidate_review)
        (review / "reference_labeling_sheet.csv").write_bytes(fx.sheet)
        (review / "review_manifest.json").write_bytes(fx.manifest_bytes())
        protected = td / "protected"
        protected.mkdir()
        (protected / "reference_confirmed.csv").write_bytes(fx.confirmed)
        cohort = td / "cohort.txt"
        cohort.write_bytes(fx.cohort_bytes)
        monkeypatch.setattr(cli, "COMMITTED_COHORT_PATH", cohort)
        monkeypatch.setattr(
            ve,
            "verify_frozen_code",
            lambda *_a, **_k: tuple(
                {"path": p, "expected_frozen_blob_sha": b, "current_blob_sha": b} for p, b in FROZEN_MATCHING_BLOBS
            ),
        )
        monkeypatch.setattr(settings, "environment", environment)
        monkeypatch.setattr(settings, "db_name", db_name)
        args = [
            "evaluate",
            "--review-dir", str(review),
            "--reference-confirmed", str(protected / "reference_confirmed.csv"),
            "--lecturer-dataset", str(fx.dataset_path),
            "--source-id-file", str(cohort),
            "--json-out", str(td / "out" / "evaluation_result.json"),
        ]
        return cli, args, td

    def _fake_db(self, monkeypatch, execute_error=None):
        import sqlalchemy
        import sqlalchemy.orm

        state = SimpleNamespace(created=False, disposed=False)

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

    def _sensitive(self):
        from sqlalchemy.exc import OperationalError

        return OperationalError("SELECT 1", {}, Exception("host=internal-db password=DO_NOT_LEAK database=secret_db"))

    def _patch_a1_db(self, monkeypatch, fx, error=None):
        def resolve(records, _session):
            if error is not None:
                raise error
            return (
                {
                    r.decision.lecturer_source_id: a1._EvaluationLecturer(
                        fx.canonical[r.decision.lecturer_source_id],
                        r.decision.lecturer_source_id,
                        r.decision.lecturer_full_name,
                        r.decision.institutional_email,
                    )
                    for r in records
                },
                [],
            )

        monkeypatch.setattr(a1, "resolve_lecturers_from_db", resolve)
        monkeypatch.setattr(a1, "load_scopus_corpus_ids", lambda _s: frozenset({"57000000001"}))
        monkeypatch.setattr(a1, "generate_pairs_from_current_production", lambda _r, _s: {})

    def _out(self, capsys) -> str:
        captured = capsys.readouterr()
        return captured.out + captured.err

    def test_prepare_cohort_writes_and_refuses_overwrite(self, fx, capsys):
        cli = self._load()
        out = Path(tempfile.mkdtemp()) / "cohort.txt"
        args = ["prepare-cohort", "--lecturer-dataset", str(fx.dataset_path), "--out", str(out)]
        assert cli.main(args) == 0
        assert out.read_bytes() == fx.cohort_bytes
        out.write_bytes(b"keep")
        assert cli.main(args) != 0 and out.read_bytes() == b"keep"
        assert cli.main(args + ["--overwrite"]) == 0 and out.read_bytes() == fx.cohort_bytes

    def test_prepare_cohort_does_not_touch_database(self):
        source = inspect.getsource(self._load()._prepare_cohort)
        assert "settings" not in source and "create_engine" not in source

    def test_prod_refused(self, monkeypatch, fx, capsys):
        cli, args, _ = self._setup(monkeypatch, fx, environment="prod")
        state = self._fake_db(monkeypatch)
        assert cli.main(args) != 0 and state.created is False

    @pytest.mark.parametrize("db_name", ["scopus_ictu_acceptance_v2", "scopus_other"])
    def test_unapproved_database_refused_without_disclosure(self, monkeypatch, fx, capsys, db_name):
        cli, args, td = self._setup(monkeypatch, fx, db_name=db_name)
        state = self._fake_db(monkeypatch)
        assert cli.main(args) != 0
        assert state.created is False
        out = self._out(capsys)
        assert "not the approved C3 runtime/test database" in out
        assert db_name not in out and "postgresql" not in out
        assert not (td / "out" / "evaluation_result.json").exists()

    def test_verification_runs_before_db(self, monkeypatch, fx, capsys):
        cli, args, td = self._setup(monkeypatch, fx)
        (td / "review" / "candidate_review.csv").write_bytes(fx.candidate_review + b"x")
        state = self._fake_db(monkeypatch)
        assert cli.main(args) != 0 and state.created is False

    def test_read_only_failure_fails_closed_and_redacted(self, monkeypatch, fx, capsys):
        cli, args, td = self._setup(monkeypatch, fx)
        state = self._fake_db(monkeypatch, execute_error=self._sensitive())
        assert cli.main(args) != 0
        assert state.disposed is True
        out = self._out(capsys)
        assert "read-only database transaction" in out
        assert not any(s in out for s in self._SECRETS)

    def test_sqlalchemy_error_redacted(self, monkeypatch, fx, capsys):
        cli, args, _ = self._setup(monkeypatch, fx)
        state = self._fake_db(monkeypatch)
        self._patch_a1_db(monkeypatch, fx, error=self._sensitive())
        assert cli.main(args) != 0
        assert state.disposed is True
        out = self._out(capsys)
        assert "Database evaluation failed safely." in out
        assert not any(s in out for s in self._SECRETS) and "OperationalError" not in out

    def test_success_writes_safe_result_and_never_writes_confirmed(self, monkeypatch, fx, capsys):
        cli, args, td = self._setup(monkeypatch, fx)
        state = self._fake_db(monkeypatch)
        self._patch_a1_db(monkeypatch, fx)
        confirmed = td / "protected" / "reference_confirmed.csv"
        before = confirmed.read_bytes()
        assert cli.main(args) == 0
        assert state.disposed is True
        assert confirmed.read_bytes() == before
        result_text = (td / "out" / "evaluation_result.json").read_text(encoding="utf-8")
        result = json.loads(result_text)
        assert result["reference_row_count"] == 50
        assert _SECRET_SOURCE not in result_text and _SECRET_NOTE not in result_text
        out = self._out(capsys)
        assert _SECRET_SOURCE not in out and "scopus_m12_test" not in out

    def test_cli_never_binds_database_exceptions(self):
        tree = ast.parse((_REPO_ROOT / "backend/scripts/run_matching_quality_evaluation.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                if ast.unparse(node.type) in {"Exception", "SQLAlchemyError"}:
                    assert node.name is None
