"""Author normalization — M2.6B.

Extracts structured author identity from raw Scopus rows and links authors to
canonical publications using the M2.6A provenance chain:

    raw_scopus_records
        → publication_raw_sources
        → publications

Pipeline:
    parse_author_occurrences(row)     → list[AuthorOccurrence]
    upsert_scopus_author()             → ScopusAuthor
    ensure_name_variant()              → ScopusAuthorNameVariant (idempotent)
    ensure_publication_author_link()   → PublicationAuthor (idempotent)

M2.7 lecturer matching is explicitly OUT OF SCOPE.

Key invariants enforced:
  1. scopus_authors.scopus_id UNIQUE — identity barrier; upsert-safe via savepoint.
  2. scopus_author_name_variants(scopus_author_id, variant_type, variant_name) UNIQUE — additive.
  3. publication_authors(publication_id, author_order) UNIQUE — first-wins.
  4. publication_authors(publication_id, scopus_author_id) UNIQUE — idempotent link.
  5. Full-name embedded ID must match Author(s) ID field — mismatch → structured error.
  6. Normalization summary nested "authors" key is preserved across M2.6A re-runs.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from app.models.publication import (
    PublicationAuthor,
    ScopusAuthor,
    ScopusAuthorNameVariant,
)
from app.models.scopus_raw import RawScopusRecord, ScopusImport
from app.services.normalization.scopus_normalizer import normalize_import

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Variant types
# ---------------------------------------------------------------------------

VARIANT_DISPLAY = "AUTHOR_DISPLAY"
VARIANT_FULL_NAME = "AUTHOR_FULL_NAME"

# ---------------------------------------------------------------------------
# Author occurrence — parsed from one raw row
# ---------------------------------------------------------------------------


@dataclass
class AuthorOccurrence:
    """One author's data parsed from a raw Scopus row."""

    scopus_id: str
    display_name: str
    full_name: str | None  # None if the field was empty
    author_order: int  # 1-based position in the author list
    embedded_id_matches: bool  # True if full-name embedded ID == scopus_id
    row_number: int  # Row number in source CSV (for error reporting)

    # Provenance
    raw_record_id: uuid.UUID
    import_id: uuid.UUID


@dataclass
class AuthorNormalizationCounters:
    """Counters for an author normalization run."""

    raw_records_processed: int = 0
    raw_records_failed: int = 0
    author_occurrences: int = 0
    unique_authors_seen: int = 0
    authors_created: int = 0
    authors_existing: int = 0
    publication_author_links_created: int = 0
    publication_author_links_existing: int = 0
    variants_created: int = 0
    variants_existing: int = 0
    conflicts: int = 0
    _seen_scopus_ids: set[str] = field(default_factory=set, repr=False)

    def to_dict(self) -> dict:
        return {
            "raw_records_processed": self.raw_records_processed,
            "raw_records_failed": self.raw_records_failed,
            "author_occurrences": self.author_occurrences,
            "unique_authors_seen": self.unique_authors_seen,
            "authors_created": self.authors_created,
            "authors_existing": self.authors_existing,
            "publication_author_links_created": self.publication_author_links_created,
            "publication_author_links_existing": self.publication_author_links_existing,
            "variants_created": self.variants_created,
            "variants_existing": self.variants_existing,
            "conflicts": self.conflicts,
        }


@dataclass
class AuthorNormalizationErrors:
    """Structured errors from author normalization."""

    errors: list[dict] = field(default_factory=list)

    def add(self, row_number: int, code: str, message: str, **extra: str) -> None:
        self.errors.append(
            {
                "row_number": row_number,
                "code": code,
                "message": message,
                **extra,
            }
        )

    def to_list(self) -> list[dict]:
        return self.errors[:50]  # cap at 50


# ---------------------------------------------------------------------------
# Author occurrence parser
# ---------------------------------------------------------------------------

# Matches a trailing parenthesized Scopus ID: "Nguyen, T. (58035626100)"
_EMBEDDED_ID_PATTERN = re.compile(r"\s*\(\s*(\d+)\s*\)\s*$", re.ASCII)


def parse_author_occurrences(
    raw_record: RawScopusRecord,
) -> tuple[list[AuthorOccurrence], list[dict]]:
    """Parse all author occurrences from one raw Scopus row.

    Returns (occurrences, parse_errors).
    parse_errors is a list of dicts with 'code' and 'message' keys.

    Rules:
    A. Split all three fields on semicolon and trim whitespace.
    B. Lists must have exactly equal lengths.
    C. Author order is 1-based positional.
    D. Author(s) ID is the canonical identity — must be non-empty and numeric.
    E. Duplicate same Scopus ID within one publication → structured error.
    F. Full-name embedded ID (if present) must match the Author(s) ID.
    G. Store full_name WITHOUT the trailing "(ID)" suffix.
    """
    raw = raw_record.raw_payload or {}
    authors_str = raw.get("Authors", "") or ""
    full_names_str = raw.get("Author full names", "") or ""
    author_ids_str = raw.get("Author(s) ID", "") or ""

    authors = _split_semicolon(authors_str)
    full_names = _split_semicolon(full_names_str)
    author_ids = _split_semicolon(author_ids_str)

    errors: list[dict] = []

    if len(authors) != len(full_names):
        errors.append(
            {
                "code": "AUTHOR_LIST_LENGTH_MISMATCH",
                "message": (
                    f"Authors count ({len(authors)}) != Full Names count ({len(full_names)})"
                ),
                "authors_count": len(authors),
                "full_names_count": len(full_names),
                "author_ids_count": len(author_ids),
            }
        )
    if len(authors) != len(author_ids):
        errors.append(
            {
                "code": "AUTHOR_LIST_LENGTH_MISMATCH",
                "message": (
                    f"Authors count ({len(authors)}) != Author IDs count ({len(author_ids)})"
                ),
                "authors_count": len(authors),
                "full_names_count": len(full_names),
                "author_ids_count": len(author_ids),
            }
        )

    # All three lists must have exactly equal non-zero length — fail closed.
    if not authors or len(authors) != len(full_names) or len(authors) != len(author_ids):
        return [], errors

    n = len(authors)

    occurrences: list[AuthorOccurrence] = []
    seen_ids_in_row: set[str] = set()

    for i in range(n):
        display_name = authors[i]
        full_name_raw = full_names[i]
        scopus_id = author_ids[i]

        # Extract embedded ID from full_name
        embedded_id: str | None = None
        full_name_stripped = full_name_raw
        m = _EMBEDDED_ID_PATTERN.search(full_name_raw)
        if m:
            embedded_id = m.group(1)
            full_name_stripped = full_name_raw[: m.start()].rstrip()

        scopus_id = scopus_id.strip()

        # Validate scopus_id — must be non-empty
        if not scopus_id:
            errors.append(
                {
                    "code": "MISSING_SCOPUS_ID",
                    "message": f"Author {i + 1}: empty Scopus ID",
                }
            )
            continue

        # Validate scopus_id — must be numeric
        if not scopus_id.isdigit():
            errors.append(
                {
                    "code": "NON_NUMERIC_SCOPUS_ID",
                    "message": f"Author {i + 1}: non-numeric Scopus ID '{scopus_id}'",
                }
            )
            continue

        # Check duplicate ID in same publication
        if scopus_id in seen_ids_in_row:
            errors.append(
                {
                    "code": "DUPLICATE_SCOPUS_ID_IN_PUBLICATION",
                    "message": f"Author {i + 1}: duplicate Scopus ID '{scopus_id}' in same publication",
                }
            )
            continue

        # Validate embedded ID matches Author(s) ID — identity consistency required
        if embedded_id is not None and embedded_id != scopus_id:
            errors.append(
                {
                    "code": "AUTHOR_ID_MISMATCH",
                    "message": (
                        f"Author {i + 1}: full-name embedded ID '{embedded_id}' "
                        f"!= Author(s) ID '{scopus_id}'"
                    ),
                    "embedded_id": embedded_id,
                    "author_id": scopus_id,
                }
            )
            # Do NOT create ScopusAuthor, variant, or link for identity-inconsistent occurrence
            seen_ids_in_row.add(scopus_id)
            continue

        seen_ids_in_row.add(scopus_id)

        occurrences.append(
            AuthorOccurrence(
                scopus_id=scopus_id,
                display_name=display_name.strip(),
                full_name=full_name_stripped.strip() if full_name_stripped.strip() else None,
                author_order=i + 1,
                embedded_id_matches=True,
                row_number=raw_record.row_number,
                raw_record_id=raw_record.id,
                import_id=raw_record.import_id,
            )
        )

    return occurrences, errors


def _split_semicolon(value: str) -> list[str]:
    """Split on semicolon, trim each part, drop empty trailing."""
    if not value.strip():
        return []
    parts = [p.strip() for p in value.split(";")]
    # Drop trailing empty parts caused by trailing semicolon
    while parts and parts[-1] == "":
        parts.pop()
    return parts


# ---------------------------------------------------------------------------
# Name normalization (conservative)
# ---------------------------------------------------------------------------

import unicodedata


def normalize_name(name: str) -> str:
    """Deterministic conservative name normalization.

    - Unicode NFKC
    - trim
    - collapse internal whitespace to single space
    - lowercase
    """
    if not name:
        return ""
    # NFKC normalization: canonical composition, compatibility decomposition
    normalized = unicodedata.normalize("NFKC", name)
    # Collapse multiple spaces to single space
    normalized = re.sub(r"\s+", " ", normalized)
    # Strip leading/trailing whitespace
    normalized = normalized.strip()
    # Lowercase
    normalized = normalized.lower()
    return normalized


# ---------------------------------------------------------------------------
# Author normalizer class
# ---------------------------------------------------------------------------


class AuthorNormalizer:
    """Normalizes authors for a Scopus import."""

    def __init__(self) -> None:
        self.counters = AuthorNormalizationCounters()
        self.errors = AuthorNormalizationErrors()

    def record_occurrences(
        self,
        occurrences: list[AuthorOccurrence],
        db: "Session",
        publication_by_raw_record_id: dict[uuid.UUID, uuid.UUID],
    ) -> None:
        """Process a batch of author occurrences.

        publication_by_raw_record_id maps raw_record.id → publication.id
        via the M2.6A publication_raw_sources provenance table.
        """
        for occ in occurrences:
            pub_id = publication_by_raw_record_id.get(occ.raw_record_id)
            if pub_id is None:
                # Raw record has no publication provenance — M2.6A did not create one.
                # Do NOT silently skip; record structured error.
                self.counters.raw_records_failed += 1
                self.errors.add(
                    occ.row_number,
                    "PUBLICATION_PROVENANCE_MISSING",
                    f"Raw record {occ.row_number} has no publication provenance; "
                    f"author '{occ.display_name}' ({occ.scopus_id}) cannot be linked.",
                    raw_record_id=str(occ.raw_record_id),
                    scopus_id=occ.scopus_id,
                    display_name=occ.display_name,
                )
                # Do NOT create author/variant/link for orphan row
                continue

            # Upsert ScopusAuthor
            author = self._upsert_author(db, occ)
            is_new = self.counters.unique_authors_seen < len(self.counters._seen_scopus_ids)

            # Ensure both name variants
            if occ.display_name:
                self._ensure_variant(
                    db, author.id, VARIANT_DISPLAY, occ.display_name, occ.raw_record_id
                )
            if occ.full_name:
                self._ensure_variant(
                    db, author.id, VARIANT_FULL_NAME, occ.full_name, occ.raw_record_id
                )

            # Ensure publication-author link
            self._ensure_publication_author_link(db, author.id, pub_id, occ.author_order, occ)

    def _upsert_author(
        self, db: "Session", occ: AuthorOccurrence
    ) -> ScopusAuthor:
        """Get existing author or create new one with preferred_name from FULL_NAME."""
        existing = db.query(ScopusAuthor).filter(
            ScopusAuthor.scopus_id == occ.scopus_id
        ).first()

        if existing is not None:
            self.counters.authors_existing += 1
            return existing

        # Determine preferred_name: prefer FULL_NAME over DISPLAY
        preferred = occ.full_name if occ.full_name else occ.display_name
        if not preferred:
            preferred = occ.scopus_id  # Fallback: use the ID itself

        author = ScopusAuthor(
            scopus_id=occ.scopus_id,
            preferred_name=preferred,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(author)
        try:
            db.flush()  # Get the ID without committing
            self.counters.authors_created += 1
            self.counters.unique_authors_seen += 1
            self.counters._seen_scopus_ids.add(occ.scopus_id)
            return author
        except IntegrityError:
            db.rollback()
            db.flush()
            # Race: another thread created it simultaneously
            existing = db.query(ScopusAuthor).filter(
                ScopusAuthor.scopus_id == occ.scopus_id
            ).first()
            if existing is not None:
                self.counters.authors_existing += 1
                return existing
            raise

    def _ensure_variant(
        self,
        db: "Session",
        author_id: uuid.UUID,
        variant_type: str,
        variant_name: str,
        raw_record_id: uuid.UUID,
    ) -> None:
        """Add a name variant if it doesn't already exist (idempotent)."""
        normalized = normalize_name(variant_name)

        existing = db.query(ScopusAuthorNameVariant).filter(
            ScopusAuthorNameVariant.scopus_author_id == author_id,
            ScopusAuthorNameVariant.variant_type == variant_type,
            ScopusAuthorNameVariant.variant_name == variant_name,
        ).first()

        if existing is not None:
            self.counters.variants_existing += 1
            return

        variant = ScopusAuthorNameVariant(
            scopus_author_id=author_id,
            variant_type=variant_type,
            variant_name=variant_name,
            variant_name_normalized=normalized,
            first_seen_raw_record_id=raw_record_id,
            created_at=datetime.now(UTC),
        )
        db.add(variant)
        try:
            db.flush()
            self.counters.variants_created += 1
        except IntegrityError:
            db.rollback()
            db.flush()
            self.counters.variants_existing += 1

    def _ensure_publication_author_link(
        self,
        db: "Session",
        author_id: uuid.UUID,
        publication_id: uuid.UUID,
        author_order: int,
        occ: AuthorOccurrence,
    ) -> None:
        """Ensure publication-author link, record conflicts without silent overwrite."""
        # Check exact existing link
        existing_link = db.query(PublicationAuthor).filter(
            PublicationAuthor.publication_id == publication_id,
            PublicationAuthor.scopus_author_id == author_id,
        ).first()

        if existing_link is not None:
            # Idempotent: same publication + same author → NO-OP
            self.counters.publication_author_links_existing += 1
            return

        # Check if the author_order slot is occupied by a different author
        occupied = db.query(PublicationAuthor).filter(
            PublicationAuthor.publication_id == publication_id,
            PublicationAuthor.author_order == author_order,
        ).first()

        if occupied is not None:
            # Conflict A or B: record but do NOT overwrite
            self.counters.conflicts += 1
            self.errors.add(
                occ.row_number,
                "AUTHOR_ORDER_CONFLICT",
                f"Position {author_order} in publication {publication_id} "
                f"is occupied by author {occupied.scopus_author_id}; "
                f"author {author_id} could not be linked at this position.",
                expected_author_id=str(author_id),
                occupied_author_id=str(occupied.scopus_author_id),
                occupied_scopus_author_id=str(occupied.scopus_author_id),
                publication_id=str(publication_id),
                author_order=author_order,
            )
            return

        link = PublicationAuthor(
            publication_id=publication_id,
            scopus_author_id=author_id,
            author_order=author_order,
            created_at=datetime.now(UTC),
        )
        db.add(link)
        try:
            db.flush()
            self.counters.publication_author_links_created += 1
        except IntegrityError:
            db.rollback()
            db.flush()
            self.counters.publication_author_links_existing += 1

    def finalize(
        self,
        db: "Session",
        import_id: uuid.UUID,
        *,
        status: str = "COMPLETED",
    ) -> None:
        """Persist author normalization counters to normalization_summary['authors'].

        Preserves all existing M2.6A counters and any other nested keys.
        """
        item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
        if item is None:
            return

        # Preserve existing M2.6A counters and other nested keys
        existing = item.normalization_summary or {}
        if isinstance(existing, str):
            import json
            try:
                existing = json.loads(existing)
            except Exception:
                existing = {}

        author_summary = {
            "status": status,
            **self.counters.to_dict(),
        }
        if self.errors.errors:
            author_summary["errors"] = self.errors.to_list()

        # Merge: update only the 'authors' nested key
        item.normalization_summary = {**existing, "authors": author_summary}
        item.updated_at = datetime.now(UTC)
        db.commit()


# ---------------------------------------------------------------------------
# Eligibility check
# ---------------------------------------------------------------------------

APPLIED_STATUSES = frozenset({"APPLIED"})


def is_import_eligible_for_author_normalization(item: ScopusImport) -> tuple[bool, str | None]:
    """Check if a Scopus import is eligible for author normalization.

    Returns (eligible, reason_if_not).

    Note: ScopusImport has no type field; all entries in that table are Scopus imports
    by construction. Lecturer imports are tracked via AuditEvent, not ScopusImport.
    """
    if item.status != "APPLIED":
        return False, f"Import must be APPLIED, but status is '{item.status}'."
    # Must have raw records
    if item.total_records == 0:
        return False, "Import has no records."
    return True, None


def get_import_author_summary(import_id: uuid.UUID) -> dict | None:
    """Read the nested authors summary from an import's normalization_summary."""
    # Import lazily to avoid circular issues at module load
    with get_db_session() as db:
        item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
        if item is None:
            return None
        summary = item.normalization_summary
        if summary is None:
            return None
        if isinstance(summary, str):
            import json
            try:
                summary = json.loads(summary)
            except Exception:
                return None
        return summary.get("authors") if isinstance(summary, dict) else None


def get_db_session() -> "Session":
    """Get a fresh database session (used by standalone helpers)."""
    from app.core.database import get_session_factory

    return get_session_factory()()


# ---------------------------------------------------------------------------
# Top-level service entry point
# ---------------------------------------------------------------------------

BATCH_SIZE = 500


def normalize_authors_for_import(
    db: "Session",
    import_id: uuid.UUID,
    cancel_check_interval: int = BATCH_SIZE,
) -> AuthorNormalizationCounters:
    """Normalize all authors for an APPLIED Scopus import.

    Prerequisites:
      1. Import is APPLIED.
      2. M2.6A publication normalization has been run.

    Idempotent: re-running produces EXISTING counters without creating duplicates.
    On failure the import remains APPLIED (never reverts to STAGED).
    """
    # Verify eligibility
    item = db.query(ScopusImport).filter(ScopusImport.id == import_id).first()
    if item is None:
        raise ValueError(f"Import {import_id} not found.")
    eligible, reason = is_import_eligible_for_author_normalization(item)
    if not eligible:
        raise ValueError(f"Import {import_id} not eligible for author normalization: {reason}")

    # Write initial NORMALIZING status
    normalizer = AuthorNormalizer()
    normalizer.finalize(db, import_id, status="NORMALIZING")

    # Load eligible raw records (VALID only)
    raw_records = (
        db.query(RawScopusRecord)
        .filter(
            RawScopusRecord.import_id == import_id,
            RawScopusRecord.validation_status == "VALID",
        )
        .order_by(RawScopusRecord.row_number)
        .all()
    )

    if not raw_records:
        normalizer.finalize(db, import_id, status="COMPLETED")
        return normalizer.counters

    # Preload publication IDs by raw_record_id via M2.6A provenance
    from app.models.publication import PublicationRawSource

    pub_links = (
        db.query(PublicationRawSource)
        .filter(PublicationRawSource.raw_record_id.in_([r.id for r in raw_records]))
        .all()
    )
    publication_by_raw_record_id = {link.raw_record_id: link.publication_id for link in pub_links}

    batch_size = max(1, cancel_check_interval)

    for offset in range(0, len(raw_records), batch_size):
        batch = raw_records[offset : offset + batch_size]

        try:
            for raw_record in batch:
                normalizer.counters.raw_records_processed += 1
                occurrences, parse_errors = parse_author_occurrences(raw_record)

                if parse_errors:
                    for err in parse_errors:
                        normalizer.errors.add(
                            raw_record.row_number,
                            err["code"],
                            err["message"],
                        )
                    normalizer.counters.raw_records_failed += 1
                    continue

                normalizer.counters.author_occurrences += len(occurrences)
                for sid in {o.scopus_id for o in occurrences}:
                    if sid not in normalizer.counters._seen_scopus_ids:
                        normalizer.counters._seen_scopus_ids.add(sid)

                normalizer.record_occurrences(
                    occurrences, db, publication_by_raw_record_id
                )

            db.commit()

        except Exception:
            db.rollback()
            normalizer.finalize(db, import_id, status="FAILED")
            raise

        # Commit progress checkpoint
        normalizer.finalize(db, import_id, status="NORMALIZING")

        # Check cancellation
        db.expire_all()
        import_item = (
            db.query(ScopusImport)
            .filter(ScopusImport.id == import_id)
            .populate_existing()
            .first()
        )
        if import_item is not None and import_item.status == "CANCELLED":
            normalizer.finalize(db, import_id, status="FAILED")
            return normalizer.counters

    normalizer.finalize(db, import_id, status="COMPLETED")
    return normalizer.counters
