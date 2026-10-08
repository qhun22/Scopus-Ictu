"""Unit tests for the C3 evaluation source-snapshot dump orchestrator (C3-A3 P1).

Mocks only: fake session, fake subprocess runner.  pg_dump / pg_restore are
never executed and no database is contacted.

R4/R5/R6 tests verify actual side-effects on temporary files:
- R4: same-path rejection before any session is opened.
- R5: metadata atomic no-clobber promotion (os.link staging).
- R6: archive exclusive promotion (os.link partial -> archive).
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.matching import eval_source_dump as sd
from app.services.matching import verified_evaluation as ve

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "backend/scripts/dump_c3_eval_source.py"
_EVAL_SCRIPT = _REPO_ROOT / "backend/scripts/run_matching_quality_evaluation.py"
_SNAPSHOT = "00000003-0000001B-1"
_PASSWORD = "S3cr3t-DO_NOT_LEAK"
_HOST = "internal-db-host"
_ARCHIVE_BYTES = b"PGDMP-fake-archive-bytes"

_PARAMS = sd.ConnectionParams(host=_HOST, port=5432, user="reader", password=_PASSWORD, database=sd.SOURCE_DATABASE_NAME)

# A parent-before-child order of the nine tables.
_GOOD_ORDER = (
    "lecturers",
    "lecturer_source_snapshots",
    "lecturer_known_publications",
    "publications",
    "scopus_authors",
    "publication_authors",
    "scopus_imports",
    "raw_scopus_records",
    "scopus_author_name_variants",
)


def _toc(tables=_GOOD_ORDER, extra_lines=()) -> str:
    lines = [
        ";",
        "; Archive created at 2026-10-08 10:00:00 UTC",
        ";     Format: CUSTOM",
        ";",
    ]
    for i, table in enumerate(tables, start=3000):
        lines.append(f"{i}; 0 {16000 + i} TABLE DATA public {table} owner_role")
    lines.extend(extra_lines)
    return "\n".join(lines) + "\n"


def _fingerprint() -> ve.InputFingerprint:
    tables = tuple(
        ve.TableFingerprint(
            table=t,
            hash_kind="primary_key" if t in ve.FINGERPRINT_KEY_TABLES else "content",
            columns=("id",),
            row_count=i + 1,
            sha256=f"{i:x}" * 64,
        )
        for i, t in enumerate(sd.DUMP_TABLES)
    )
    return ve.InputFingerprint(schema_version=1, sha256="e" * 64, tables=tables)


class _Session:
    """Fake session: answers the orchestrator's SQL and tracks transaction state."""

    def __init__(self, *, connected=sd.SOURCE_DATABASE_NAME, revisions=(sd.EXPECTED_ALEMBIC_REVISION,),
                 snapshot=_SNAPSHOT, fail_on=None, rollback_error=None):
        self.connected = connected
        self.revisions = list(revisions)
        self.snapshot = snapshot
        self.fail_on = fail_on
        self.rollback_error = rollback_error
        self.statements: list[str] = []
        self.events: list[str] = []
        self.in_transaction = False

    def execute(self, statement, *_a, **_k):
        sql = str(statement)
        self.statements.append(sql)
        self.in_transaction = True
        if self.fail_on is not None and self.fail_on in sql:
            from sqlalchemy.exc import OperationalError

            raise OperationalError(sql, {}, Exception(f"host={_HOST} password={_PASSWORD}"))
        if sql == "SELECT current_database()":
            return SimpleNamespace(scalar_one=lambda: self.connected)
        if sql == "SELECT version_num FROM alembic_version":
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(self.revisions)))
        if sql == "SELECT pg_export_snapshot()":
            self.events.append("export_snapshot")
            return SimpleNamespace(scalar_one=lambda: self.snapshot)
        return SimpleNamespace()

    def rollback(self):
        self.events.append("rollback")
        self.in_transaction = False
        if self.rollback_error is not None:
            raise self.rollback_error

    def commit(self):
        raise AssertionError("commit must never be called")


class _Runner:
    """Fake subprocess.run for pg_dump and pg_restore --list."""

    def __init__(self, session, *, dump_rc=0, dump_exc=None, write=True, toc=None, restore_rc=0,
                 partial_bytes=_ARCHIVE_BYTES):
        self.session = session
        self.dump_rc = dump_rc
        self.dump_exc = dump_exc
        self.write = write
        self.toc = _toc() if toc is None else toc
        self.restore_rc = restore_rc
        self.partial_bytes = partial_bytes
        self.calls: list[dict] = []

    def __call__(self, argv, **kwargs):
        self.calls.append({"argv": list(argv), **kwargs})
        if Path(argv[0]).name.startswith("pg_dump"):
            self.session.events.append("pg_dump")
            assert self.session.in_transaction, "pg_dump must run while the exporting transaction is open"
            if self.dump_exc is not None:
                raise self.dump_exc
            file_arg = next(a for a in argv if a.startswith("--file="))
            if self.write:
                Path(file_arg[len("--file="):]).write_bytes(self.partial_bytes)
            return subprocess.CompletedProcess(argv, self.dump_rc, "", f"pg_dump: error: host={_HOST} {_PASSWORD}")
        self.session.events.append("pg_restore_list")
        assert self.session.in_transaction
        return subprocess.CompletedProcess(argv, self.restore_rc, self.toc, "")


def _dump(tmp_path, session=None, runner=None, fingerprint=None, **kwargs):
    session = session or _Session()
    runner = runner or _Runner(session)
    calls: list[str] = []

    def fp(s):
        assert s is session
        calls.append("fingerprint")
        session.events.append("fingerprint")
        return fingerprint or _fingerprint()

    archive = tmp_path / "source.dump"
    result = sd.dump_source_snapshot(
        session,
        params=_PARAMS,
        archive_path=archive,
        runner=runner,
        base_env={"PATH": "/usr/bin", "PGPASSWORD": "inherited", "PGSERVICE": "x", "pgdatabase": "y"},
        compute_fingerprint=fp,
        **kwargs,
    )
    return result, session, runner, archive


# ===========================================================================
# Contract constants
# ===========================================================================


class TestContract:
    def test_nine_tables_are_exactly_fingerprint_v1_tables(self):
        assert len(sd.DUMP_TABLES) == 9
        assert set(sd.DUMP_TABLES) == set(ve.FINGERPRINT_CONTENT_COLUMNS) | set(ve.FINGERPRINT_KEY_TABLES)
        assert set(sd.TABLE_PARENTS) == set(sd.DUMP_TABLES)

    def test_source_and_revision_pins(self):
        assert sd.SOURCE_DATABASE_NAME == "scopus_ictu_acceptance_v2"
        assert sd.EXPECTED_ALEMBIC_REVISION == "d3f7a1c9e2b4"

    def test_fingerprint_v1_and_evaluation_gate_unchanged(self):
        assert ve.FINGERPRINT_SCHEMA_VERSION == 1
        assert ve.EXPECTED_INPUT_FINGERPRINT_SHA256 is None
        assert ve.APPROVED_DATABASE_NAME == "scopus_c3_eval_v1"
        assert "scopus_ictu_acceptance_v2" in ve.REJECTED_DATABASE_NAMES
        assert ve.is_approved_database("postgresql+psycopg2://u:p@h/scopus_ictu_acceptance_v2") is False

    def test_parent_order_reflects_model_foreign_keys(self):
        from app.models import Base

        for table in sd.DUMP_TABLES:
            referenced = {
                fk.column.table.name
                for fk in Base.metadata.tables[table].foreign_keys
                if fk.column.table.name in sd.DUMP_TABLES and fk.column.table.name != table
            }
            assert referenced == set(sd.TABLE_PARENTS[table]), table


class TestSourceAllowlist:
    def _url(self, name):
        return f"postgresql+psycopg2://u:p@localhost:5432/{name}"

    def test_only_acceptance_source_accepted(self):
        assert sd.is_source_database(self._url("scopus_ictu_acceptance_v2")) is True

    @pytest.mark.parametrize(
        "name",
        ["scopus_c3_eval_v1", "scopus_m12_test", "SCOPUS_ICTU_ACCEPTANCE_V2", "scopus_ictu_acceptance_v2_copy", ""],
    )
    def test_other_names_rejected(self, name):
        assert sd.is_source_database(self._url(name)) is False

    def test_malformed_url_rejected(self):
        assert sd.is_source_database("not a url") is False


# ===========================================================================
# Orchestrator happy path
# ===========================================================================


class TestOrchestratorSuccess:
    def test_order_one_open_transaction(self, tmp_path):
        result, session, _runner, archive = _dump(tmp_path)
        assert session.statements[:3] == [
            ve.READ_ONLY_SNAPSHOT_SQL,
            "SELECT current_database()",
            "SELECT version_num FROM alembic_version",
        ]
        assert session.events == ["fingerprint", "export_snapshot", "pg_dump", "pg_restore_list", "rollback"]
        assert archive.read_bytes() == _ARCHIVE_BYTES
        assert not sd.partial_path_for(archive).exists()
        assert result.snapshot_id == _SNAPSHOT
        assert result.alembic_revision == "d3f7a1c9e2b4"
        assert result.fingerprint.sha256 == "e" * 64

    def test_pg_dump_argv(self, tmp_path):
        _result, _session, runner, archive = _dump(tmp_path)
        argv = runner.calls[0]["argv"]
        assert argv[0] == "pg_dump"
        assert f"--snapshot={_SNAPSHOT}" in argv
        assert f"--file={sd.partial_path_for(archive)}" in argv
        assert {"--format=custom", "--data-only", "--no-password", "--strict-names"} <= set(argv)
        tables = [a for a in argv if a.startswith("--table=")]
        assert tables == [f"--table=public.{t}" for t in sd.DUMP_TABLES]
        assert not any("disable-triggers" in a for a in argv)
        assert not any(a.startswith(("--username", "--password", "--host", "--dbname", "-U", "-W", "-h", "-d")) for a in argv)

    def test_credentials_only_in_child_environment(self, tmp_path):
        _result, _session, runner, _archive = _dump(tmp_path)
        dump_call, list_call = runner.calls
        joined = " ".join(dump_call["argv"] + list_call["argv"])
        assert _PASSWORD not in joined and "reader" not in joined and _HOST not in joined
        env = dump_call["env"]
        assert env["PGPASSWORD"] == _PASSWORD and env["PGUSER"] == "reader"
        assert env["PGHOST"] == _HOST and env["PGPORT"] == "5432"
        assert env["PGDATABASE"] == sd.SOURCE_DATABASE_NAME
        assert "PGSERVICE" not in env and "pgdatabase" not in env and env["PATH"] == "/usr/bin"
        # pg_restore --list reads the file only: no credentials at all.
        assert not any(k.upper().startswith("PG") for k in list_call["env"])
        assert dump_call["timeout"] == sd.PG_DUMP_TIMEOUT_SECONDS
        assert dump_call["check"] is False and dump_call["capture_output"] is True

    def test_connection_params_repr_redacted(self):
        assert _PASSWORD not in repr(_PARAMS) and _HOST not in repr(_PARAMS)

    def test_metadata(self, tmp_path):
        import hashlib

        result, _session, _runner, archive = _dump(tmp_path)
        meta = result.metadata(archive.name)
        assert meta["alembic_revision"] == "d3f7a1c9e2b4"
        assert meta["snapshot_id"] == _SNAPSHOT
        assert meta["archive_sha256"] == hashlib.sha256(_ARCHIVE_BYTES).hexdigest()
        assert meta["archive_file"] == "source.dump"
        assert set(meta["table_row_counts"]) == set(sd.DUMP_TABLES)
        assert meta["input_fingerprint"] == _fingerprint().as_dict()
        assert meta["input_fingerprint"]["schema_version"] == 1
        assert meta["archive_parent_before_child"] is True
        assert sd.SOURCE_DATABASE_NAME not in json.dumps(meta)

    def test_wrong_order_reported_not_refused(self, tmp_path):
        reversed_order = tuple(reversed(_GOOD_ORDER))
        session = _Session()
        result, *_ = _dump(tmp_path, session=session, runner=_Runner(session, toc=_toc(reversed_order)))
        assert result.toc.parent_before_child is False
        assert result.toc.data_tables == reversed_order


# ===========================================================================
# Orchestrator failures: rollback, partial removed, nothing published
# ===========================================================================


def _assert_failed_cleanly(tmp_path, session):
    archive = tmp_path / "source.dump"
    assert not archive.exists()
    assert not sd.partial_path_for(archive).exists()
    assert session.events[-1] == "rollback"
    assert session.in_transaction is False


class TestOrchestratorFailures:
    def test_pg_dump_nonzero_exit(self, tmp_path):
        session = _Session()
        with pytest.raises(sd.SourceDumpError) as exc_info:
            _dump(tmp_path, session=session, runner=_Runner(session, dump_rc=1))
        _assert_failed_cleanly(tmp_path, session)
        assert _PASSWORD not in str(exc_info.value) and _HOST not in str(exc_info.value)
        assert "pg_restore_list" not in session.events

    @pytest.mark.parametrize(
        "exc",
        [subprocess.TimeoutExpired("pg_dump", 1), FileNotFoundError("pg_dump"), PermissionError("denied")],
    )
    def test_pg_dump_cannot_run(self, tmp_path, exc):
        session = _Session()
        with pytest.raises(sd.SourceDumpError):
            _dump(tmp_path, session=session, runner=_Runner(session, dump_exc=exc))
        _assert_failed_cleanly(tmp_path, session)

    def test_pg_dump_success_without_archive(self, tmp_path):
        session = _Session()
        with pytest.raises(sd.SourceDumpError, match="no archive"):
            _dump(tmp_path, session=session, runner=_Runner(session, write=False))
        _assert_failed_cleanly(tmp_path, session)

    def test_pg_restore_list_fails(self, tmp_path):
        session = _Session()
        with pytest.raises(sd.SourceDumpError):
            _dump(tmp_path, session=session, runner=_Runner(session, restore_rc=1))
        _assert_failed_cleanly(tmp_path, session)

    @pytest.mark.parametrize(
        "toc",
        [
            _toc(_GOOD_ORDER[:-1]),
            _toc(_GOOD_ORDER + ("publication_raw_sources",)),
            _toc(_GOOD_ORDER + ("lecturers",)),
            _toc(_GOOD_ORDER, extra_lines=["4000; 1259 17000 TABLE public lecturers owner_role"]),
            _toc(_GOOD_ORDER, extra_lines=["4001; 0 0 SEQUENCE SET public some_seq owner_role"]),
            _toc(_GOOD_ORDER, extra_lines=["garbage line"]),
            _toc(_GOOD_ORDER).replace("TABLE DATA public lecturers ", "TABLE DATA other lecturers "),
        ],
        ids=["missing", "extra-table", "duplicate", "schema-entry", "sequence-set", "garbage", "other-schema"],
    )
    def test_bad_toc_rejected(self, tmp_path, toc):
        session = _Session()
        with pytest.raises(sd.SourceDumpError):
            _dump(tmp_path, session=session, runner=_Runner(session, toc=toc))
        _assert_failed_cleanly(tmp_path, session)

    def test_fingerprint_error_before_snapshot_export(self, tmp_path):
        session = _Session()
        runner = _Runner(session)

        def boom(_s):
            raise ve.VerificationError("Fingerprint input for lecturers has duplicate or invalid primary keys.")

        with pytest.raises(ve.VerificationError):
            sd.dump_source_snapshot(
                session, params=_PARAMS, archive_path=tmp_path / "source.dump", runner=runner,
                base_env={}, compute_fingerprint=boom,
            )
        assert "export_snapshot" not in session.events and runner.calls == []
        _assert_failed_cleanly(tmp_path, session)

    @pytest.mark.parametrize("connected", ["scopus_c3_eval_v1", "scopus_m12_test", "postgres"])
    def test_wrong_connected_database(self, tmp_path, connected):
        session = _Session(connected=connected)
        runner = _Runner(session)
        with pytest.raises(sd.SourceDumpError) as exc_info:
            _dump(tmp_path, session=session, runner=runner)
        assert connected not in str(exc_info.value)
        assert "fingerprint" not in session.events and runner.calls == []
        _assert_failed_cleanly(tmp_path, session)

    @pytest.mark.parametrize("revisions", [(), ("b27c9d1e4f60",), ("d3f7a1c9e2b4", "d3f7a1c9e2b4")])
    def test_wrong_alembic_revision(self, tmp_path, revisions):
        session = _Session(revisions=revisions)
        runner = _Runner(session)
        with pytest.raises(sd.SourceDumpError, match="Alembic"):
            _dump(tmp_path, session=session, runner=runner)
        assert "fingerprint" not in session.events and runner.calls == []
        _assert_failed_cleanly(tmp_path, session)

    @pytest.mark.parametrize("snapshot", ["", "x; rm -rf /", "--file=/etc/passwd", None, "0000-00 01"])
    def test_malformed_snapshot_id(self, tmp_path, snapshot):
        session = _Session(snapshot=snapshot)
        runner = _Runner(session)
        with pytest.raises(sd.SourceDumpError, match="snapshot"):
            _dump(tmp_path, session=session, runner=runner)
        assert runner.calls == []
        _assert_failed_cleanly(tmp_path, session)

    def test_read_only_transaction_failure(self, tmp_path):
        session = _Session(fail_on="SET TRANSACTION")
        with pytest.raises(sd.SourceDumpError) as exc_info:
            _dump(tmp_path, session=session)
        assert _PASSWORD not in str(exc_info.value)
        _assert_failed_cleanly(tmp_path, session)

    def test_database_error_propagates_after_cleanup(self, tmp_path):
        from sqlalchemy.exc import OperationalError

        session = _Session(fail_on="pg_export_snapshot")
        with pytest.raises(OperationalError):
            _dump(tmp_path, session=session)
        _assert_failed_cleanly(tmp_path, session)

    def test_rollback_failure_after_dump_discards_archive(self, tmp_path):
        session = _Session(rollback_error=RuntimeError("connection lost"))
        with pytest.raises(sd.SourceDumpError, match="close"):
            _dump(tmp_path, session=session)
        archive = tmp_path / "source.dump"
        assert not archive.exists() and not sd.partial_path_for(archive).exists()

    def test_keyboard_interrupt_during_dump_cleans_up(self, tmp_path):
        session = _Session()

        class _Interrupting(_Runner):
            def __call__(self, argv, **kwargs):
                file_arg = next(a for a in argv if a.startswith("--file="))
                Path(file_arg[len("--file="):]).write_bytes(b"half")
                raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            _dump(tmp_path, session=session, runner=_Interrupting(session))
        _assert_failed_cleanly(tmp_path, session)

    def test_refuses_existing_archive_or_partial(self, tmp_path):
        archive = tmp_path / "source.dump"
        archive.write_bytes(b"old")
        session = _Session()
        with pytest.raises(sd.SourceDumpError, match="overwrite"):
            _dump(tmp_path, session=session)
        assert archive.read_bytes() == b"old" and session.statements == []
        archive.unlink()
        sd.partial_path_for(archive).write_bytes(b"stale")
        with pytest.raises(sd.SourceDumpError, match="partial"):
            _dump(tmp_path, session=_Session())


# ===========================================================================
# ToC parser
# ===========================================================================


class TestToc:
    def test_good_toc(self):
        check = sd.check_archive_toc(_toc())
        assert check.data_tables == _GOOD_ORDER and check.parent_before_child is True

    def test_header_entries_allowed(self):
        toc = _toc(extra_lines=["1; 0 0 ENCODING - ENCODING ", "2; 0 0 STDSTRINGS - STDSTRINGS ",
                                "3; 0 0 SEARCHPATH - SEARCHPATH "])
        assert sd.check_archive_toc(toc).data_tables == _GOOD_ORDER

    @pytest.mark.parametrize(
        ("child", "parent"),
        [(c, p) for c, ps in sd.TABLE_PARENTS.items() for p in ps],
    )
    def test_each_child_before_parent_detected(self, child, parent):
        order = [t for t in _GOOD_ORDER if t != child]
        order.insert(order.index(parent), child)
        assert sd.is_parent_before_child(order) is False


# ===========================================================================
# Structural separation from evaluate
# ===========================================================================


def _names_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


_EVALUATE_PATH = {
    "evaluate",
    "_evaluate",
    "verify_input_fingerprint",
    "require_pinned_fingerprint",
    "run_frozen_a1_evaluation",
    "verify_package_rerender",
    "verify_offline_inputs",
    "build_result",
    "is_approved_database",
    "verify_connected_database",
    "APPROVED_DATABASE_NAME",
    "scopus_c3_eval_v1",
}


class TestSeparation:
    def test_source_dump_module_has_no_evaluate_path(self):
        module_path = Path(inspect.getsourcefile(sd))
        assert not (_names_in(module_path) & _EVALUATE_PATH)

    def test_source_dump_script_has_no_evaluate_path(self):
        assert not (_names_in(_SCRIPT) & _EVALUATE_PATH)

    def test_no_write_apis_in_source_dump(self):
        # "flush" is permitted in write_metadata_atomic (file I/O flush+fsync).
        # "delete" is permitted in NamedTemporaryFile(delete=False).
        _db_write_attrs = {"commit", "add", "add_all", "add_all", "merge"}
        for path in (Path(inspect.getsourcefile(sd)), _SCRIPT):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Attribute):
                    assert node.attr not in _db_write_attrs
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    upper = node.value.upper()
                    assert not upper.lstrip().startswith(("INSERT", "UPDATE", "DELETE", "ALTER", "DROP",
                                                          "CREATE", "TRUNCATE", "LOCK"))
                    assert "--disable-triggers" not in node.value

    def test_evaluation_cli_subcommands_unchanged(self):
        spec = importlib.util.spec_from_file_location("run_mqe_cli_sep", _EVAL_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        parser = module._build_parser()
        sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        assert set(sub.choices) == {"prepare-cohort", "compute-fingerprint", "evaluate"}
        assert "eval_source_dump" not in _EVAL_SCRIPT.read_text(encoding="utf-8")


# ===========================================================================
# CLI (settings + engine mocked; orchestrator real with fake runner)
# ===========================================================================


class TestCli:
    def _load(self):
        spec = importlib.util.spec_from_file_location("dump_c3_eval_source_cli", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _setup(self, monkeypatch, db_name=sd.SOURCE_DATABASE_NAME, environment="local", session=None,
               runner_kwargs=None):
        import sqlalchemy
        import sqlalchemy.orm
        from app.core.config import settings

        monkeypatch.setattr(settings, "environment", environment)
        monkeypatch.setattr(settings, "db_name", db_name)
        monkeypatch.setattr(settings, "db_password", _PASSWORD)
        monkeypatch.setattr(settings, "db_host", _HOST)
        state = SimpleNamespace(created=False, disposed=False)
        session = session or _Session()

        class _Engine:
            def dispose(self):
                state.disposed = True

        class _SessionCtx:
            def __init__(self, *_a, **_k):
                pass

            def __enter__(self):
                return session

            def __exit__(self, *_a):
                return False

        def _create(*_a, **_k):
            state.created = True
            return _Engine()

        monkeypatch.setattr(sqlalchemy, "create_engine", _create)
        monkeypatch.setattr(sqlalchemy.orm, "Session", _SessionCtx)
        runner = _Runner(session, **(runner_kwargs or {}))
        real = sd.dump_source_snapshot

        def _with_mocks(sess, **kwargs):
            return real(sess, runner=runner, compute_fingerprint=lambda _s: _fingerprint(), **kwargs)

        monkeypatch.setattr(sd, "dump_source_snapshot", _with_mocks)
        state.session, state.runner = session, runner
        return state

    def _out(self, tmp_path):
        return ["--archive-out", str(tmp_path / "src.dump"), "--metadata-out", str(tmp_path / "src.json")]

    def test_success_writes_archive_and_metadata(self, monkeypatch, capsys, tmp_path):
        cli = self._load()
        state = self._setup(monkeypatch)
        assert cli.main(self._out(tmp_path)) == 0
        meta = json.loads((tmp_path / "src.json").read_text(encoding="utf-8"))
        assert meta["snapshot_id"] == _SNAPSHOT and meta["alembic_revision"] == "d3f7a1c9e2b4"
        assert (tmp_path / "src.dump").read_bytes() == _ARCHIVE_BYTES
        assert state.disposed is True
        out = capsys.readouterr()
        for secret in (_PASSWORD, _HOST, sd.SOURCE_DATABASE_NAME):
            assert secret not in out.out + out.err

    def test_dump_failure_publishes_nothing(self, monkeypatch, capsys, tmp_path):
        cli = self._load()
        state = self._setup(monkeypatch, runner_kwargs={"dump_rc": 2})
        assert cli.main(self._out(tmp_path)) == 1
        assert sorted(p.name for p in tmp_path.iterdir()) == []
        assert state.disposed is True
        out = capsys.readouterr()
        assert _PASSWORD not in out.out + out.err and _HOST not in out.out + out.err

    @pytest.mark.parametrize("db_name", ["scopus_c3_eval_v1", "scopus_m12_test"])
    def test_refuses_non_source_configured_database(self, monkeypatch, capsys, tmp_path, db_name):
        cli = self._load()
        state = self._setup(monkeypatch, db_name=db_name)
        assert cli.main(self._out(tmp_path)) == 1
        assert state.created is False
        assert db_name not in capsys.readouterr().err

    def test_refuses_prod(self, monkeypatch, tmp_path):
        cli = self._load()
        state = self._setup(monkeypatch, environment="prod")
        assert cli.main(self._out(tmp_path)) == 1
        assert state.created is False

    def test_refuses_existing_outputs(self, monkeypatch, tmp_path):
        cli = self._load()
        state = self._setup(monkeypatch)
        (tmp_path / "src.json").write_text("{}", encoding="utf-8")
        assert cli.main(self._out(tmp_path)) == 1
        assert state.created is False

    def test_database_error_redacted(self, monkeypatch, capsys, tmp_path):
        cli = self._load()
        state = self._setup(monkeypatch, session=_Session(fail_on="alembic_version"))
        assert cli.main(self._out(tmp_path)) == 1
        assert state.disposed is True and list(tmp_path.iterdir()) == []
        out = capsys.readouterr()
        assert _PASSWORD not in out.out + out.err and _HOST not in out.out + out.err


# ===========================================================================
# R4 — Same-path rejection (archive vs metadata)
# ===========================================================================


class TestR4SamePath:
    """All rejections must happen before any DB session is opened."""

    def _load_cli(self):
        spec = importlib.util.spec_from_file_location("dump_c3_eval_source_r4", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _setup_no_db(self, monkeypatch):
        import sqlalchemy
        state = SimpleNamespace(engine_created=False)

        def _boom(*_a, **_k):
            state.engine_created = True
            raise AssertionError("Engine must not be created for same-path rejection")

        monkeypatch.setattr(sqlalchemy, "create_engine", _boom)
        from app.core.config import settings
        monkeypatch.setattr(settings, "environment", "local")
        monkeypatch.setattr(settings, "db_name", sd.SOURCE_DATABASE_NAME)
        monkeypatch.setattr(settings, "db_password", "x")
        monkeypatch.setattr(settings, "db_host", "h")
        return state

    def test_same_literal_path_rejected(self, monkeypatch, capsys, tmp_path):
        cli = self._load_cli()
        state = self._setup_no_db(monkeypatch)
        path = str(tmp_path / "out.dump")
        assert cli.main(["--archive-out", path, "--metadata-out", path]) == 1
        assert not state.engine_created
        err = capsys.readouterr().err
        assert _PASSWORD not in err and _HOST not in err
        assert not any(tmp_path.iterdir())

    def test_same_path_via_resolve_rejected(self, monkeypatch, capsys, tmp_path):
        cli = self._load_cli()
        self._setup_no_db(monkeypatch)
        # Two lexically different strings resolving to the same path.
        a = str(tmp_path / "sub" / ".." / "out.dump")
        b = str(tmp_path / "out.dump")
        assert cli.main(["--archive-out", a, "--metadata-out", b]) == 1

    def test_same_path_via_symlink_rejected(self, monkeypatch, capsys, tmp_path):
        cli = self._load_cli()
        self._setup_no_db(monkeypatch)
        real = tmp_path / "out.dump"
        link = tmp_path / "link.dump"
        real.write_bytes(b"x")
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation not supported in this environment")
        assert cli.main(["--archive-out", str(real), "--metadata-out", str(link)]) == 1

    def test_same_path_helper_unit(self, tmp_path):
        a = tmp_path / "x.dump"
        b = tmp_path / "x.dump"
        assert sd._same_path(a, b) is True
        assert sd._same_path(a, tmp_path / "y.dump") is False

    def test_same_path_resolve_alias(self, tmp_path):
        # sub/../x.dump resolves to x.dump
        a = tmp_path / "sub" / ".." / "x.dump"
        b = tmp_path / "x.dump"
        assert sd._same_path(a, b) is True

    def test_same_path_inode_existing_files(self, tmp_path):
        a = tmp_path / "x.dump"
        b = tmp_path / "y.dump"
        a.write_bytes(b"data")
        import os
        os.link(a, b)  # hard link: same inode
        assert sd._same_path(a, b) is True


# ===========================================================================
# R6 — Exclusive archive promotion (os.link no-clobber)
# ===========================================================================


class TestR6ArchivePromotion:
    def test_exclusive_promote_succeeds(self, tmp_path):
        staging = tmp_path / "staging"
        staging.write_bytes(b"archive-data")
        dest = tmp_path / "archive.dump"
        sd.exclusive_promote(staging, dest)
        assert dest.read_bytes() == b"archive-data"
        assert not staging.exists()

    def test_exclusive_promote_collision_raises(self, tmp_path):
        staging = tmp_path / "staging"
        staging.write_bytes(b"new")
        dest = tmp_path / "archive.dump"
        dest.write_bytes(b"existing")
        with pytest.raises(sd.SourceDumpError, match="promotion"):
            sd.exclusive_promote(staging, dest)
        # Destination is untouched; staging is preserved for cleanup.
        assert dest.read_bytes() == b"existing"
        assert staging.exists()

    def test_archive_promotion_collision_via_exclusive_promote(self, tmp_path):
        """exclusive_promote raises when destination exists; pre-existing content survives."""
        staging = tmp_path / "source.dump.partial"
        staging.write_bytes(b"new-archive-data")
        dest = tmp_path / "source.dump"
        dest.write_bytes(b"concurrent-write")
        with pytest.raises(sd.SourceDumpError, match="promotion"):
            sd.exclusive_promote(staging, dest)
        assert dest.read_bytes() == b"concurrent-write"
        assert staging.exists()

    def test_cleanup_oserror_tracked_not_swallowed(self, tmp_path, monkeypatch):
        """If cleanup itself raises OSError, result reports it (incomplete=True)."""
        f = tmp_path / "leftover.dump"
        f.write_bytes(b"x")
        orig = Path.unlink

        def _fail(self, missing_ok=False):
            raise OSError("simulated unlink failure")

        monkeypatch.setattr(Path, "unlink", _fail)
        result = sd.cleanup_owned_artifacts([f])
        assert result.incomplete
        assert "incomplete" in result.summary()
        assert _PASSWORD not in result.summary() and _HOST not in result.summary()


# ===========================================================================
# R5 — Metadata atomic no-clobber promotion
# ===========================================================================


class TestR5MetadataPromotion:
    def _run_cli_with_real_orchestrator(self, monkeypatch, tmp_path, *, runner_kwargs=None,
                                        session=None):
        """CLI with mocked DB but real orchestrator + real file ops."""
        import sqlalchemy
        import sqlalchemy.orm
        from app.core.config import settings

        monkeypatch.setattr(settings, "environment", "local")
        monkeypatch.setattr(settings, "db_name", sd.SOURCE_DATABASE_NAME)
        monkeypatch.setattr(settings, "db_password", _PASSWORD)
        monkeypatch.setattr(settings, "db_host", _HOST)

        sess = session or _Session()

        class _Engine:
            def dispose(self): pass

        class _SessionCtx:
            def __init__(self, *_a, **_k): pass
            def __enter__(self): return sess
            def __exit__(self, *_a): return False

        monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_a, **_k: _Engine())
        monkeypatch.setattr(sqlalchemy.orm, "Session", _SessionCtx)

        runner = _Runner(sess, **(runner_kwargs or {}))
        real = sd.dump_source_snapshot

        def _with_fp(s, **kwargs):
            return real(s, runner=runner, compute_fingerprint=lambda _s: _fingerprint(), **kwargs)

        monkeypatch.setattr(sd, "dump_source_snapshot", _with_fp)
        return sess, runner

    def test_metadata_written_atomically_and_archive_present(self, monkeypatch, tmp_path):
        """Success path: both archive and metadata are present; no staging leftover."""
        spec = importlib.util.spec_from_file_location("dump_cli_r5_ok", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self._run_cli_with_real_orchestrator(monkeypatch, tmp_path)
        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"

        assert module.main(["--archive-out", str(archive), "--metadata-out", str(meta)]) == 0
        assert archive.is_file()
        assert meta.is_file()
        payload = json.loads(meta.read_text(encoding="utf-8"))
        assert payload["alembic_revision"] == "d3f7a1c9e2b4"
        # No staging files left over.
        assert not any(p.suffix == ".meta_staging" for p in tmp_path.iterdir())

    def test_metadata_destination_collision_removes_archive(self, monkeypatch, capsys, tmp_path):
        """If metadata destination appears after preflight, archive is removed."""
        spec = importlib.util.spec_from_file_location("dump_cli_r5_col", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"

        self._run_cli_with_real_orchestrator(monkeypatch, tmp_path)

        # Intercept exclusive_promote to simulate a race on the metadata dest.
        real_promote = sd.exclusive_promote
        call_count = [0]

        def _racing_promote(staging, destination):
            call_count[0] += 1
            if destination == meta:
                # Concurrent write to metadata destination.
                meta.write_bytes(b"concurrent-meta")
            return real_promote(staging, destination)

        monkeypatch.setattr(sd, "exclusive_promote", _racing_promote)

        assert module.main(["--archive-out", str(archive), "--metadata-out", str(meta)]) == 1
        # Archive must be removed because metadata failed.
        assert not archive.exists()
        # The concurrent metadata file must not be overwritten.
        assert meta.read_bytes() == b"concurrent-meta"
        out = capsys.readouterr()
        assert _PASSWORD not in out.out + out.err

    def test_metadata_write_failure_removes_archive(self, monkeypatch, capsys, tmp_path):
        """If metadata staging write raises OSError, archive is removed."""
        spec = importlib.util.spec_from_file_location("dump_cli_r5_wr", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"

        self._run_cli_with_real_orchestrator(monkeypatch, tmp_path)

        def _boom_write(content, destination):
            raise OSError("disk full")

        monkeypatch.setattr(sd, "write_metadata_atomic", _boom_write)
        assert module.main(["--archive-out", str(archive), "--metadata-out", str(meta)]) == 1
        assert not archive.exists()
        assert not meta.exists()

    def test_existing_metadata_not_overwritten(self, monkeypatch, capsys, tmp_path):
        """Pre-existing metadata file is never touched."""
        spec = importlib.util.spec_from_file_location("dump_cli_r5_ex", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"
        meta.write_text("existing", encoding="utf-8")

        self._run_cli_with_real_orchestrator(monkeypatch, tmp_path)
        assert module.main(["--archive-out", str(archive), "--metadata-out", str(meta)]) == 1
        assert meta.read_text(encoding="utf-8") == "existing"
        assert not archive.exists()

    def test_no_staging_leftover_on_metadata_failure(self, monkeypatch, tmp_path):
        """After metadata promotion failure, no .meta_staging file remains."""
        spec = importlib.util.spec_from_file_location("dump_cli_r5_stg", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"
        meta.write_bytes(b"block")  # pre-existing to trigger promotion failure

        self._run_cli_with_real_orchestrator(monkeypatch, tmp_path)
        assert module.main(["--archive-out", str(archive), "--metadata-out", str(meta)]) == 1
        assert not any(p.suffix == ".meta_staging" for p in tmp_path.iterdir())

    def test_write_metadata_atomic_produces_correct_content(self, tmp_path):
        content = b'{"key": "value"}\n'
        dest = tmp_path / "meta.json"
        staging = sd.write_metadata_atomic(content, dest)
        assert staging.is_file()
        assert staging.read_bytes() == content
        assert staging != dest
        assert staging.parent == dest.parent
        staging.unlink()

    def test_exclusive_promote_metadata_no_clobber(self, tmp_path):
        staging = tmp_path / "meta.staging"
        staging.write_bytes(b"new-meta")
        dest = tmp_path / "meta.json"
        dest.write_bytes(b"old-meta")
        with pytest.raises(sd.SourceDumpError, match="promotion"):
            sd.exclusive_promote(staging, dest)
        assert dest.read_bytes() == b"old-meta"
        assert staging.exists()


# ===========================================================================
# R4/R5/R6 — CleanupResult helper
# ===========================================================================


class TestCleanupResult:
    def test_all_removed(self, tmp_path):
        f1, f2 = tmp_path / "a", tmp_path / "b"
        f1.write_bytes(b"x")
        f2.write_bytes(b"y")
        r = sd.cleanup_owned_artifacts([f1, f2])
        assert not r.incomplete
        assert not f1.exists() and not f2.exists()

    def test_missing_file_not_an_error(self, tmp_path):
        r = sd.cleanup_owned_artifacts([tmp_path / "nonexistent"])
        assert not r.incomplete

    def test_oserror_recorded_not_swallowed(self, tmp_path, monkeypatch):
        f = tmp_path / "locked"
        f.write_bytes(b"x")
        orig = Path.unlink

        def _fail(self, missing_ok=False):
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "unlink", _fail)
        r = sd.cleanup_owned_artifacts([f])
        assert r.incomplete
        assert "incomplete" in r.summary()
        assert "locked" in r.summary()

    def test_summary_contains_no_sensitive_data(self, tmp_path):
        f = tmp_path / "archive.dump"
        f.write_bytes(b"x")
        r = sd.cleanup_owned_artifacts([f])
        summary = r.summary()
        assert _PASSWORD not in summary and _HOST not in summary


# ===========================================================================
# F1 — Cleanup failure after successful hard-link publication
# ===========================================================================


class TestF1ExclusivePromoteCleanup:
    """exclusive_promote now returns CleanupResult; staging unlink failure must not be swallowed."""

    def test_success_path_returns_complete_result(self, tmp_path):
        staging = tmp_path / "staging"
        staging.write_bytes(b"data")
        dest = tmp_path / "dest.dump"
        result = sd.exclusive_promote(staging, dest)
        assert dest.read_bytes() == b"data"
        assert not staging.exists()
        assert not result.incomplete
        assert result.removed == ["staging"]
        assert result.failed == []

    def test_staging_unlink_failure_returns_incomplete(self, tmp_path, monkeypatch):
        staging = tmp_path / "staging"
        staging.write_bytes(b"data")
        dest = tmp_path / "dest.dump"

        orig_unlink = Path.unlink

        def _fail_staging(self, missing_ok=False):
            if self == staging:
                raise OSError("permission denied")
            orig_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _fail_staging)
        result = sd.exclusive_promote(staging, dest)

        # Destination is published and intact.
        assert dest.read_bytes() == b"data"
        # Staging still exists (unlink failed).
        assert staging.exists()
        # Result reports incomplete.
        assert result.incomplete
        assert "staging" in result.summary()
        # No credential leak in result.
        assert _PASSWORD not in result.summary() and _HOST not in result.summary()

    def test_destination_not_deleted_when_staging_unlink_fails(self, tmp_path, monkeypatch):
        """Destination must survive even if callers call cleanup_owned_artifacts after."""
        staging = tmp_path / "staging"
        staging.write_bytes(b"payload")
        dest = tmp_path / "dest.dump"

        orig_unlink = Path.unlink

        def _fail_staging(self, missing_ok=False):
            if self == staging:
                raise OSError("locked")
            orig_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _fail_staging)
        sd.exclusive_promote(staging, dest)

        # Simulate caller mistakenly passing dest to cleanup — must not delete it.
        # (This test documents the expected caller discipline; dest is NOT in owned[]
        # in the orchestrator after promotion, so this scenario cannot happen via
        # the orchestrator, but the test pins the invariant.)
        assert dest.is_file()

    def test_pre_link_failure_raises_source_dump_error_staging_intact(self, tmp_path):
        staging = tmp_path / "staging"
        staging.write_bytes(b"data")
        dest = tmp_path / "dest.dump"
        dest.write_bytes(b"existing")
        with pytest.raises(sd.SourceDumpError, match="promotion"):
            sd.exclusive_promote(staging, dest)
        assert dest.read_bytes() == b"existing"
        assert staging.exists()

    def test_orchestrator_raises_on_incomplete_archive_staging_cleanup(self, tmp_path, monkeypatch):
        """dump_source_snapshot raises SourceDumpError when archive staging unlink fails."""
        session = _Session()

        orig_unlink = Path.unlink

        def _fail_partial(self, missing_ok=False):
            partial = sd.partial_path_for(tmp_path / "source.dump")
            if self == partial:
                raise OSError("permission denied")
            orig_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _fail_partial)

        with pytest.raises(sd.SourceDumpError, match="staging cleanup incomplete"):
            _dump(tmp_path, session=session)

        # Destination archive must exist (was promoted).
        archive = tmp_path / "source.dump"
        assert archive.is_file()

    def test_orchestrator_error_contains_no_credentials(self, tmp_path, monkeypatch):
        session = _Session()

        orig_unlink = Path.unlink

        def _fail_partial(self, missing_ok=False):
            partial = sd.partial_path_for(tmp_path / "source.dump")
            if self == partial:
                raise OSError("permission denied")
            orig_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _fail_partial)

        try:
            _dump(tmp_path, session=session)
        except sd.SourceDumpError as exc:
            assert _PASSWORD not in str(exc) and _HOST not in str(exc)

    def test_cli_incomplete_metadata_staging_cleanup_returns_1_destinations_intact(
        self, monkeypatch, capsys, tmp_path
    ):
        """If metadata staging unlink fails after promotion, CLI returns 1; both archive and
        metadata are published and must not be removed."""
        spec = importlib.util.spec_from_file_location("dump_cli_f1_meta", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"

        import sqlalchemy, sqlalchemy.orm
        from app.core.config import settings

        monkeypatch.setattr(settings, "environment", "local")
        monkeypatch.setattr(settings, "db_name", sd.SOURCE_DATABASE_NAME)
        monkeypatch.setattr(settings, "db_password", _PASSWORD)
        monkeypatch.setattr(settings, "db_host", _HOST)

        sess = _Session()

        class _Engine:
            def dispose(self): pass

        class _SessionCtx:
            def __init__(self, *_a, **_k): pass
            def __enter__(self): return sess
            def __exit__(self, *_a): return False

        monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_a, **_k: _Engine())
        monkeypatch.setattr(sqlalchemy.orm, "Session", _SessionCtx)

        runner = _Runner(sess)
        real = sd.dump_source_snapshot

        def _with_fp(s, **kwargs):
            return real(s, runner=runner, compute_fingerprint=lambda _s: _fingerprint(), **kwargs)

        monkeypatch.setattr(sd, "dump_source_snapshot", _with_fp)

        # Intercept exclusive_promote to fail staging unlink only for the metadata staging.
        real_promote = sd.exclusive_promote

        def _failing_meta_cleanup(staging, destination):
            result = real_promote(staging, destination)
            if destination == meta:
                # Simulate unlink failure after successful link.
                return sd.CleanupResult(removed=[], failed=[staging.name])
            return result

        monkeypatch.setattr(sd, "exclusive_promote", _failing_meta_cleanup)

        rc = module.main(["--archive-out", str(archive), "--metadata-out", str(meta)])
        assert rc == 1
        # Both destinations must be present.
        assert archive.is_file()
        assert meta.is_file()
        # Error message must mention cleanup incomplete.
        err = capsys.readouterr().err
        assert "incomplete" in err
        assert _PASSWORD not in err and _HOST not in err


# ===========================================================================
# F2 — Staging cleanup inside write_metadata_atomic
# ===========================================================================


class TestF2WriteMetadataAtomic:
    """write_metadata_atomic must clean up its own staging on any write/flush/fsync/close failure."""

    def test_write_failure_cleans_staging_and_raises(self, tmp_path, monkeypatch):
        dest = tmp_path / "meta.json"
        import io

        orig_write = io.RawIOBase.write

        def _fail_write(self, data):
            raise OSError("disk full")

        # Monkeypatch the BufferedWriter write method.
        import builtins
        monkeypatch.setattr("builtins.open", builtins.open)  # ensure open is real

        # Intercept at the NamedTemporaryFile level via a wrapper.
        import tempfile as _tempfile
        orig_ntf = _tempfile.NamedTemporaryFile

        class _FailWriteNTF:
            def __init__(self, *a, **kw):
                self._real = orig_ntf(*a, **kw)
                self.name = self._real.name
            def write(self, data):
                raise OSError("disk full")
            def flush(self): pass
            def fileno(self): return self._real.fileno()
            def close(self): self._real.close()

        monkeypatch.setattr(_tempfile, "NamedTemporaryFile", lambda *a, **kw: _FailWriteNTF(*a, **kw))

        with pytest.raises(sd.SourceDumpError):
            sd.write_metadata_atomic(b"content", dest)

        # No staging file should remain.
        assert not any(p.suffix == ".meta_staging" for p in tmp_path.iterdir())
        # Destination was never written.
        assert not dest.exists()

    def test_fsync_failure_cleans_staging_and_raises(self, tmp_path, monkeypatch):
        dest = tmp_path / "meta.json"

        orig_fsync = os.fsync

        def _fail_fsync(fd):
            raise OSError("I/O error")

        monkeypatch.setattr(os, "fsync", _fail_fsync)

        with pytest.raises(sd.SourceDumpError):
            sd.write_metadata_atomic(b"content", dest)

        assert not any(p.suffix == ".meta_staging" for p in tmp_path.iterdir())
        assert not dest.exists()

    def test_flush_failure_cleans_staging_and_raises(self, tmp_path, monkeypatch):
        dest = tmp_path / "meta.json"
        import tempfile as _tempfile
        orig_ntf = _tempfile.NamedTemporaryFile

        class _FailFlushNTF:
            def __init__(self, *a, **kw):
                self._real = orig_ntf(*a, **kw)
                self.name = self._real.name
            def write(self, data):
                self._real.write(data)
            def flush(self):
                raise OSError("flush error")
            def fileno(self): return self._real.fileno()
            def close(self): self._real.close()

        monkeypatch.setattr(_tempfile, "NamedTemporaryFile", lambda *a, **kw: _FailFlushNTF(*a, **kw))

        with pytest.raises(sd.SourceDumpError):
            sd.write_metadata_atomic(b"content", dest)

        assert not any(p.suffix == ".meta_staging" for p in tmp_path.iterdir())

    def test_close_failure_after_successful_write_cleans_staging_and_raises(self, tmp_path, monkeypatch):
        dest = tmp_path / "meta.json"
        import tempfile as _tempfile
        orig_ntf = _tempfile.NamedTemporaryFile

        class _FailCloseNTF:
            def __init__(self, *a, **kw):
                self._real = orig_ntf(*a, **kw)
                self.name = self._real.name
            def write(self, data):
                self._real.write(data)
            def flush(self):
                self._real.flush()
            def fileno(self): return self._real.fileno()
            def close(self):
                self._real.close()
                raise OSError("close error")

        monkeypatch.setattr(_tempfile, "NamedTemporaryFile", lambda *a, **kw: _FailCloseNTF(*a, **kw))

        with pytest.raises(sd.SourceDumpError):
            sd.write_metadata_atomic(b"content", dest)

        assert not any(p.suffix == ".meta_staging" for p in tmp_path.iterdir())

    def test_staging_unlink_failure_raises_cleanup_incomplete(self, tmp_path, monkeypatch):
        dest = tmp_path / "meta.json"

        orig_fsync = os.fsync

        def _fail_fsync(fd):
            raise OSError("I/O error")

        monkeypatch.setattr(os, "fsync", _fail_fsync)

        orig_unlink = Path.unlink

        def _fail_unlink(self, missing_ok=False):
            if str(self).endswith(".meta_staging"):
                raise OSError("permission denied")
            orig_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _fail_unlink)

        with pytest.raises(sd.SourceDumpError, match="cleanup incomplete"):
            sd.write_metadata_atomic(b"content", dest)

        # Destination never written.
        assert not dest.exists()

    def test_success_path_staging_in_same_dir_content_correct(self, tmp_path):
        dest = tmp_path / "meta.json"
        content = b'{"schema_version": 1}\n'
        staging = sd.write_metadata_atomic(content, dest)
        assert staging.parent == dest.parent
        assert staging.read_bytes() == content
        assert staging != dest
        assert not dest.exists()
        staging.unlink()  # caller cleanup

    def test_f2_does_not_leak_credentials_in_error(self, tmp_path, monkeypatch):
        dest = tmp_path / "meta.json"

        def _fsync_with_cred_msg(fd):
            raise OSError(_PASSWORD)

        monkeypatch.setattr(os, "fsync", _fsync_with_cred_msg)
        with pytest.raises(sd.SourceDumpError) as exc_info:
            sd.write_metadata_atomic(b"x", dest)
        # SourceDumpError message must not contain the password from OSError.
        assert _PASSWORD not in str(exc_info.value)

    def test_cli_archive_removed_when_write_metadata_atomic_raises(self, monkeypatch, tmp_path):
        """If write_metadata_atomic raises SourceDumpError, archive is cleaned up."""
        spec = importlib.util.spec_from_file_location("dump_cli_f2_write", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"

        import sqlalchemy, sqlalchemy.orm
        from app.core.config import settings

        monkeypatch.setattr(settings, "environment", "local")
        monkeypatch.setattr(settings, "db_name", sd.SOURCE_DATABASE_NAME)
        monkeypatch.setattr(settings, "db_password", _PASSWORD)
        monkeypatch.setattr(settings, "db_host", _HOST)

        sess = _Session()

        class _Engine:
            def dispose(self): pass

        class _SessionCtx:
            def __init__(self, *_a, **_k): pass
            def __enter__(self): return sess
            def __exit__(self, *_a): return False

        monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_a, **_k: _Engine())
        monkeypatch.setattr(sqlalchemy.orm, "Session", _SessionCtx)

        runner = _Runner(sess)
        real = sd.dump_source_snapshot

        def _with_fp(s, **kwargs):
            return real(s, runner=runner, compute_fingerprint=lambda _s: _fingerprint(), **kwargs)

        monkeypatch.setattr(sd, "dump_source_snapshot", _with_fp)

        def _fail_write(content, destination):
            raise sd.SourceDumpError("Metadata staging write failed.")

        monkeypatch.setattr(sd, "write_metadata_atomic", _fail_write)

        rc = module.main(["--archive-out", str(archive), "--metadata-out", str(meta)])
        assert rc == 1
        # Archive must be removed since metadata was never published.
        assert not archive.exists()
        assert not meta.exists()


# ===========================================================================
# R6 residual — Metadata staging cleanup failure reported in finally block
# ===========================================================================


class TestR6ResidualMetadataStagingCleanup:
    """finally-path cleanup_owned_artifacts result was previously discarded.
    After the fix, CleanupResult.incomplete is checked and reported via _emit_error.
    """

    def _setup_cli(self, monkeypatch, tmp_path):
        """Load CLI module and wire fake DB/session/subprocess."""
        import sqlalchemy
        import sqlalchemy.orm
        from app.core.config import settings

        spec = importlib.util.spec_from_file_location("dump_cli_r6res", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        monkeypatch.setattr(settings, "environment", "local")
        monkeypatch.setattr(settings, "db_name", sd.SOURCE_DATABASE_NAME)
        monkeypatch.setattr(settings, "db_password", _PASSWORD)
        monkeypatch.setattr(settings, "db_host", _HOST)

        sess = _Session()

        class _Engine:
            def dispose(self): pass

        class _SessionCtx:
            def __init__(self, *_a, **_k): pass
            def __enter__(self): return sess
            def __exit__(self, *_a): return False

        monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_a, **_k: _Engine())
        monkeypatch.setattr(sqlalchemy.orm, "Session", _SessionCtx)

        runner = _Runner(sess)
        real_dump = sd.dump_source_snapshot

        def _with_fp(s, **kwargs):
            return real_dump(s, runner=runner, compute_fingerprint=lambda _s: _fingerprint(), **kwargs)

        monkeypatch.setattr(sd, "dump_source_snapshot", _with_fp)
        return module

    def _make_promote_fail_for_meta(self, meta: Path, monkeypatch):
        """Patch sd.exclusive_promote to succeed for archive (orchestrator) but
        raise SourceDumpError when the destination is the metadata path."""
        real_promote = sd.exclusive_promote

        def _selective_fail(staging, destination):
            if destination == meta:
                raise sd.SourceDumpError(
                    "Exclusive promotion failed: destination appeared after preflight check."
                )
            return real_promote(staging, destination)

        monkeypatch.setattr(sd, "exclusive_promote", _selective_fail)

    def test_staging_cleanup_failure_reported_in_stderr(self, monkeypatch, capsys, tmp_path):
        """When metadata exclusive_promote raises and meta_staging cleanup also raises OSError,
        stderr must contain 'cleanup incomplete' and the basename of the staging file.
        Exit code must be non-zero. Staging file must remain on disk (unlink failed).
        Archive must be removed (metadata was never published).
        Metadata destination must not exist (never promoted)."""
        module = self._setup_cli(monkeypatch, tmp_path)
        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"

        # Track the staging path created by write_metadata_atomic.
        real_wma = sd.write_metadata_atomic
        created_staging: list[Path] = []

        def _wma_track(content, destination):
            staging = real_wma(content, destination)
            created_staging.append(staging)
            return staging

        monkeypatch.setattr(sd, "write_metadata_atomic", _wma_track)

        # Fail exclusive_promote only for the metadata destination.
        self._make_promote_fail_for_meta(meta, monkeypatch)

        # Fail Path.unlink ONLY for the metadata staging path.
        orig_unlink = Path.unlink

        def _fail_staging_unlink(self, missing_ok=False):
            if created_staging and self == created_staging[0]:
                raise OSError("permission denied")
            orig_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _fail_staging_unlink)

        rc = module.main(["--archive-out", str(archive), "--metadata-out", str(meta)])

        assert rc == 1
        err = capsys.readouterr().err
        # Primary error must be present.
        assert "Metadata publication failed" in err
        # Cleanup incomplete must also be reported.
        assert "cleanup incomplete" in err
        # Basename of staging file must be mentioned.
        assert created_staging, "staging path was never captured"
        assert created_staging[0].name in err
        # No credentials leaked.
        assert _PASSWORD not in err and _HOST not in err
        # Staging file still exists on disk (unlink failed).
        assert created_staging[0].exists()
        # Metadata destination was never published.
        assert not meta.exists()
        # Archive removed (promotion failed before metadata was published).
        assert not archive.exists()

    def test_staging_cleanup_success_no_spurious_warning(self, monkeypatch, capsys, tmp_path):
        """When metadata exclusive_promote raises but staging cleanup succeeds,
        no 'cleanup incomplete' warning is emitted. Exit code is 1 (primary error)."""
        module = self._setup_cli(monkeypatch, tmp_path)
        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"

        # Fail exclusive_promote only for the metadata destination.
        self._make_promote_fail_for_meta(meta, monkeypatch)

        rc = module.main(["--archive-out", str(archive), "--metadata-out", str(meta)])

        assert rc == 1
        err = capsys.readouterr().err
        # Primary error present.
        assert "Metadata publication failed" in err
        # No spurious cleanup warning.
        assert "cleanup incomplete" not in err
        # No credentials.
        assert _PASSWORD not in err and _HOST not in err
        # No staging file remains.
        assert not any(p.suffix == ".meta_staging" for p in tmp_path.iterdir())

    def test_metadata_destination_not_touched_on_staging_cleanup_failure(
        self, monkeypatch, capsys, tmp_path
    ):
        """Pre-existing metadata destination must not be overwritten or deleted
        when staging cleanup fails after a failed promotion."""
        module = self._setup_cli(monkeypatch, tmp_path)
        archive = tmp_path / "src.dump"
        meta = tmp_path / "src.json"
        meta.write_bytes(b"pre-existing-meta")

        real_wma = sd.write_metadata_atomic
        created_staging: list[Path] = []

        def _wma_track(content, destination):
            staging = real_wma(content, destination)
            created_staging.append(staging)
            return staging

        monkeypatch.setattr(sd, "write_metadata_atomic", _wma_track)

        # Fail exclusive_promote only for the metadata destination.
        self._make_promote_fail_for_meta(meta, monkeypatch)

        orig_unlink = Path.unlink

        def _fail_staging_unlink(self, missing_ok=False):
            if created_staging and self == created_staging[0]:
                raise OSError("permission denied")
            orig_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _fail_staging_unlink)

        rc = module.main(["--archive-out", str(archive), "--metadata-out", str(meta)])

        assert rc == 1
        # Pre-existing metadata unchanged.
        assert meta.read_bytes() == b"pre-existing-meta"
