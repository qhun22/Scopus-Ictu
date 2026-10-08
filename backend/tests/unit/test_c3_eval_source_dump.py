"""Unit tests for the C3 evaluation source-snapshot dump orchestrator (C3-A3 P1).

Mocks only: fake session, fake subprocess runner.  pg_dump / pg_restore are
never executed and no database is contacted.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
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
        for path in (Path(inspect.getsourcefile(sd)), _SCRIPT):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Attribute):
                    assert node.attr not in {"commit", "add", "add_all", "flush", "delete", "merge"}
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
