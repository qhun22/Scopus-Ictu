"""Backup/restore refusals that need no database: protected names, bad names, tampered dumps."""

from __future__ import annotations

import hashlib

import pytest

from scripts import db_backup


@pytest.mark.parametrize("name", ["scopus_ictu_app", "scopus_ictu_demo_teacher_20261014", "postgres", "template1"])
def test_protected_databases_are_refused_as_restore_targets(name):
    with pytest.raises(db_backup.BackupError, match="bao ve"):
        db_backup._check_target_name(name)


@pytest.mark.parametrize("name", ["Bad Name", "x", "1abc", "has-dash", "UPPER", "a" * 64, "drop;table"])
def test_malformed_names_are_refused(name):
    with pytest.raises(db_backup.BackupError):
        db_backup._check_target_name(name)


def test_a_new_snake_case_name_is_accepted():
    db_backup._check_target_name("restore_check_20261102")


def _dump(tmp_path, content: bytes, *, checksum: str | None):
    dump = tmp_path / "x.dump"
    dump.write_bytes(content)
    if checksum is not None:
        (tmp_path / "x.dump.sha256").write_text(f"{checksum} *x.dump\n", encoding="ascii")
    return dump


def test_a_dump_with_a_matching_checksum_passes(tmp_path):
    content = b"synthetic dump bytes"
    dump = _dump(tmp_path, content, checksum=hashlib.sha256(content).hexdigest())
    assert db_backup._verify_checksum(dump) == hashlib.sha256(content).hexdigest()


def test_a_tampered_dump_is_refused(tmp_path):
    dump = _dump(tmp_path, b"changed after backup", checksum=hashlib.sha256(b"original").hexdigest())
    with pytest.raises(db_backup.BackupError, match="KHONG khop"):
        db_backup._verify_checksum(dump)


def test_a_dump_without_a_checksum_file_is_refused(tmp_path):
    dump = _dump(tmp_path, b"anything", checksum=None)
    with pytest.raises(db_backup.BackupError, match="sha256"):
        db_backup._verify_checksum(dump)
