"""Unit tests for the dataset validator script (no DB)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_ictu_lecturer_dataset.py"
DATASET_PATH = REPO_ROOT.parent / "data" / "lecturers" / "ictu_lecturers.json"
EXAMPLE_PATH = REPO_ROOT.parent / "data" / "lecturers" / "ictu_lecturers.example.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.validate_ictu_lecturer_dataset", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def test_validator_accepts_canonical_dataset() -> None:
    if not DATASET_PATH.exists():
        pytest.skip("Canonical dataset not built yet — run scripts.build_ictu_lecturer_dataset.")
    result = _run(str(DATASET_PATH))
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_validator_strict_count_matches() -> None:
    if not DATASET_PATH.exists():
        pytest.skip("Canonical dataset not built yet.")
    # Canonical DSpace-archive dataset is exactly 410 records (M2.5A §3).
    result = _run("--expected-count", "410", str(DATASET_PATH))
    assert result.returncode == 0, result.stderr


def test_validator_strict_count_mismatch() -> None:
    if not DATASET_PATH.exists():
        pytest.skip("Canonical dataset not built yet.")
    result = _run("--expected-count", "33", str(DATASET_PATH))
    assert result.returncode == 2
    assert "EXPECTED_COUNT_MISMATCH" in result.stderr


def test_validator_rejects_missing_file() -> None:
    result = _run(str(REPO_ROOT / "does-not-exist.json"))
    assert result.returncode == 2
    assert "FILE_NOT_FOUND" in result.stderr


def test_validator_accepts_example_dataset() -> None:
    if not EXAMPLE_PATH.exists():
        pytest.skip("Example dataset not built yet.")
    result = _run(str(EXAMPLE_PATH))
    assert result.returncode == 0, result.stderr


def test_validator_rejects_invalid_json() -> None:
    bad = REPO_ROOT / "tests" / "fixtures" / "_invalid_lecturer.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not-json", encoding="utf-8")
    try:
        result = _run(str(bad))
        assert result.returncode == 2
        assert "INVALID_JSON" in result.stderr
    finally:
        bad.unlink(missing_ok=True)


def test_validator_rejects_forbidden_field() -> None:
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8")) if DATASET_PATH.exists() else None
    if payload is None:
        pytest.skip("Canonical dataset not built yet.")
    payload["lecturers"][0]["password"] = "hunter2"
    tmp = REPO_ROOT / "tests" / "fixtures" / "_with_password.json"
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        result = _run(str(tmp))
        assert result.returncode == 2
        assert "FORBIDDEN_FIELDS_PRESENT" in result.stderr
    finally:
        tmp.unlink(missing_ok=True)
