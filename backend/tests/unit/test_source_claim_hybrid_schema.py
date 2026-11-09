"""B2-D schema and migration structure, rendered offline against the PostgreSQL dialect.

No database is touched and the migration is never executed: ``as_sql`` rendering only.
The DB-level CHECK and FK behaviour these constraints declare is therefore NOT_EXECUTED
here — that needs a real PostgreSQL run.
"""

from __future__ import annotations

import importlib.util
import io
import re
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base
from app.models.source_claim_hybrid import HYBRID_TABLES

BACKEND = Path(__file__).resolve().parents[2]
VERSIONS = BACKEND / "alembic" / "versions"
MIGRATION = VERSIONS / "c99a03e55ff3_e3_p3b2d_source_claim_hybrid_history.py"
PG = postgresql.dialect()
FROZEN = ("lecturer_scopus_candidates", "lecturer_scopus_candidate_evidence",
          "lecturer_scopus_candidate_reviews", "lecturer_scopus_identities",
          "identity_evidence", "mapping_reviews", "audit_events", "users",
          "candidate_generation_runs", "source_artifacts", "source_claims")


def _module():
    spec = importlib.util.spec_from_file_location("e3_p3b2d", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render(step: str) -> str:
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer, "target_metadata": Base.metadata})
    with Operations.context(context):
        getattr(_module(), step)()
    return buffer.getvalue()


def _blocks(sql: str, prefix: str) -> dict[str, str]:
    blocks = {}
    for statement in sql.split(";"):
        text = statement.strip()
        if not text.upper().startswith(prefix):
            continue
        name = text[len(prefix):].strip().split()[0].split("(")[0]
        blocks[name] = text
    return blocks


def _items(create_table_sql: str) -> set[str]:
    body = create_table_sql[create_table_sql.index("(") + 1: create_table_sql.rindex(")")]
    items, depth, current = [], 0, ""
    for char in body:
        if char == "," and depth == 0:
            items.append(current)
            current = ""
            continue
        depth += (char == "(") - (char == ")")
        current += char
    items.append(current)
    return {" ".join(item.split()) for item in items if item.strip()}


HARDENING = VERSIONS / "d0b14a77c8e2_e3_p3b2e_hybrid_history_hardening.py"
# Everything migration d0b14a77c8e2 adds to the B2-D tables, as it appears in the models.
HARDENING_ITEMS = {
    "sc_hybrid_contexts": ("uq_sc_hybrid_contexts_candidate_policy",),
    "sc_hybrid_events": ("previous_stream_seq", "uq_sc_hybrid_events_chain_link",
                         "fk_sc_hybrid_events_chain_link",
                         "fk_sc_hybrid_events_context_candidate_policy"),
}


def test_c99_is_still_the_accepted_b2d_revision_and_the_hardening_sits_on_top():
    module = _module()
    assert (module.revision, module.down_revision) == ("c99a03e55ff3", "b88f02d44ff2")
    spec = importlib.util.spec_from_file_location("e3_p3b2e", HARDENING)
    hardening = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hardening)
    assert (hardening.revision, hardening.down_revision) == ("d0b14a77c8e2", "c99a03e55ff3")


def test_migration_is_the_single_new_head_on_top_of_the_accepted_one():
    module = _module()
    assert (module.revision, module.down_revision) == ("c99a03e55ff3", "b88f02d44ff2")
    revisions, downs = set(), set()
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        found = re.search(r'^revision(?::[^=]+)?\s*=\s*"([^"]+)"', text, re.M)
        down = re.search(r"^down_revision(?::[^=]+)?\s*=\s*(.+)$", text, re.M)
        if found:
            revisions.add(found.group(1))
        if down:
            downs.update(re.findall(r'"([^"]+)"', down.group(1)))
    # The chain keeps growing (B2-E hardening d0b14a77c8e2, G09 e4a1b7c92d10, main-ID label
    # f2b8c3d19a47, feedback reports d4e7c3a98f12, feedback report seen 15c7b721214c,
    # canonical publication DOI b3d91f4c7a20, users.avatar_url c4f1a7e9d203,
    # users.has_password/google_linked e8b2c6a94f17); the
    # published revisions below the head are never rewritten.
    assert revisions - downs == {"e8b2c6a94f17"}, "exactly one head"
    assert {"e4a1b7c92d10", "d0b14a77c8e2", "c99a03e55ff3", "b88f02d44ff2"} <= downs


def test_migration_tables_match_the_models_item_by_item():
    """c99a03e55ff3 plus exactly the items d0b14a77c8e2 adds equal the models."""
    rendered = _blocks(_render("upgrade"), "CREATE TABLE")
    assert set(rendered) == set(HYBRID_TABLES)
    for name in HYBRID_TABLES:
        model_sql = str(CreateTable(Base.metadata.tables[name]).compile(dialect=PG))
        added = HARDENING_ITEMS.get(name, ())
        model_items = _items(model_sql)
        hardening = {item for item in model_items if any(token in item for token in added)}
        assert all(any(token in item for item in hardening) for token in added), name
        assert _items(rendered[name]) == model_items - hardening, name


def test_migration_indexes_match_the_models():
    rendered = _blocks(_render("upgrade"), "CREATE INDEX")
    expected = {}
    for name in HYBRID_TABLES:
        for index in Base.metadata.tables[name].indexes:
            expected[index.name] = " ".join(
                str(CreateIndex(index).compile(dialect=PG)).split())
    assert set(rendered) == set(expected)
    for name, sql in expected.items():
        assert " ".join(rendered[name].split()) == sql


def test_the_migration_only_adds_and_never_touches_a_frozen_table():
    sql = _render("upgrade").upper()
    assert "ALTER TABLE" not in sql and "DROP " not in sql
    for table in FROZEN:
        # A frozen table may be referenced by a new FK, but never redefined.
        assert f"CREATE TABLE {table.upper()}" not in sql


def test_the_new_tables_add_no_foreign_key_into_the_staging_contract():
    """E3-P2-B1 keeps staging pre-identity with nothing downstream pointing into it.

    B2-D does not reopen that contract: lineage is revalidated by the append boundary
    and pinned by the stored digests instead of by a referential constraint.
    """
    staging = {n for n in Base.metadata.tables if n.startswith("source_")}
    for name in HYBRID_TABLES:
        for fk in Base.metadata.tables[name].foreign_keys:
            assert fk.column.table.name not in staging, (name, fk.target_fullname)


def test_no_finalization_or_identity_relation_is_introduced():
    """The schema has no place to put an acceptance, by construction."""
    names = " ".join(HYBRID_TABLES)
    assert "final" not in names and "identit" not in names
    columns = {c.name for t in HYBRID_TABLES for c in Base.metadata.tables[t].columns}
    assert not {"identity_id", "finalization_id", "candidate_review_id",
                "mapping_review_id", "resulting_identity_id"} & columns


@pytest.mark.parametrize(("table", "constraint"), [
    # The invariants that must be enforced by the database, not only by the service.
    ("sc_hybrid_provenance", "ck_sc_hybrid_provenance_never_independent"),
    ("sc_hybrid_events", "uq_sc_hybrid_events_operation_key"),
    ("sc_hybrid_events", "uq_sc_hybrid_events_previous_event_id"),
    ("sc_hybrid_events", "uq_sc_hybrid_events_stream"),
    ("sc_hybrid_events", "ck_sc_hybrid_events_snapshot_hash_matches"),
    ("sc_hybrid_events", "ck_sc_hybrid_events_envelope_hash_matches"),
    ("sc_hybrid_events", "ck_sc_hybrid_events_chain_head_consistency"),
    ("sc_hybrid_events", "ck_sc_hybrid_events_human_action_required"),
    ("sc_hybrid_proposals", "uq_sc_hybrid_proposals_context_id"),
    ("sc_hybrid_proposals", "ck_sc_hybrid_proposals_branch_assurance_consistency"),
    ("sc_hybrid_approvals", "uq_sc_hybrid_approvals_proposal_id"),
    ("sc_hybrid_approvals", "ck_sc_hybrid_approvals_distinct_accounts"),
    ("sc_hybrid_approvals", "ck_sc_hybrid_approvals_distinct_human_principals"),
    ("sc_hybrid_approvals", "fk_sc_hybrid_approvals_proposal_binding"),
    ("sc_hybrid_revocations", "uq_sc_hybrid_revocations_target_event_id"),
    ("sc_hybrid_revocations", "ck_sc_hybrid_revocations_distinct_human_principals"),
    ("sc_hybrid_policies", "ck_sc_hybrid_policies_policy_digest_matches"),
])
def test_security_invariants_are_declared_in_the_schema(table, constraint):
    declared = {c.name for c in Base.metadata.tables[table].constraints}
    assert constraint in declared
    assert constraint in _render("upgrade")


def test_downgrade_refuses_to_drop_recorded_history():
    sql = _render("downgrade")
    for table in HYBRID_TABLES:
        assert f"refusing to drop {table}" in sql
        assert f"DROP TABLE {table}" in sql


def test_every_new_constraint_name_fits_postgresql_identifier_limits():
    for name in HYBRID_TABLES:
        table = Base.metadata.tables[name]
        assert len(name) <= 63
        for constraint in table.constraints:
            assert constraint.name is None or len(str(constraint.name)) <= 63
        for index in table.indexes:
            assert len(index.name) <= 63
