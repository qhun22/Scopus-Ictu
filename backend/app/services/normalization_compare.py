"""Before / after view of one publication's normalisation (read-only).

Shows, field by field, the value as it arrived in the imported CSV row (immutable), the value the
system stores, and the canonical form used for de-duplication and matching. Nothing is written:
the raw row is never changed, which is what lets a reviewer look back at the original at any time.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.publication import Publication, PublicationRawSource
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.lecturer_dataset.known_publication_ingestion import normalize_doi_n0
from app.services.normalization.scopus_normalizer import normalize_eid, normalize_title

Row = tuple[str, str | None, str | None, str | None]


@dataclass(frozen=True, slots=True)
class CompareField:
    field: str
    raw: str | None
    stored: str | None
    canonical: str | None
    # How the stored/canonical value differs from the raw one: SAME | CLEANED | CHANGED | MISSING
    status: str


@dataclass(frozen=True, slots=True)
class CompareSource:
    file_name: str
    row_number: int
    row_hash: str


@dataclass(frozen=True, slots=True)
class NormalizationCompare:
    eid: str
    sources: tuple[CompareSource, ...]
    fields: tuple[CompareField, ...]


def _text(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value)
    return rendered if rendered.strip() else None


def _status(raw: str | None, stored: str | None, canonical: str | None) -> str:
    """MISSING (nothing), CHANGED (stored differs from the raw text and is not its canonical form),
    CLEANED (the raw text and its canonical form differ, e.g. a DOI URL or letter case, whether
    the stored value is already canonical or still as received), else SAME."""

    if raw is None and stored is None:
        return "MISSING"
    if (raw or "").strip() != (stored or ""):
        return "CLEANED" if canonical is not None and canonical == stored else "CHANGED"
    if canonical is not None and canonical != (stored or ""):
        return "CLEANED"
    return "SAME"


def build_compare(db: Session, eid: str) -> NormalizationCompare | None:
    publication = db.scalar(select(Publication).where(Publication.eid == eid))
    if publication is None:
        return None
    rows = db.execute(
        select(RawScopusRecord, ScopusImport.file_name)
        .join(PublicationRawSource, PublicationRawSource.raw_record_id == RawScopusRecord.id)
        .join(ScopusImport, ScopusImport.id == RawScopusRecord.import_id)
        .where(PublicationRawSource.publication_id == publication.id)
        .order_by(RawScopusRecord.created_at.asc())
    ).all()
    sources = tuple(
        CompareSource(file_name=name, row_number=rec.row_number, row_hash=rec.row_hash)
        for rec, name in rows
    )
    payload: dict = rows[0][0].raw_payload if rows else {}

    def raw(header: str) -> str | None:
        return _text(payload.get(header))

    def same(name: str, header: str, stored: object) -> Row:
        # Stored as received; the canonical form is the stored value itself.
        return name, raw(header), _text(stored), _text(stored)

    candidates = [
        ("eid", raw("EID"), publication.eid, normalize_eid(raw("EID")) or publication.eid),
        ("doi", raw("DOI"), _text(publication.doi), normalize_doi_n0(raw("DOI"))),
        ("title", raw("Title"), _text(publication.title), normalize_title(raw("Title"))),
        same("source_title", "Source title", publication.source_title),
        same("year", "Year", publication.year),
        same("document_type", "Document Type", publication.document_type),
        same("cited_by_count", "Cited by", publication.cited_by_count),
    ]
    fields = tuple(
        CompareField(name, r, stored, canonical, _status(r, stored, canonical))
        for name, r, stored, canonical in candidates
    )
    return NormalizationCompare(publication.eid, sources, fields)
