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
from app.services.matching import review_package as rp
from app.services.matching import verified_evaluation as ve
from app.services.matching.candidate_types import (
    CandidateEvidence,
    EnrichedLecturerScopusCandidate,
    PublicationEvidenceConflict,
)
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


def _synthetic_candidates(canonical, cohort) -> tuple:
    """Deterministic transient candidates for a few cohort lecturers."""

    def candidate(source_id, scopus_id, author_int):
        return EnrichedLecturerScopusCandidate(
            lecturer_id=canonical[source_id],
            scopus_author_id=uuid.UUID(int=author_int),
            scopus_id=scopus_id,
            preferred_name=f"Author {scopus_id}",
            evidence=(
                CandidateEvidence(
                    rule_id="RULE_EXACT_N0",
                    lecturer_source_value="Lecturer",
                    lecturer_comparison_value="lecturer",
                    scopus_surface_type="PREFERRED_NAME",
                    scopus_surface_value=f"Author {scopus_id}",
                    scopus_comparison_value="lecturer",
                ),
            ),
            publication_evidence=(),
        )

    return (
        candidate(cohort[0], "57000000001", 9001),
        candidate(cohort[1], "57000000002", 9002),
        candidate(cohort[1], "57000000003", 9003),
    )


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
        self.selected = selected
        self.canonical = {s: uuid.uuid4() for s in self.cohort}
        self.enriched = _synthetic_candidates(self.canonical, self.cohort)
        self.conflicts = (
            PublicationEvidenceConflict(
                known_publication_id=uuid.UUID(int=4242),
                lecturer_id=self.canonical[self.cohort[5]],
                lecturer_snapshot_id=uuid.UUID(int=4343),
                reason="TITLE_AMBIGUOUS",
                doi_publication_ids=(),
                title_publication_ids=(uuid.UUID(int=1), uuid.UUID(int=2)),
            ),
        )
        pkg = build_review_package(
            selected=selected,
            canonical_ids=self.canonical,
            enriched_candidates=self.enriched,
            conflicts=self.conflicts,
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
def fx(monkeypatch) -> _Fixture:
    fixture = _Fixture()
    # Synthetic datasets are not the frozen Phase-1 snapshot; register this one
    # explicitly so the other gates can be exercised in isolation.
    monkeypatch.setattr(
        ve,
        "PHASE1_ACCEPTED_DATASET_SHA256",
        (*ve.PHASE1_ACCEPTED_DATASET_SHA256, hashlib.sha256(fixture.dataset).hexdigest()),
    )
    return fixture


def _real_dataset_forms() -> tuple[bytes, bytes]:
    raw = (_REPO_ROOT / "data/lecturers/ictu_lecturers.json").read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    return lf, lf.replace(b"\n", b"\r\n")


def _real_cohort_bytes() -> bytes:
    return (_REPO_ROOT / "data/matching/evaluation/primary_cohort_source_ids.txt").read_bytes()


def _real_manifest(dataset_sha: str, cohort_bytes: bytes) -> dict:
    return {
        "official_lecturer_dataset_sha256": dataset_sha,
        "source_id_file_sha256": hashlib.sha256(cohort_bytes).hexdigest(),
        "selected_lecturer_count": 50,
    }


# ===========================================================================
# FROZEN PHASE-1 OFFICIAL DATASET
# ===========================================================================


class TestFrozenOfficialDataset:
    def test_accepted_hash_constants(self):
        assert ve.PHASE1_ACCEPTED_DATASET_SHA256 == (
            "9428e0a2b009ecff1043b4dc796ed69a0fc64054594b0fb40ffa27bbed4ec82e",
            "ac4ed2d3f3c5fc7e73912ac9386b5710f4e015bbd7028e5b48a656dae3d4c3d4",
        )

    def test_known_lf_snapshot_accepted(self):
        lf, _ = _real_dataset_forms()
        assert hashlib.sha256(lf).hexdigest() == ve.PHASE1_OFFICIAL_DATASET_SHA256_LF
        assert ve.verify_frozen_official_dataset(lf) == ve.PHASE1_OFFICIAL_DATASET_SHA256_LF

    def test_known_crlf_snapshot_accepted(self):
        _, crlf = _real_dataset_forms()
        assert hashlib.sha256(crlf).hexdigest() == ve.PHASE1_OFFICIAL_DATASET_SHA256_CRLF
        assert ve.verify_frozen_official_dataset(crlf) == ve.PHASE1_OFFICIAL_DATASET_SHA256_CRLF

    def test_third_hash_rejected_without_disclosing_it(self):
        lf, _ = _real_dataset_forms()
        changed = lf + b"\n"
        with pytest.raises(VerificationError) as exc_info:
            ve.verify_frozen_official_dataset(changed)
        assert "frozen C3-A3 Phase-1 snapshot" in str(exc_info.value)
        assert hashlib.sha256(changed).hexdigest() not in str(exc_info.value)

    @pytest.mark.parametrize("field", ["full_name", "institutional_email"])
    def test_same_cohort_ids_but_modified_identity_rejected(self, field):
        lf, _ = _real_dataset_forms()
        data = json.loads(lf.decode("utf-8"))
        cohort = ve.select_primary_cohort(lf)
        target = next(row for row in data["lecturers"] if row["source_id"].strip() == cohort[0])
        target[field] = (target.get(field) or "x") + " CHANGED"
        modified = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        assert ve.select_primary_cohort(modified) == cohort
        with pytest.raises(VerificationError, match="Phase-1 snapshot"):
            ve.verify_frozen_official_dataset(modified)
        cohort_bytes = _real_cohort_bytes()
        manifest = _real_manifest(hashlib.sha256(modified).hexdigest(), cohort_bytes)
        with pytest.raises(VerificationError, match="Phase-1 snapshot"):
            ve.verify_dataset_and_cohort(manifest, modified, cohort_bytes, cohort_bytes)

    @pytest.mark.parametrize("form", [0, 1])
    def test_frozen_form_with_matching_manifest_valid(self, form):
        dataset = _real_dataset_forms()[form]
        cohort_bytes = _real_cohort_bytes()
        manifest = _real_manifest(hashlib.sha256(dataset).hexdigest(), cohort_bytes)
        assert len(ve.verify_dataset_and_cohort(manifest, dataset, cohort_bytes, cohort_bytes)) == 50

    @pytest.mark.parametrize("dataset_form,manifest_form", [(0, 1), (1, 0)])
    def test_manifest_still_binds_exact_bytes(self, dataset_form, manifest_form):
        forms = _real_dataset_forms()
        cohort_bytes = _real_cohort_bytes()
        manifest = _real_manifest(hashlib.sha256(forms[manifest_form]).hexdigest(), cohort_bytes)
        with pytest.raises(VerificationError, match="review manifest"):
            ve.verify_dataset_and_cohort(manifest, forms[dataset_form], cohort_bytes, cohort_bytes)

    def test_committed_cohort_file_unchanged(self):
        content = _real_cohort_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(content).hexdigest() == (
            "e91babc67ade4413f0378c199a5821f10cba73da73dbbe22bdbec452fc357878"
        )


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


_PINNED_TEST_DIGEST = "a" * 64


def _patch_a2_db_reads(monkeypatch, fx, log, enriched=None, conflicts=None, canonical=None):
    """Simulate the frozen A2 DB reads; the 'database state' is passed explicitly."""
    state_canonical = dict(fx.canonical if canonical is None else canonical)
    state_enriched = fx.enriched if enriched is None else enriched
    state_conflicts = fx.conflicts if conflicts is None else conflicts

    def resolve(selected, session):
        log.append(("a2_resolve", id(session)))
        return {lecturer.source_id: state_canonical[lecturer.source_id] for lecturer in selected}

    def generate(canonical_ids, session):
        log.append(("a2_generate", id(session)))
        return tuple(state_enriched), tuple(state_conflicts)

    monkeypatch.setattr(rp, "resolve_canonical_lecturers_from_db", resolve)
    monkeypatch.setattr(rp, "generate_review_inputs", generate)


def _fake_fingerprint(digest: str) -> "ve.InputFingerprint":
    return ve.InputFingerprint(schema_version=ve.FINGERPRINT_SCHEMA_VERSION, sha256=digest, tables=())


def _install_fake_db(monkeypatch, execute_error=None, connected_db="scopus_c3_eval_v1"):
    import sqlalchemy
    import sqlalchemy.orm

    state = SimpleNamespace(created=False, disposed=False, statements=[])

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

        def execute(self, statement, *_a, **_k):
            state.statements.append(str(statement))
            if execute_error is not None:
                raise execute_error
            return SimpleNamespace(scalar_one=lambda: connected_db)

        def commit(self):
            raise AssertionError("commit must never be called")

    def _create(*_a, **_k):
        state.created = True
        return _Engine()

    monkeypatch.setattr(sqlalchemy, "create_engine", _create)
    monkeypatch.setattr(sqlalchemy.orm, "Session", _Session)
    return state


class TestCli:
    _SECRETS = ("internal-db", "DO_NOT_LEAK", "secret_db")

    def _load(self):
        script = _REPO_ROOT / "backend/scripts/run_matching_quality_evaluation.py"
        spec = importlib.util.spec_from_file_location("run_matching_quality_evaluation_cli", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _setup(
        self,
        monkeypatch,
        fx,
        db_name="scopus_c3_eval_v1",
        environment="local",
        pinned=_PINNED_TEST_DIGEST,
        actual=_PINNED_TEST_DIGEST,
    ):
        from app.core.config import settings

        cli = self._load()
        monkeypatch.setattr(ve, "EXPECTED_INPUT_FINGERPRINT_SHA256", pinned)
        self.sessions_used = []

        def _fingerprint(session):
            self.sessions_used.append(("fingerprint", id(session)))
            return _fake_fingerprint(actual)

        monkeypatch.setattr(ve, "compute_input_fingerprint", _fingerprint)
        _patch_a2_db_reads(monkeypatch, fx, self.sessions_used)
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

    def _fake_db(self, monkeypatch, execute_error=None, connected_db="scopus_c3_eval_v1"):
        return _install_fake_db(monkeypatch, execute_error=execute_error, connected_db=connected_db)

    def _sensitive(self):
        from sqlalchemy.exc import OperationalError

        return OperationalError("SELECT 1", {}, Exception("host=internal-db password=DO_NOT_LEAK database=secret_db"))

    def _patch_a1_db(self, monkeypatch, fx, error=None):
        def resolve(records, _session):
            getattr(self, "sessions_used", []).append(("a1_resolve", id(_session)))
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

    def test_prepare_cohort_refuses_unapproved_snapshot_before_writing(self, capsys):
        cli = self._load()
        lf, _ = _real_dataset_forms()
        data = json.loads(lf.decode("utf-8"))
        data["lecturers"][0]["full_name"] += " CHANGED"
        td = Path(tempfile.mkdtemp())
        dataset = td / "lecturers.json"
        dataset.write_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        out = td / "cohort.txt"
        assert cli.main(["prepare-cohort", "--lecturer-dataset", str(dataset), "--out", str(out)]) != 0
        assert not out.exists()
        assert "Phase-1 snapshot" in self._out(capsys)

    def test_prepare_cohort_accepts_frozen_snapshot(self, capsys):
        cli = self._load()
        td = Path(tempfile.mkdtemp())
        for form in _real_dataset_forms():
            dataset = td / "lecturers.json"
            dataset.write_bytes(form)
            out = td / "cohort.txt"
            assert cli.main(["prepare-cohort", "--lecturer-dataset", str(dataset), "--out", str(out), "--overwrite"]) == 0
            assert out.read_bytes() == _real_cohort_bytes().replace(b"\r\n", b"\n")

    def test_prepare_cohort_does_not_touch_database(self):
        source = inspect.getsource(self._load()._prepare_cohort)
        assert "settings" not in source and "create_engine" not in source

    def test_prod_refused(self, monkeypatch, fx, capsys):
        cli, args, _ = self._setup(monkeypatch, fx, environment="prod")
        state = self._fake_db(monkeypatch)
        assert cli.main(args) != 0 and state.created is False

    @pytest.mark.parametrize("db_name", ["scopus_ictu_acceptance_v2", "scopus_m12_test", "scopus_other"])
    def test_unapproved_database_refused_without_disclosure(self, monkeypatch, fx, capsys, db_name):
        cli, args, td = self._setup(monkeypatch, fx, db_name=db_name)
        state = self._fake_db(monkeypatch)
        assert cli.main(args) != 0
        assert state.created is False
        out = self._out(capsys)
        assert "not the approved C3 evaluation database" in out
        assert db_name not in out and "postgresql" not in out
        assert not (td / "out" / "evaluation_result.json").exists()

    @pytest.mark.parametrize("connected", ["scopus_m12_test", "scopus_ictu_acceptance_v2", "postgres"])
    def test_valid_config_but_wrong_connected_database_refused(self, monkeypatch, fx, capsys, connected):
        cli, args, td = self._setup(monkeypatch, fx)
        state = self._fake_db(monkeypatch, connected_db=connected)
        self._patch_a1_db(monkeypatch, fx)
        assert cli.main(args) != 0
        assert state.disposed is True
        out = self._out(capsys)
        assert "Connected database is not the approved C3 evaluation database." in out
        assert connected not in out
        assert not (td / "out" / "evaluation_result.json").exists()

    def test_unpinned_fingerprint_refuses_before_database(self, monkeypatch, fx, capsys):
        cli, args, td = self._setup(monkeypatch, fx, pinned=None)
        state = self._fake_db(monkeypatch)
        assert cli.main(args) != 0
        assert state.created is False
        assert "UNPINNED" in self._out(capsys)
        assert not (td / "out" / "evaluation_result.json").exists()

    def test_fingerprint_mismatch_refused(self, monkeypatch, fx, capsys):
        cli, args, td = self._setup(monkeypatch, fx, actual="b" * 64)
        state = self._fake_db(monkeypatch)
        self._patch_a1_db(monkeypatch, fx)
        assert cli.main(args) != 0
        assert state.disposed is True
        assert "does not match the pinned fingerprint" in self._out(capsys)
        assert not (td / "out" / "evaluation_result.json").exists()

    def test_snapshot_transaction_is_first_statement_and_shared(self, monkeypatch, fx, capsys):
        cli, args, _ = self._setup(monkeypatch, fx)
        state = self._fake_db(monkeypatch)
        self._patch_a1_db(monkeypatch, fx)
        assert cli.main(args) == 0
        assert state.statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        assert state.statements[1] == "SELECT current_database()"
        steps = [step for step, _ in self.sessions_used]
        assert steps == ["fingerprint", "a2_resolve", "a2_generate", "a1_resolve"]
        assert len({session_id for _, session_id in self.sessions_used}) == 1

    def test_rerender_mismatch_fails_closed_without_result(self, monkeypatch, fx, capsys):
        cli, args, td = self._setup(monkeypatch, fx)
        state = self._fake_db(monkeypatch)
        self._patch_a1_db(monkeypatch, fx)
        _patch_a2_db_reads(monkeypatch, fx, [], enriched=fx.enriched[:-1])
        assert cli.main(args) != 0
        assert state.disposed is True
        assert "not byte-equal to the re-render" in self._out(capsys)
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
        assert "read-only snapshot transaction" in out
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
        assert result["input_fingerprint"]["sha256"] == _PINNED_TEST_DIGEST
        assert result["input_fingerprint"]["schema_version"] == 1
        assert result["review_package_rerender"]["verified"] is True
        assert result["review_package_rerender"]["candidate_review_sha256"] == hashlib.sha256(fx.candidate_review).hexdigest()
        assert _SECRET_SOURCE not in result_text and _SECRET_NOTE not in result_text
        out = self._out(capsys)
        assert _SECRET_SOURCE not in out and "scopus_c3_eval_v1" not in out

    def test_cli_never_binds_database_exceptions(self):
        tree = ast.parse((_REPO_ROOT / "backend/scripts/run_matching_quality_evaluation.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                if ast.unparse(node.type) in {"Exception", "SQLAlchemyError"}:
                    assert node.name is None


# ===========================================================================
# DATABASE IDENTITY GUARD
# ===========================================================================


class TestDatabaseGuard:
    def _url(self, name: str) -> str:
        return f"postgresql+psycopg2://u:p@localhost:5432/{name}"

    def test_approved_name_exact(self):
        assert ve.APPROVED_DATABASE_NAME == "scopus_c3_eval_v1"
        assert ve.is_approved_database(self._url("scopus_c3_eval_v1")) is True

    @pytest.mark.parametrize(
        "name",
        [
            "scopus_m12_test",
            "scopus_ictu_acceptance_v2",
            "scopus_c3_eval_v2",
            "SCOPUS_C3_EVAL_V1",
            "scopus_c3_eval_v1_copy",
            "",
        ],
    )
    def test_other_names_rejected(self, name):
        assert ve.is_approved_database(self._url(name)) is False

    def test_malformed_url_rejected(self):
        assert ve.is_approved_database("not a url") is False

    def test_connected_database_must_match(self):
        ok = SimpleNamespace(execute=lambda _s: SimpleNamespace(scalar_one=lambda: "scopus_c3_eval_v1"))
        ve.verify_connected_database(ok)
        for actual in ("scopus_m12_test", "scopus_ictu_acceptance_v2", "postgres"):
            bad = SimpleNamespace(execute=lambda _s, a=actual: SimpleNamespace(scalar_one=lambda: a))
            with pytest.raises(VerificationError) as exc_info:
                ve.verify_connected_database(bad)
            assert actual not in str(exc_info.value)

    def test_settings_have_no_raw_url_override_path(self):
        from app.core.config import Settings

        fields = set(Settings.model_fields)
        assert "database_url" not in fields  # computed from DB_* only
        assert "db_name" in fields


# ===========================================================================
# INPUT FINGERPRINT (schema_version 1)
# ===========================================================================


def _uuid(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


def _fp_rows():
    lec, snap, kp, pub, auth, var, pa = (_uuid(i) for i in range(1, 8))
    imp, raw = _uuid(100), _uuid(101)
    content = {
        "lecturers": [{"id": lec, "full_name": "TS. Nguyễn Văn A", "repository_profile_url": "https://r/a/"}],
        "lecturer_source_snapshots": [{"id": snap, "lecturer_id": lec}],
        "lecturer_known_publications": [
            {"id": kp, "lecturer_id": lec, "snapshot_id": snap, "doi_normalized": None, "title_normalized": "t"}
        ],
        "publications": [{"id": pub, "eid": "2-s2.0-1", "doi": None, "title": "T", "title_normalized": "t"}],
        "scopus_authors": [{"id": auth, "scopus_id": "57000000001", "preferred_name": "Nguyen, A."}],
        "scopus_author_name_variants": [
            {"id": var, "scopus_author_id": auth, "variant_type": "AUTHOR_FULL_NAME", "variant_name": "Nguyen Van A"}
        ],
        "publication_authors": [{"id": pa, "publication_id": pub, "scopus_author_id": auth}],
    }
    keys = {"scopus_imports": [imp], "raw_scopus_records": [raw]}
    return content, keys


def _with_extra_rows(content, keys):
    content = {t: list(r) for t, r in content.items()}
    keys = {t: list(k) for t, k in keys.items()}
    content["lecturers"].append({"id": _uuid(50), "full_name": "B", "repository_profile_url": None})
    content["publications"].append(
        {"id": _uuid(51), "eid": "2-s2.0-2", "doi": "10.1/x", "title": "U", "title_normalized": "u"}
    )
    keys["raw_scopus_records"].append(_uuid(52))
    return content, keys


def _copy_content(content):
    return {t: [dict(r) for r in rows] for t, rows in content.items()}


def _cj(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class TestInputFingerprint:
    def test_contract_columns_and_tables(self):
        assert ve.FINGERPRINT_SCHEMA_VERSION == 1
        assert set(ve.FINGERPRINT_CONTENT_COLUMNS) | set(ve.FINGERPRINT_KEY_TABLES) == {
            "scopus_imports",
            "raw_scopus_records",
            "scopus_authors",
            "scopus_author_name_variants",
            "publications",
            "publication_authors",
            "lecturers",
            "lecturer_source_snapshots",
            "lecturer_known_publications",
        }
        for columns in ve.FINGERPRINT_CONTENT_COLUMNS.values():
            assert list(columns) == sorted(columns) and "id" in columns
            assert "raw_payload" not in columns
        assert ve.FINGERPRINT_CONTENT_COLUMNS["scopus_author_name_variants"] == (
            "id",
            "scopus_author_id",
            "variant_name",
            "variant_type",
        )

    def test_matches_independent_reference_computation(self):
        content, keys = _fp_rows()
        fp = ve.fingerprint_from_rows(content, keys)
        tables = []
        for table in sorted([*ve.FINGERPRINT_CONTENT_COLUMNS, *ve.FINGERPRINT_KEY_TABLES]):
            if table in ve.FINGERPRINT_CONTENT_COLUMNS:
                cols = ve.FINGERPRINT_CONTENT_COLUMNS[table]
                rows = sorted(
                    (
                        {c: (str(v) if isinstance(v, uuid.UUID) else v) for c, v in r.items() if c in cols}
                        for r in content[table]
                    ),
                    key=lambda r: r["id"],
                )
                tables.append(
                    {
                        "table": table,
                        "hash_kind": "content",
                        "columns": list(cols),
                        "row_count": len(rows),
                        "sha256": hashlib.sha256(_cj(rows)).hexdigest(),
                    }
                )
            else:
                ks = sorted(str(k) for k in keys[table])
                tables.append(
                    {
                        "table": table,
                        "hash_kind": "primary_key",
                        "columns": ["id"],
                        "row_count": len(ks),
                        "sha256": hashlib.sha256(_cj(ks)).hexdigest(),
                    }
                )
        expected = hashlib.sha256(_cj({"schema_version": 1, "tables": tables})).hexdigest()
        assert fp.sha256 == expected
        assert fp.as_dict()["tables"] == tables

    def test_order_independent(self):
        content, keys = _with_extra_rows(*_fp_rows())
        a = ve.fingerprint_from_rows(content, keys)
        rev_content = {t: list(reversed(r)) for t, r in content.items()}
        rev_keys = {t: list(reversed(k)) for t, k in keys.items()}
        assert ve.fingerprint_from_rows(rev_content, rev_keys).sha256 == a.sha256

    @pytest.mark.parametrize(
        "table,column,value",
        [
            ("lecturers", "full_name", "TS. Nguyễn Văn B"),
            ("lecturers", "repository_profile_url", "https://r/b/"),
            ("scopus_authors", "preferred_name", "Nguyen, B."),
            ("scopus_authors", "scopus_id", "57000000002"),
            ("scopus_author_name_variants", "variant_name", "Nguyen Van B"),
            ("scopus_author_name_variants", "variant_type", "AUTHOR_DISPLAY"),
            ("lecturer_known_publications", "title_normalized", "t2"),
            ("lecturer_known_publications", "snapshot_id", uuid.UUID(int=996)),
            ("publications", "eid", "2-s2.0-9"),
            ("publication_authors", "scopus_author_id", uuid.UUID(int=999)),
            ("lecturer_source_snapshots", "lecturer_id", uuid.UUID(int=998)),
            ("lecturers", "id", uuid.UUID(int=997)),
        ],
    )
    def test_business_column_or_uuid_change_changes_digest(self, table, column, value):
        content, keys = _fp_rows()
        base = ve.fingerprint_from_rows(content, keys).sha256
        changed = _copy_content(content)
        changed[table][0][column] = value
        assert ve.fingerprint_from_rows(changed, keys).sha256 != base

    def test_null_distinct_from_empty_string(self):
        content, keys = _fp_rows()
        base = ve.fingerprint_from_rows(content, keys).sha256
        changed = _copy_content(content)
        changed["publications"][0]["doi"] = ""
        assert ve.fingerprint_from_rows(changed, keys).sha256 != base

    def test_strings_not_normalized(self):
        content, keys = _fp_rows()
        base = ve.fingerprint_from_rows(content, keys).sha256
        for variant in ("TS. Nguyễn Văn A ", "ts. nguyễn văn a"):
            changed = _copy_content(content)
            changed["lecturers"][0]["full_name"] = variant
            assert ve.fingerprint_from_rows(changed, keys).sha256 != base

    @pytest.mark.parametrize(
        "table",
        [
            "lecturers",
            "lecturer_source_snapshots",
            "lecturer_known_publications",
            "publications",
            "scopus_authors",
            "scopus_author_name_variants",
            "publication_authors",
        ],
    )
    def test_row_count_change_changes_digest(self, table):
        content, keys = _fp_rows()
        base = ve.fingerprint_from_rows(content, keys).sha256
        changed = _copy_content(content)
        changed[table].append(dict(changed[table][0], id=uuid.UUID(int=12345)))
        assert ve.fingerprint_from_rows(changed, keys).sha256 != base

    @pytest.mark.parametrize("table", ["scopus_imports", "raw_scopus_records"])
    def test_raw_key_set_change_changes_digest(self, table):
        content, keys = _fp_rows()
        base = ve.fingerprint_from_rows(content, keys).sha256
        added = {t: list(k) for t, k in keys.items()}
        added[table].append(uuid.UUID(int=777))
        replaced = {t: list(k) for t, k in keys.items()}
        replaced[table] = [uuid.UUID(int=778)]
        assert ve.fingerprint_from_rows(content, added).sha256 != base
        assert ve.fingerprint_from_rows(content, replaced).sha256 != base

    def test_raw_payload_change_with_same_keys_does_not_change_digest(self):
        content, keys = _fp_rows()
        base = ve.fingerprint_from_rows(content, keys).sha256
        with_payload_a = {t: [dict(r, raw_payload={"x": 1}) for r in rows] for t, rows in content.items()}
        with_payload_b = {t: [dict(r, raw_payload={"x": 2}) for r in rows] for t, rows in content.items()}
        assert ve.fingerprint_from_rows(with_payload_a, keys).sha256 == base
        assert ve.fingerprint_from_rows(with_payload_b, keys).sha256 == base

    def test_schema_version_changes_digest(self):
        content, keys = _fp_rows()
        v1 = ve.fingerprint_from_rows(content, keys).sha256
        assert v1 != ve.fingerprint_from_rows(content, keys, schema_version=2).sha256

    def test_duplicate_primary_key_rejected(self):
        content, keys = _fp_rows()
        content["lecturers"].append(dict(content["lecturers"][0]))
        with pytest.raises(VerificationError):
            ve.fingerprint_from_rows(content, keys)

    def test_missing_table_or_column_rejected(self):
        content, keys = _fp_rows()
        partial = dict(content)
        del partial["publications"]
        with pytest.raises(VerificationError):
            ve.fingerprint_from_rows(partial, keys)
        content["publications"][0].pop("doi")
        with pytest.raises(VerificationError):
            ve.fingerprint_from_rows(content, keys)

    def test_unsupported_value_type_rejected(self):
        content, keys = _fp_rows()
        content["publications"][0]["doi"] = 1.5
        with pytest.raises(VerificationError):
            ve.fingerprint_from_rows(content, keys)


class _FingerprintSession:
    """Fake session serving SELECTs from in-memory rows; refuses anything else."""

    def __init__(self, content, keys, reverse=False):
        self.content = content
        self.keys = keys
        self.reverse = reverse
        self.statements: list[str] = []

    def execute(self, statement, *_a, **_k):
        sql = str(statement)
        self.statements.append(sql)
        assert sql.lstrip().upper().startswith("SELECT"), sql
        assert "raw_payload" not in sql
        table = statement.get_final_froms()[0].name
        names = [c.name for c in statement.selected_columns]
        if table in self.content:
            rows = [{n: r[n] for n in names} for r in self.content[table]]
        else:
            rows = [{"id": k} for k in self.keys[table]]
        if self.reverse:
            rows = list(reversed(rows))
        return SimpleNamespace(
            mappings=lambda: SimpleNamespace(all=lambda: rows),
            scalars=lambda: SimpleNamespace(all=lambda: [r["id"] for r in rows]),
        )


class TestFingerprintLoader:
    def test_loader_is_select_only_and_order_independent(self):
        content, keys = _with_extra_rows(*_fp_rows())
        expected = ve.fingerprint_from_rows(content, keys).sha256
        forward = _FingerprintSession(content, keys)
        backward = _FingerprintSession(content, keys, reverse=True)
        assert ve.compute_input_fingerprint(forward).sha256 == expected
        assert ve.compute_input_fingerprint(backward).sha256 == expected
        assert len(forward.statements) == 9

    def test_no_write_apis_in_fingerprint_code(self):
        functions = [ve.compute_input_fingerprint, ve.fingerprint_from_rows, ve.verify_connected_database]
        for fn in functions:
            tree = ast.parse(inspect.getsource(fn).lstrip())
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    assert node.attr not in {"commit", "add", "add_all", "flush", "delete", "merge", "insert", "update"}
        assert ve.READ_ONLY_SNAPSHOT_SQL == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"


class TestPinnedFingerprint:
    def test_expected_fingerprint_is_unpinned_in_this_commit(self):
        assert ve.EXPECTED_INPUT_FINGERPRINT_SHA256 is None

    def test_unpinned_refused(self):
        with pytest.raises(VerificationError, match="UNPINNED"):
            ve.require_pinned_fingerprint()
        with pytest.raises(VerificationError, match="UNPINNED"):
            ve.verify_input_fingerprint(_fake_fingerprint("c" * 64))

    @pytest.mark.parametrize("bad", ["", "abc", "Z" * 64, "A" * 64])
    def test_malformed_pin_refused(self, bad):
        with pytest.raises(VerificationError, match="malformed"):
            ve.require_pinned_fingerprint(bad)

    def test_match_and_mismatch(self):
        ve.verify_input_fingerprint(_fake_fingerprint("c" * 64), expected="c" * 64)
        with pytest.raises(VerificationError, match="does not match"):
            ve.verify_input_fingerprint(_fake_fingerprint("d" * 64), expected="c" * 64)
        wrong_version = ve.InputFingerprint(schema_version=2, sha256="c" * 64, tables=())
        with pytest.raises(VerificationError):
            ve.verify_input_fingerprint(wrong_version, expected="c" * 64)


class TestComputeFingerprintCli:
    def _load(self):
        script = _REPO_ROOT / "backend/scripts/run_matching_quality_evaluation.py"
        spec = importlib.util.spec_from_file_location("run_matching_quality_evaluation_cli_fp", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _env(self, monkeypatch, db_name="scopus_c3_eval_v1", environment="local"):
        from app.core.config import settings

        monkeypatch.setattr(settings, "environment", environment)
        monkeypatch.setattr(settings, "db_name", db_name)

    def test_compute_works_while_unpinned(self, monkeypatch, capsys):
        assert ve.EXPECTED_INPUT_FINGERPRINT_SHA256 is None
        cli = self._load()
        self._env(monkeypatch)
        state = _install_fake_db(monkeypatch)
        content, keys = _fp_rows()
        expected = ve.fingerprint_from_rows(content, keys)
        monkeypatch.setattr(ve, "compute_input_fingerprint", lambda _s: expected)
        out_file = Path(tempfile.mkdtemp()) / "fingerprint.json"
        assert cli.main(["compute-fingerprint", "--json-out", str(out_file)]) == 0
        payload = json.loads(out_file.read_text(encoding="utf-8"))
        assert payload["sha256"] == expected.sha256 and payload["schema_version"] == 1
        assert payload["database_identity_verified"] is True
        assert state.statements[:2] == [
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
            "SELECT current_database()",
        ]
        assert state.disposed is True
        out = capsys.readouterr()
        assert "scopus_c3_eval_v1" not in out.out + out.err

    @pytest.mark.parametrize("db_name", ["scopus_m12_test", "scopus_ictu_acceptance_v2"])
    def test_compute_refuses_wrong_configured_database(self, monkeypatch, capsys, db_name):
        cli = self._load()
        self._env(monkeypatch, db_name=db_name)
        state = _install_fake_db(monkeypatch)
        assert cli.main(["compute-fingerprint"]) != 0
        assert state.created is False

    def test_compute_refuses_wrong_connected_database(self, monkeypatch, capsys):
        cli = self._load()
        self._env(monkeypatch)
        state = _install_fake_db(monkeypatch, connected_db="scopus_ictu_acceptance_v2")
        monkeypatch.setattr(ve, "compute_input_fingerprint", lambda _s: pytest.fail("must not fingerprint"))
        assert cli.main(["compute-fingerprint"]) != 0
        assert state.disposed is True
        out = capsys.readouterr()
        assert "scopus_ictu_acceptance_v2" not in out.out + out.err

    def test_compute_refuses_prod(self, monkeypatch, capsys):
        cli = self._load()
        self._env(monkeypatch, environment="prod")
        state = _install_fake_db(monkeypatch)
        assert cli.main(["compute-fingerprint"]) != 0
        assert state.created is False

    def test_compute_redacts_database_errors(self, monkeypatch, capsys):
        from sqlalchemy.exc import OperationalError

        cli = self._load()
        self._env(monkeypatch)
        state = _install_fake_db(
            monkeypatch,
            execute_error=OperationalError("SELECT 1", {}, Exception("host=internal-db password=DO_NOT_LEAK")),
        )
        assert cli.main(["compute-fingerprint"]) != 0
        assert state.disposed is True
        out = capsys.readouterr()
        assert "DO_NOT_LEAK" not in out.out + out.err and "internal-db" not in out.out + out.err


# ===========================================================================
# REVIEW PACKAGE RE-RENDER (byte-equal provenance)
# ===========================================================================


def _with_sha(manifest: dict, **files: bytes) -> dict:
    """An attacker-consistent manifest: hashes recomputed for tampered files."""
    out = dict(manifest)
    if "candidate_review" in files:
        out["candidate_review_sha256"] = hashlib.sha256(files["candidate_review"]).hexdigest()
    if "sheet" in files:
        out["reference_labeling_sheet_sha256"] = hashlib.sha256(files["sheet"]).hexdigest()
    return out


def _flip_one_byte(data: bytes, needle: bytes) -> bytes:
    index = data.index(needle)
    return data[:index] + bytes([data[index] ^ 0x01]) + data[index + 1 :]


class TestPackageRerender:
    SESSION = object()

    def _run(self, fx, *, manifest=None, candidate_review=None, sheet=None):
        return ve.verify_package_rerender(
            self.SESSION,
            manifest=fx.manifest if manifest is None else manifest,
            candidate_review_bytes=fx.candidate_review if candidate_review is None else candidate_review,
            labeling_sheet_bytes=fx.sheet if sheet is None else sheet,
            dataset_bytes=fx.dataset,
            source_id_file_bytes=fx.cohort_bytes,
        )

    def test_matching_rerender_passes(self, monkeypatch, fx):
        log: list = []
        _patch_a2_db_reads(monkeypatch, fx, log)
        result = self._run(fx)
        assert result["verified"] is True
        assert result["candidate_review_sha256"] == hashlib.sha256(fx.candidate_review).hexdigest()
        assert "generated_at" not in result["compared_manifest_fields"]
        assert [step for step, _ in log] == ["a2_resolve", "a2_generate"]
        assert {sid for _, sid in log} == {id(self.SESSION)}

    def test_fixture_package_is_non_trivial(self, fx):
        rows = list(csv.DictReader(io.StringIO(fx.candidate_review.decode("utf-8"))))
        assert sum(1 for r in rows if r["suggestion_status"] == "CANDIDATE") == 3
        assert any(r["lecturer_publication_conflict_count"] == "1" for r in rows)

    def test_one_byte_change_in_candidate_csv_rejected_even_with_consistent_manifest(self, monkeypatch, fx):
        _patch_a2_db_reads(monkeypatch, fx, [])
        tampered = _flip_one_byte(fx.candidate_review, b"57000000002")
        with pytest.raises(VerificationError, match="candidate_review.csv is not byte-equal"):
            self._run(fx, manifest=_with_sha(fx.manifest, candidate_review=tampered), candidate_review=tampered)

    def test_one_byte_change_in_blank_sheet_rejected_even_with_consistent_manifest(self, monkeypatch, fx):
        _patch_a2_db_reads(monkeypatch, fx, [])
        tampered = _flip_one_byte(fx.sheet, b"Lecturer 0")
        with pytest.raises(VerificationError, match="reference_labeling_sheet.csv is not byte-equal"):
            self._run(fx, manifest=_with_sha(fx.manifest, sheet=tampered), sheet=tampered)

    def test_manifest_hash_not_matching_actual_file_rejected(self, monkeypatch, fx):
        _patch_a2_db_reads(monkeypatch, fx, [])
        with pytest.raises(VerificationError, match="does not match the review manifest hash"):
            self._run(fx, candidate_review=fx.candidate_review + b"\n")

    @pytest.mark.parametrize(
        "field,value",
        [
            ("candidate_pair_count", 99),
            ("ambiguous_lecturer_count", 0),
            ("publication_conflict_count", 0),
            ("publication_rule_set_version", "tampered"),
        ],
    )
    def test_self_declared_manifest_fields_not_trusted(self, monkeypatch, fx, field, value):
        _patch_a2_db_reads(monkeypatch, fx, [])
        with pytest.raises(VerificationError, match=field):
            self._run(fx, manifest={**fx.manifest, field: value})

    def test_generated_at_is_the_only_free_field(self, monkeypatch, fx):
        _patch_a2_db_reads(monkeypatch, fx, [])
        assert self._run(fx, manifest={**fx.manifest, "generated_at": "2030-01-01T00:00:00+00:00"})["verified"]

    @pytest.mark.parametrize(
        "change",
        ["drop_candidate", "extra_conflict", "different_lecturer_uuid_map"],
    )
    def test_different_database_state_rejected(self, monkeypatch, fx, change):
        kwargs = {}
        if change == "drop_candidate":
            kwargs["enriched"] = fx.enriched[:-1]
        elif change == "extra_conflict":
            kwargs["conflicts"] = fx.conflicts + (
                PublicationEvidenceConflict(
                    known_publication_id=uuid.UUID(int=5151),
                    lecturer_id=fx.canonical[fx.cohort[7]],
                    lecturer_snapshot_id=uuid.UUID(int=5252),
                    reason="DOI_AMBIGUOUS",
                    doi_publication_ids=(),
                    title_publication_ids=(),
                ),
            )
        else:
            kwargs["canonical"] = {s: uuid.uuid4() for s in fx.cohort}
        _patch_a2_db_reads(monkeypatch, fx, [], **kwargs)
        with pytest.raises(VerificationError):
            self._run(fx)

    def test_expected_bytes_come_from_database_inputs_not_package(self, monkeypatch, fx):
        captured = {}
        real_build = rp.build_review_package

        def spy(**kwargs):
            captured.update(kwargs)
            return real_build(**kwargs)

        _patch_a2_db_reads(monkeypatch, fx, [])
        monkeypatch.setattr(rp, "build_review_package", spy)
        self._run(fx)
        assert tuple(captured["enriched_candidates"]) == fx.enriched
        assert tuple(captured["conflicts"]) == fx.conflicts
        assert captured["official_dataset_bytes"] == fx.dataset
        assert captured["source_id_file_bytes"] == fx.cohort_bytes
        assert captured["rule_set_id"] == CANDIDATE_RULE_SET_ID
        for value in captured.values():
            assert value is not fx.candidate_review and value is not fx.sheet

    def test_rerender_source_never_reads_package_csv_for_inputs(self):
        source = inspect.getsource(ve.verify_package_rerender)
        tree = ast.parse(source)
        call_names = {
            getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert {"resolve_canonical_lecturers_from_db", "generate_review_inputs", "build_review_package"} <= call_names
        assert "DictReader" not in call_names and "reader" not in call_names

    def test_unresolved_lecturer_in_database_fails_closed(self, monkeypatch, fx):
        def resolve(selected, session):
            raise rp.ReviewPackageError("Canonical lecturer resolution failed")

        monkeypatch.setattr(rp, "resolve_canonical_lecturers_from_db", resolve)
        with pytest.raises(VerificationError, match="re-render failed"):
            self._run(fx)

    def test_rerender_performs_no_writes(self):
        tree = ast.parse(inspect.getsource(ve.verify_package_rerender))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"commit", "add", "add_all", "flush", "delete", "merge", "write_bytes", "write_text"}
