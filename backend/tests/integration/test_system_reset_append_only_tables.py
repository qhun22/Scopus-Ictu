"""System reset must still wipe everything when append-only guard triggers exist.

Reproduces the 500 from POST /system/reset: TRUNCATE ... CASCADE reaches append-only
history tables (lecturer_publication_exclusion_events here) whose BEFORE TRUNCATE guard
refuses it. The reset lifts the guard inside its own transaction and re-arms it.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.system import reset_system
from app.models.base import Base
from app.models.governance import User
from app.models.publication_exclusion import LecturerPublicationExclusionEvent
from tests.db_safety_guard import assert_safe_for_destructive_test

MIGRATION = (Path(__file__).resolve().parents[2] / "alembic" / "versions"
             / "e4a1b7c92d10_g09_lecturer_publication_exclusions.py")


@pytest.fixture
def schema_session(isolated_db_engine):
    if isolated_db_engine is None:
        pytest.skip("No isolated PostgreSQL test database available.")
    schema = f"reset_{uuid.uuid4().hex}"
    with isolated_db_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(isolated_db_engine.url, future=True, connect_args={
        "options": f"-csearch_path={schema} -cstatement_timeout=30000"})
    try:
        Base.metadata.create_all(bind=engine, tables=[
            t for n, t in Base.metadata.tables.items()
            if n != LecturerPublicationExclusionEvent.__tablename__])
        spec = importlib.util.spec_from_file_location("reset_mig", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(
                    conn, opts={"target_metadata": Base.metadata})):
                module.upgrade()                      # real table + real append-only guards
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()
        assert_safe_for_destructive_test(isolated_db_engine)
        with isolated_db_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def _seed(db):
    admin_id, user_id, lecturer_id, pub_id = (uuid.uuid4() for _ in range(4))
    for uid, role in ((admin_id, "ADMIN"), (user_id, "REVIEWER")):
        db.add(User(id=uid, email=f"{uid.hex}@test.local", password_hash="x" * 40,
                    display_name=role, role=role, is_active=True, version=1, auth_version=1))
    db.execute(text("INSERT INTO lecturers (id, full_name, full_name_normalized, version) "
                    "VALUES (:i, 'L', 'l', 1)"), {"i": lecturer_id})
    db.execute(text("INSERT INTO publications (id, eid, title, title_normalized) "
                    "VALUES (:i, 'EID-RESET', 't', 't')"), {"i": pub_id})
    db.flush()
    db.execute(text(
        "INSERT INTO lecturer_publication_exclusion_events (lecturer_id, publication_id, "
        "action, reason, acted_by_user_id) VALUES (:l, :p, 'EXCLUDE', 'r', :u)"),
        {"l": lecturer_id, "p": pub_id, "u": admin_id})
    db.commit()
    return admin_id


def test_reset_wipes_append_only_history_and_re_arms_the_guard(schema_session):
    with schema_session() as db:
        admin_id = _seed(db)
        admin = db.get(User, admin_id)
        result = reset_system("ICTU", db=db, _actor=admin)
        assert result["status"] == "ok"
        assert db.execute(text(
            "SELECT count(*) FROM lecturer_publication_exclusion_events")).scalar_one() == 0
        assert db.execute(text("SELECT count(*) FROM publications")).scalar_one() == 0
        assert [r[0] for r in db.execute(text("SELECT role FROM users")).all()] == ["ADMIN"]
        # The guard is armed again after the reset (ENABLE ALWAYS = 'A').
        assert db.execute(text(
            "SELECT tgenabled FROM pg_trigger WHERE tgname = 'lpee_forbid_truncate'"
        )).scalar_one() == "A"
        with pytest.raises(DatabaseError, match="append-only"):
            db.execute(text("TRUNCATE lecturer_publication_exclusion_events"))
        db.rollback()
