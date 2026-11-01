"""E3-P3-B1: explicit source-claim evidence and non-reviewable staged runs.

Revision ID: b88f02d44ff2. Revises: a77e01c33ee1.
Source only; execution requires a separately authorized migration deployment.
"""

from alembic import op

revision = "b88f02d44ff2"
down_revision = "a77e01c33ee1"
branch_labels = None
depends_on = None

EVIDENCE = "lecturer_scopus_candidate_evidence"
RUNS = "candidate_generation_runs"


def _checks(source_claims: bool) -> None:
    kinds = "'NAME', 'PUBLICATION'" + (", 'SOURCE_CLAIM'" if source_claims else "")
    terminal = "'COMPLETED', 'FAILED'" + (", 'STAGED'" if source_claims else "")
    for table, name, expression in (
        (EVIDENCE, "evidence_kind", f"evidence_kind IN ({kinds})"),
        (RUNS, "status", f"status IN ('RUNNING', {terminal})"),
        (RUNS, "completion_consistency",
         "(status = 'RUNNING' AND completed_at IS NULL) OR "
         f"(status IN ({terminal}) AND completed_at IS NOT NULL)"),
    ):
        constraint = op.f(f"ck_{table}_{name}")
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(constraint, table, expression)


def upgrade() -> None:
    _checks(True)


def downgrade() -> None:
    # Existing SOURCE_CLAIM/STAGED data makes the old checks fail. Intentionally
    # fail closed instead of deleting history or making it reviewable.
    _checks(False)
