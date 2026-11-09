"""Backfill ``publications.doi`` to its canonical DOI_N0 form.

Publications created before this revision kept the DOI as received from Scopus
(only trimmed). New ones are stored canonical, so this rewrites the old rows to
match: NFKC, trim, lower-case, recognized resolver prefix removed. Data only;
no schema change.

``raw_scopus_records`` is not touched, so the DOI exactly as Scopus sent it stays
available. For that reason ``downgrade`` is a no-op: the canonical form is the
same DOI, and the original spelling is not a single value when several imports
supplied the same publication.

The normalization is a frozen copy on purpose: a migration must keep meaning
what it meant when published, even if the application rule changes later.

Revision ID: b3d91f4c7a20, revises 15c7b721214c. Not applied to any database
by this change.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3d91f4c7a20"
down_revision: str | None = "15c7b721214c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def _canonical_doi(value: str) -> str | None:
    text = unicodedata.normalize("NFKC", value).strip()
    lowered = text.lower()
    for prefix in _DOI_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    return unicodedata.normalize("NFKC", text).strip().lower() or None


def upgrade() -> None:
    bind = op.get_bind()
    publications = sa.table("publications", sa.column("id"), sa.column("doi", sa.String))
    rows = bind.execute(
        sa.select(publications.c.id, publications.c.doi).where(publications.c.doi.is_not(None))
    ).all()
    for row in rows:
        canonical = _canonical_doi(row.doi)
        if canonical != row.doi:
            bind.execute(
                sa.update(publications)
                .where(publications.c.id == row.id)
                .values(doi=canonical)
            )


def downgrade() -> None:
    """No-op: see the module docstring."""
