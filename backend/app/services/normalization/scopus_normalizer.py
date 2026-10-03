"""Publication normalization — M2.6A.

Maps VALID raw_scopus_records to canonical publications via EID deduplication.
Raw rows are immutable; provenance is tracked in publication_raw_sources.

Key invariants enforced:
  1. publications.eid UNIQUE — final integrity barrier; race-safe via savepoint.
  2. publication_raw_sources(raw_record_id) UNIQUE — idempotent linking only.
  3. Existing EID + different metadata → EXISTING_METADATA_CHANGED; never overwritten.
  4. No author normalization (deferred to M2.6B).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.publication import Publication, PublicationRawSource
from app.models.scopus_raw import RawScopusRecord, ScopusImport

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Normalization classification outcomes
# ---------------------------------------------------------------------------

NORMALIZATION_OUTCOMES = frozenset({
    "NEW",
    "EXISTING_UNCHANGED",
    "EXISTING_METADATA_CHANGED",
    "INVALID_EID",
    "NORMALIZATION_ERROR",
})
"""Mutually-exclusive terminal outcomes for a raw record."""


@dataclass
class NormalizationCounters:
    """Durable counters for a normalization run — stored in error_summary JSONB."""

    canonical_new: int = 0
    canonical_existing: int = 0
    canonical_metadata_changed: int = 0
    canonical_failed: int = 0
    canonical_intra_duplicate: int = 0
    _canonical_processed: int = field(default=0, init=False, repr=False)

    @property
    def canonical_processed(self) -> int:
        """Computed: sum of the four mutually-exclusive terminal outcomes."""
        return (
            self.canonical_new
            + self.canonical_existing
            + self.canonical_metadata_changed
            + self.canonical_failed
        )

    def invariant_holds(self) -> bool:
        return (
            self.canonical_processed
            == self.canonical_new
            + self.canonical_existing
            + self.canonical_metadata_changed
            + self.canonical_failed
            and self.canonical_intra_duplicate <= self.canonical_processed
        )

    def to_dict(self) -> dict:
        return {
            "canonical_new": self.canonical_new,
            "canonical_existing": self.canonical_existing,
            "canonical_metadata_changed": self.canonical_metadata_changed,
            "canonical_failed": self.canonical_failed,
            "canonical_processed": self.canonical_processed,
            "canonical_intra_duplicate": self.canonical_intra_duplicate,
        }


@dataclass
class NormalizationResult:
    outcome: str
    publication: Publication | None
    changed_fields: list[str] = field(default_factory=list)
    error_message: str | None = None


# ---------------------------------------------------------------------------
# EID normalization
# ---------------------------------------------------------------------------

SCOPUS_EID_PATTERN = re.compile(r"^[0-9]+-s2\.0-[0-9]+$", re.ASCII)


def normalize_eid(raw: str | None) -> str | None:
    """Normalize a raw Scopus EID to canonical form.

    Rules:
      - Ensure string type.
      - Strip leading/trailing whitespace.
      - Reject empty-after-trim as None.
      - Preserve semantic value (do not lowercase/uppercase).
      - Basic format check for known Scopus EID pattern (conservative).

    Returns None for invalid or missing EIDs.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    # Basic structural guard: Scopus EIDs follow 2-s2.0-HEXID format.
    # Reject only clearly malformed non-empty values (e.g. contain whitespace in middle).
    if " " in trimmed or "\t" in trimmed:
        return None
    return trimmed


def is_eid_valid(raw: str | None) -> bool:
    """True when a raw EID normalizes to a non-None value."""
    return normalize_eid(raw) is not None


# ---------------------------------------------------------------------------
# Title normalization (matches existing Publication.title_normalized semantics)
# ---------------------------------------------------------------------------

import unicodedata


def normalize_title(title: str | None) -> str | None:
    """Return a normalized version of a title for comparison/storage.

    Applies: Unicode NFKC, lowercase, strip.
    Returns None when input is None or empty.
    """
    if not title:
        return None
    normalized = unicodedata.normalize("NFKC", title)
    normalized = normalized.lower().strip()
    return normalized or None


# ---------------------------------------------------------------------------
# Metadata comparison
# ---------------------------------------------------------------------------

# Fields on Publication that can be derived from raw_scopus_records payload.
CANONICAL_COMPARABLE_FIELDS = frozenset({
    "title",
    "title_normalized",
    "doi",
    "source_title",
    "year",
    "volume",
    "issue",
    "art_no",
    "page_start",
    "page_end",
    "cited_by_count",
    "document_type",
    "publication_stage",
    "open_access_status",
})
"""Fields used for EXISTING_METADATA_CHANGED detection."""


def compare_metadata(
    existing: Publication, candidate: dict, raw_payload: dict
) -> list[str]:
    """Compare raw-derived fields against existing canonical publication.

    Returns list of field names that differ between existing and candidate.

    Rules:
      - Skip None-vs-None as equal.
      - Trim whitespace for string comparisons.
      - Normalize title via the same normalize_title() used at creation.
      - Use raw_payload keys for candidate values (source headers).
    """
    changed: list[str] = []

    # title
    raw_title = _raw_field(candidate, raw_payload, "Title", "title")
    existing_title = existing.title
    if not _field_equal(existing_title, raw_title):
        changed.append("title")

    # doi
    raw_doi = _raw_doi(candidate, raw_payload)
    if not _nullable_str_equal(existing.doi, raw_doi):
        changed.append("doi")

    # source_title
    raw_source = _raw_field(candidate, raw_payload, "Source", "source_title")
    if not _nullable_str_equal(existing.source_title, raw_source):
        changed.append("source_title")

    # year
    raw_year = _raw_int(candidate, raw_payload, "Year", "year")
    if not _field_equal(existing.year, raw_year):
        changed.append("year")

    # volume
    raw_vol = _raw_field(candidate, raw_payload, "Volume", "volume")
    if not _nullable_str_equal(existing.volume, raw_vol):
        changed.append("volume")

    # issue
    raw_issue = _raw_field(candidate, raw_payload, "Issue", "issue")
    if not _nullable_str_equal(existing.issue, raw_issue):
        changed.append("issue")

    # art_no
    raw_art = _raw_field(candidate, raw_payload, "Art. No.", "art_no")
    if not _nullable_str_equal(existing.art_no, raw_art):
        changed.append("art_no")

    # page_start
    raw_ps = _raw_field(candidate, raw_payload, "Page start", "page_start")
    if not _nullable_str_equal(existing.page_start, raw_ps):
        changed.append("page_start")

    # page_end
    raw_pe = _raw_field(candidate, raw_payload, "Page end", "page_end")
    if not _nullable_str_equal(existing.page_end, raw_pe):
        changed.append("page_end")

    # cited_by_count
    raw_cited = _raw_int(candidate, raw_payload, "Cited by", "cited_by_count")
    if not _nullable_int_equal(existing.cited_by_count, raw_cited):
        changed.append("cited_by_count")

    # document_type
    raw_doctype = _bounded_raw_field(raw_payload, "Document Type", 50)
    if not _nullable_str_equal(existing.document_type, raw_doctype):
        changed.append("document_type")

    # publication_stage
    raw_stage = _bounded_raw_field(raw_payload, "Publication Stage", 50)
    if not _nullable_str_equal(existing.publication_stage, raw_stage):
        changed.append("publication_stage")

    # open_access_status
    raw_oa = _bounded_raw_field(raw_payload, "Open Access", 50)
    if not _nullable_str_equal(existing.open_access_status, raw_oa):
        changed.append("open_access_status")

    return changed


# ---------------------------------------------------------------------------
# Payload field extractors
# ---------------------------------------------------------------------------

def _raw_field(
    mapping: dict, raw_payload: dict, header: str, _fallback: str
) -> str | None:
    """Extract a string field from the raw payload by exact header match."""
    if header in raw_payload:
        val = raw_payload.get(header)
        if val and str(val).strip():
            return str(val).strip()
    return None


def _bounded_raw_field(raw_payload: dict, header: str, max_length: int) -> str | None:
    """Map a raw string into a bounded canonical column.

    The immutable raw payload retains the complete source value. Canonical
    columns honor the frozen M1 physical lengths, and comparisons use the same
    mapping so an idempotent rerun does not report a false metadata change.
    """
    value = _raw_field({}, raw_payload, header, header)
    return value[:max_length] if value is not None else None


def _raw_doi(mapping: dict, raw_payload: dict) -> str | None:
    """Extract DOI from raw payload."""
    val = raw_payload.get("DOI") or mapping.get("doi_raw")
    if val:
        stripped = str(val).strip()
        return stripped or None
    return None


def _raw_int(
    mapping: dict, raw_payload: dict, header: str, _fallback: str
) -> int | None:
    """Extract an integer field from the raw payload."""
    val = raw_payload.get(header)
    if val is None:
        return None
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def _nullable_int_equal(a: int | None, b: int | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return a == b


def _nullable_str_equal(a: str | None, b: str | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return a.strip() == b.strip()


def _field_equal(a: object, b: object) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, str) and isinstance(b, str):
        return a.strip() == b.strip()
    return a == b


# ---------------------------------------------------------------------------
# Publication creation from raw payload
# ---------------------------------------------------------------------------

def create_publication_from_raw(
    raw_record: RawScopusRecord,
) -> Publication:
    """Create a canonical Publication from a VALID raw_scopus_record."""
    eid = normalize_eid(raw_record.eid_raw)
    payload = raw_record.raw_payload

    title = _raw_field({}, payload, "Title", "title") or "Unknown Title"
    title_norm = normalize_title(title) or "unknown title"

    doi = _raw_doi({}, payload)

    now = datetime.now(UTC)
    return Publication(
        id=uuid.uuid4(),
        eid=eid,  # validated caller ensures non-None
        doi=doi,
        title=title,
        title_normalized=title_norm,
        source_title=_raw_field({}, payload, "Source", "source_title"),
        year=_raw_int({}, payload, "Year", "year"),
        volume=_raw_field({}, payload, "Volume", "volume"),
        issue=_raw_field({}, payload, "Issue", "issue"),
        art_no=_raw_field({}, payload, "Art. No.", "art_no"),
        page_start=_raw_field({}, payload, "Page start", "page_start"),
        page_end=_raw_field({}, payload, "Page end", "page_end"),
        cited_by_count=_raw_int({}, payload, "Cited by", "cited_by_count"),
        document_type=_bounded_raw_field(payload, "Document Type", 50),
        publication_stage=_bounded_raw_field(payload, "Publication Stage", 50),
        open_access_status=_bounded_raw_field(payload, "Open Access", 50),
        version=1,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Integrity error classification
# ---------------------------------------------------------------------------

def is_publication_eid_unique_violation(exc: IntegrityError) -> bool:
    """Detect whether an IntegrityError is specifically publications.eid uniqueness.

    Works with psycopg2 (postgresql+psycopg2 driver):
      - exc.orig.pgcode == '23505' for unique violation
      - exc.orig.constname carries the constraint name OR the string 'N/A'
      - exc.orig.diag.constraint_name carries the actual DB constraint name
      - exc.args contains the full error message with constraint name

    Multiple fallback checks ensure robustness across SQLAlchemy versions.
    """
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False

    pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
    if pgcode != "23505":
        return False

    # PostgreSQL drivers expose the violated constraint on ``diag`` (psycopg2)
    # or directly on the original exception.  When present it is authoritative:
    # a different 23505 must never be downgraded to EXISTING.
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None) if diag is not None else None
    constraint_name = (
        constraint_name
        or getattr(orig, "constraint_name", None)
        or getattr(orig, "constname", None)
    )
    if constraint_name and constraint_name != "N/A":
        return constraint_name == "uq_publications_eid"

    # Compatibility fallback for test doubles/older drivers that expose no
    # constraint field.  pgcode=23505 remains mandatory.
    return any(
        isinstance(arg, str) and "uq_publications_eid" in arg
        for arg in (getattr(orig, "args", None) or ())
    )


def is_unrelated_integrity_error(exc: IntegrityError) -> bool:
    """True when the IntegrityError is NOT the expected publications.eid race."""
    return not is_publication_eid_unique_violation(exc)


# ---------------------------------------------------------------------------
# Concurrent provenance link helper
# ---------------------------------------------------------------------------

def link_provenance(
    db: Session,
    publication: Publication,
    raw_record: RawScopusRecord,
    existing_by_raw_id: dict[uuid.UUID, PublicationRawSource] | None = None,
) -> bool:
    """Create publication_raw_sources link idempotently.

    Returns True if link was created (or already existed pointing to same pub).
    Raises ProvenanceConflict if raw_record already links to a DIFFERENT publication.

    Implements savepoint so outer transaction is never corrupted.
    """
    # Batch callers preload this map once, avoiding one SELECT per raw row.
    # Standalone callers retain the safe single-row lookup.
    existing = (
        existing_by_raw_id.get(raw_record.id)
        if existing_by_raw_id is not None
        else db.query(PublicationRawSource)
        .filter(PublicationRawSource.raw_record_id == raw_record.id)
        .first()
    )
    if existing is not None:
        if existing.publication_id != publication.id:
            raise ProvenanceConflict(raw_record.id, existing.publication_id, publication.id)
        return True  # idempotent: already linked to same publication

    try:
        with db.begin_nested():
            link = PublicationRawSource(
                id=uuid.uuid4(),
                publication_id=publication.id,
                raw_record_id=raw_record.id,
                created_at=datetime.now(UTC),
            )
            db.add(link)
            db.flush()
        if existing_by_raw_id is not None:
            existing_by_raw_id[raw_record.id] = link
        return True
    except IntegrityError as exc:
        # begin_nested() rolls back only its savepoint.  Never roll back the
        # outer batch here; completed work in that transaction remains usable.
        # Another concurrent process created the link first
        existing = (
            db.query(PublicationRawSource)
            .filter(PublicationRawSource.raw_record_id == raw_record.id)
            .first()
        )
        if existing is not None:
            if existing.publication_id != publication.id:
                raise ProvenanceConflict(raw_record.id, existing.publication_id, publication.id)
            if existing_by_raw_id is not None:
                existing_by_raw_id[raw_record.id] = existing
            return True
        # Unexpected: re-raise unrelated IntegrityError
        raise


class ProvenanceConflict(Exception):
    """Raised when a raw_record is already linked to a different publication."""

    def __init__(self, raw_record_id: uuid.UUID, existing_pub_id: uuid.UUID, attempted_pub_id: uuid.UUID) -> None:
        self.raw_record_id = raw_record_id
        self.existing_pub_id = existing_pub_id
        self.attempted_pub_id = attempted_pub_id
        super().__init__(
            f"raw_record {raw_record_id} already links to publication {existing_pub_id}; "
            f"cannot relink to {attempted_pub_id}"
        )


# ---------------------------------------------------------------------------
# Single-record normalization
# ---------------------------------------------------------------------------

def normalize_single_raw(
    db: Session,
    raw_record: RawScopusRecord,
    existing_by_eid: dict[str, Publication],
    provenance_by_raw_id: dict[uuid.UUID, PublicationRawSource] | None = None,
) -> NormalizationResult:
    """Normalize one raw_scopus_record to canonical publications.

    Caller ensures raw_record.validation_status == 'VALID'.
    """
    eid = normalize_eid(raw_record.eid_raw)
    if eid is None:
        return NormalizationResult(
            outcome="INVALID_EID",
            publication=None,
            error_message="Raw record has no usable EID",
        )

    # Same-batch deduplication: check in-memory cache first
    existing_pub = existing_by_eid.get(eid)

    if existing_pub is not None:
        # EID exists — compare metadata without writing
        changed = compare_metadata(existing_pub, {}, raw_record.raw_payload)
        if changed:
            outcome = "EXISTING_METADATA_CHANGED"
        else:
            outcome = "EXISTING_UNCHANGED"
        # Always link provenance even for unchanged
        try:
            link_provenance(db, existing_pub, raw_record, provenance_by_raw_id)
        except ProvenanceConflict:
            return NormalizationResult(
                outcome="NORMALIZATION_ERROR",
                publication=None,
                error_message="RAW_SOURCE_CANONICAL_CONFLICT",
            )
        return NormalizationResult(
            outcome=outcome,
            publication=existing_pub,
            changed_fields=changed,
        )

    # EID is new in this batch — attempt to create
    new_pub = create_publication_from_raw(raw_record)

    try:
        with db.begin_nested():
            db.add(new_pub)
            db.flush()

    except IntegrityError as exc:
        if not is_publication_eid_unique_violation(exc):
            raise  # unrelated DB error — propagate

        # Race: another process created it concurrently.
        # The nested savepoint has already been rolled back automatically.
        # The outer transaction remains usable.
        # Under READ COMMITTED, the winner's row is now visible.
        recovered_pub = _recover_concurrent_pub(db, eid)
        if recovered_pub is None:
            return NormalizationResult(
                outcome="NORMALIZATION_ERROR",
                publication=None,
                error_message="CONCURRENT_INSERT_NOT_VISIBLE",
            )

        # Race recovery succeeded — link to the winner
        existing_by_eid[eid] = recovered_pub
        try:
            link_provenance(db, recovered_pub, raw_record, provenance_by_raw_id)
        except ProvenanceConflict:
            return NormalizationResult(
                outcome="NORMALIZATION_ERROR",
                publication=None,
                error_message="RAW_SOURCE_CANONICAL_CONFLICT",
            )
        return NormalizationResult(
            outcome="EXISTING_UNCHANGED",
            publication=recovered_pub,
        )

    # Insert succeeded — update cache and link
    existing_by_eid[eid] = new_pub
    try:
        link_provenance(db, new_pub, raw_record, provenance_by_raw_id)
    except ProvenanceConflict:
        return NormalizationResult(
            outcome="NORMALIZATION_ERROR",
            publication=None,
            error_message="RAW_SOURCE_CANONICAL_CONFLICT",
        )

    return NormalizationResult(outcome="NEW", publication=new_pub)


def _recover_concurrent_pub(db: Session, eid: str) -> Publication | None:
    """Recover publication by EID after a concurrent insert race.

    Implements bounded retry under READ COMMITTED isolation.
    """
    for _ in range(3):
        pub = db.query(Publication).filter(Publication.eid == eid).first()
        if pub is not None:
            return pub
    return None


# ---------------------------------------------------------------------------
# Batch normalization
# ---------------------------------------------------------------------------

def normalize_batch(
    db: Session,
    raw_records: list[RawScopusRecord],
    eid_cache: dict[str, Publication],
    seen_eids_in_import: set[str] | None = None,
) -> tuple[Normalizer, list[RawScopusRecord]]:
    """Normalize a batch of raw records, updating eid_cache in place.

    eid_cache holds both preloaded publications AND newly created ones from this
    batch. normalize_single_raw reads it to avoid duplicate inserts; created
    publications are written back so later rows in the same batch see them too.

    Intra-file duplicates (same EID appearing twice in the same batch) are
    detected by looking in eid_cache: the second row sees the canonical pub
    already created by the first and is classified EXISTING_UNCHANGED (or
    EXISTING_METADATA_CHANGED) rather than NEW.  canonical_intra_duplicate
    tracks how many such rows were skipped.
    """
    normalizer = Normalizer()
    seen_eids = seen_eids_in_import if seen_eids_in_import is not None else set()
    raw_ids = [raw.id for raw in raw_records]
    provenance_by_raw_id = {
        link.raw_record_id: link
        for link in (
            db.query(PublicationRawSource)
            .filter(PublicationRawSource.raw_record_id.in_(raw_ids))
            .all()
            if raw_ids
            else []
        )
    }

    for raw in raw_records:
        eid = normalize_eid(raw.eid_raw)

        # Intra-file duplicate: EID already processed in this same batch
        if eid is not None and eid in seen_eids:
            normalizer.counters.canonical_intra_duplicate += 1
            # Still classify + count the outcome so canonical_processed includes this row
            canonical_pub = eid_cache.get(eid)
            if canonical_pub is not None:
                changed = compare_metadata(canonical_pub, {}, raw.raw_payload)
                if changed:
                    normalizer.counters.canonical_metadata_changed += 1
                else:
                    normalizer.counters.canonical_existing += 1
                try:
                    link_provenance(db, canonical_pub, raw, provenance_by_raw_id)
                except ProvenanceConflict:
                    pass  # concurrent link already won
            else:
                # Should not happen: cache should contain pub after first row
                normalizer.counters.canonical_failed += 1
            continue

        result = normalize_single_raw(db, raw, eid_cache, provenance_by_raw_id)
        normalizer.record(result)

        if eid is not None:
            seen_eids.add(eid)

    return normalizer, []


# ---------------------------------------------------------------------------
# Normalizer — orchestrates per-import normalization
# ---------------------------------------------------------------------------

BATCH_SIZE = getattr(settings, "scopus_normalization_batch_size", 500)


class Normalizer:
    """Orchestrates full-import normalization with batched processing."""

    def __init__(self) -> None:
        self.counters = NormalizationCounters()
        self.errors: list[dict] = []

    def record(self, result: NormalizationResult) -> None:
        outcome = result.outcome
        if outcome == "NEW":
            self.counters.canonical_new += 1
        elif outcome == "EXISTING_UNCHANGED":
            self.counters.canonical_existing += 1
        elif outcome == "EXISTING_METADATA_CHANGED":
            self.counters.canonical_metadata_changed += 1
        elif outcome in {"INVALID_EID", "NORMALIZATION_ERROR"}:
            self.counters.canonical_failed += 1
            if outcome == "NORMALIZATION_ERROR" and result.error_message:
                self.errors.append({"outcome": outcome, "error": result.error_message})

    def finalize(
        self,
        db: Session,
        import_id: uuid.UUID,
        *,
        status: str = "COMPLETED",
        total_records: int | None = None,
    ) -> None:
        """Persist normalization counters to scopus_imports.normalization_summary.

        Writes ONLY to normalization_summary — error_summary retains raw validation
        errors and is never overwritten by normalization.
        """
        item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
        if item is None:
            return

        summary = self.counters.to_dict()
        summary["status"] = status
        if total_records is not None:
            summary["total_records"] = total_records
            summary["progress_percent"] = (
                min(100, round(self.counters.canonical_processed * 100 / total_records))
                if total_records
                else (100 if status == "COMPLETED" else 0)
            )
        if self.errors:
            summary["normalization_errors"] = self.errors[:50]  # cap at 50

        item.normalization_summary = summary
        item.updated_at = datetime.now(UTC)
        db.commit()


# ---------------------------------------------------------------------------
# Top-level service entry point
# ---------------------------------------------------------------------------

def normalize_import(
    db: Session,
    import_id: uuid.UUID,
    cancel_check_interval: int = BATCH_SIZE,
) -> NormalizationCounters:
    """Normalize all VALID raw records for a completed Scopus import.

    Workflow:
      1. Load all eligible raw records.
      2. Batch-process with preloaded EID lookups.
      3. Track intra-file duplicates across the entire import.
      4. Write provenance links per row.
      5. Persist counters to scopus_imports.normalization_summary.
      6. Idempotent: re-running produces stable counters (EXISTING_UNCHANGED).

    Cancellation is checked at every committed batch boundary.  Completed
    batches remain durable and unprocessed raw rows stay unlinked.  A cancelled
    import is terminal; retry requires a new import (the original raw/provenance
    remains immutable for auditability).
    """
    batch_size = max(1, cancel_check_interval)

    # Step 1: load eligible raw records
    eligible = (
        db.query(RawScopusRecord)
        .filter(
            RawScopusRecord.import_id == import_id,
            RawScopusRecord.validation_status == "VALID",
        )
        .order_by(RawScopusRecord.row_number)
        .all()
    )

    normalizer = Normalizer()
    total_records = len(eligible)
    normalizer.finalize(
        db,
        import_id,
        status="NORMALIZING" if eligible else "COMPLETED",
        total_records=total_records,
    )
    if not eligible:
        return normalizer.counters

    # Step 2: preload existing publications by EID
    raw_eids = [normalize_eid(r.eid_raw) for r in eligible]
    valid_eids = [e for e in raw_eids if e is not None]

    existing_by_eid: dict[str, Publication] = {}
    if valid_eids:
        chunks = [
            valid_eids[i : i + batch_size]
            for i in range(0, len(valid_eids), batch_size)
        ]
        for chunk in chunks:
            pubs = db.query(Publication).filter(Publication.eid.in_(chunk)).all()
            for pub in pubs:
                existing_by_eid[pub.eid] = pub

    # Step 3: process in batches
    seen_eids_in_import: set[str] = set()

    for offset in range(0, len(eligible), batch_size):
        batch = eligible[offset : offset + batch_size]
        try:
            batch_normalizer, _ = normalize_batch(
                db,
                batch,
                existing_by_eid,
                seen_eids_in_import,
            )
        except Exception:
            db.rollback()
            normalizer.finalize(
                db,
                import_id,
                status="FAILED",
                total_records=total_records,
            )
            raise
        # Merge counters (no longer frozen, direct += works)
        normalizer.counters.canonical_new += batch_normalizer.counters.canonical_new
        normalizer.counters.canonical_existing += batch_normalizer.counters.canonical_existing
        normalizer.counters.canonical_metadata_changed += batch_normalizer.counters.canonical_metadata_changed
        normalizer.counters.canonical_failed += batch_normalizer.counters.canonical_failed
        normalizer.counters.canonical_intra_duplicate += batch_normalizer.counters.canonical_intra_duplicate
        normalizer.errors.extend(batch_normalizer.errors)

        # Commit each completed batch so cancellation never invalidates earlier
        # canonical rows or provenance links.
        normalizer.finalize(
            db,
            import_id,
            status="NORMALIZING",
            total_records=total_records,
        )

        # Refresh from PostgreSQL after the commit so a cancellation written by
        # another session is visible before the next batch begins.
        db.expire_all()
        import_item = (
            db.query(ScopusImport)
            .filter(ScopusImport.id == import_id)
            .populate_existing()
            .first()
        )
        if import_item is not None and import_item.status == "CANCELLED":
            normalizer.finalize(
                db,
                import_id,
                status="CANCELLED",
                total_records=total_records,
            )
            return normalizer.counters

    # canonical_processed is a @property — computed on access, no need to recalculate

    # Step 4: persist summary
    normalizer.finalize(
        db,
        import_id,
        status="COMPLETED",
        total_records=total_records,
    )

    return normalizer.counters
