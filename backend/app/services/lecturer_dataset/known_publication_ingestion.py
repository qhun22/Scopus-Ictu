"""M2.7A-4 — ICTU-Craw known-publication ingestion service.

This service is intentionally narrow and READ-ONLY on master data:

  - It does NOT touch the ``lecturers`` table.
  - It does NOT touch M2.7 identity tables.
  - It does NOT modify ``publications`` or any Scopus-derived data.
  - It ONLY writes to ``lecturer_source_snapshots`` and
    ``lecturer_known_publications``.

The service accepts a typed in-memory list of :class:`CrawLecturerSource`
records (already produced from the frozen Craw artifacts by the caller).
This is a deliberate separation: the service never reads Craw, and never
embeds an absolute Craw path.

Architectural contract
======================

SNAPSHOT_UNIT
    ONE :class:`LecturerSourceSnapshot` per ICTU-Craw lecturer record.
    The snapshot is the immutable capture of the lecturer/profile source
    state (full Craw lecturer JSON), and the publication attribution rows
    reference that snapshot via the M1C-01 composite FK.

KNOWN_PUBLICATION_IDEMPOTENCY_KEY
    ``(snapshot_hash, lecturer_id, source_publication_url)`` — if the
    same content-addressed snapshot already exists in the database and
    the lecturer is already mapped, the row is reused and no second
    snapshot is written. Within a single snapshot, each distinct
    ``source_publication_url`` produces one
    :class:`LecturerKnownPublication` row (the
    ``source_publication_url`` is the publication's stable
    ``source_id`` from Craw).

    Cross-lecturer evidence for the same publication is preserved:
    two different lecturers may each have their own row pointing to
    the same publication (M2.7A-3 step 25). The service never
    collapses two rows on the basis of equal DOI/title.

SOURCE_DUPLICATE_POLICY
    Within a single snapshot: a single ``source_publication_url`` is
    ingested at most once (collapsed if repeated). When two or more
    distinct ``source_publication_url`` references in the same Craw
    lecturer record map to the same canonical Scopus publication
    (identical DOI or identical normalized title), the first URL is
    persisted as a :class:`LecturerKnownPublication` row and the
    remaining URLs are listed in the snapshot's
    ``validation_errors`` JSONB with code ``SOURCE_URL_COLLISION``.
    Every distinct source URL remains recoverable through
    ``snapshot.raw_payload.public_publication_links`` AND through
    ``snapshot.validation_errors``. Cross-snapshot duplicates
    (same URL in two different captures) are preserved because they
    represent two different immutable source events.

EXISTING_SERVICE_REUSABLE
    false — the existing :class:`LecturerImportService` mutates
    ``lecturers`` and uses an envelope parser that is incompatible
    with the raw Craw shape. The service below is purpose-built to
    fit the M1C-01 contract without touching master data.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master_lecturer import (
    Lecturer,
    LecturerKnownPublication,
    LecturerSourceSnapshot,
)


# ---------------------------------------------------------------------------
# DOI normalization (mirrors the conservative M2.7A-3 contract)
# ---------------------------------------------------------------------------
_DOI_PREFIXES: tuple[str, ...] = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)
_WS_RE = re.compile(r"\s+")


def normalize_doi_n0(value: str | None) -> str | None:
    """DOI_N0: trim, lowercase, strip recognized resolver prefixes only.

    No fuzzy repair, no character deletion. Returns None if the input is
    empty or not a string. Preserves the original raw value separately.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    s = unicodedata.normalize("NFKC", value).strip()
    if not s:
        return None
    low = s.lower()
    for p in _DOI_PREFIXES:
        if low.startswith(p):
            s = s[len(p):]
            low = s.lower()
            break
    s = unicodedata.normalize("NFKC", s).strip().lower()
    return s if s else None


def normalize_title_t0(value: str | None) -> str:
    """Title_T0: NFKC + trim + collapse whitespace + casefold.

    No stemming, no token reordering, no semantic transformation.
    """
    if not value:
        return ""
    s = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    return _WS_RE.sub(" ", s)


def is_valid_year(value: int | None) -> bool:
    if value is None:
        return True
    return isinstance(value, int) and 1000 <= value <= 9999


# ---------------------------------------------------------------------------
# Typed input contract
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CrawPublicationAttribution:
    """One publication attribution from a Craw lecturer record.

    ``source_publication_url`` is the stable publication-level identifier
    in the Craw dataset (the ``source_id`` of a publications.json row).
    It is the natural idempotency key together with ``snapshot_hash``.
    """

    source_publication_url: str
    title_raw: str | None
    doi_raw: str | None
    published_year: int | None


@dataclass(frozen=True, slots=True)
class CrawLecturerSource:
    """One ICTU-Craw lecturer record plus its publication attributions."""

    craw_source_id: str  # Craw record source_id (= profile URL)
    craw_full_name: str
    raw_payload: dict
    publication_attributions: tuple[CrawPublicationAttribution, ...]


@dataclass(frozen=True, slots=True)
class IngestionError:
    code: str
    message: str
    craw_source_id: str | None = None
    source_publication_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "craw_source_id": self.craw_source_id,
            "source_publication_url": self.source_publication_url,
        }


@dataclass(frozen=True, slots=True)
class IngestionPreview:
    source_lecturer_count: int
    source_publication_attribution_count: int
    mapped_lecturer_count: int
    unmapped_lecturer_count: int
    ambiguous_lecturer_count: int
    snapshots_to_create: int
    snapshots_already_present: int
    known_publications_to_create: int
    known_publications_already_present: int
    source_duplicates_within_snapshot: int
    invalid_records: int
    conflicts: int
    errors: tuple[IngestionError, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class IngestionResult:
    snapshots_created: int
    snapshots_reused: int
    known_publications_created: int
    known_publications_reused: int
    source_duplicates_collapsed: int
    unmapped_lecturers: tuple[str, ...]
    ambiguous_lecturers: tuple[str, ...]
    invalid_records: int
    errors: tuple[IngestionError, ...]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash_payload(payload: dict | list) -> str:
    """Deterministic SHA-256 over canonical JSON.

    Stable across process restarts and across machines with the same
    Python version (sort_keys=True, ensure_ascii=True so that any
    escaped unicode form is identical).
    """
    body = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _validate_attribution(attr: CrawPublicationAttribution) -> IngestionError | None:
    if not attr.source_publication_url or not attr.source_publication_url.strip():
        return IngestionError(
            code="EMPTY_SOURCE_PUBLICATION_URL",
            message="publication attribution has empty source_publication_url",
            source_publication_url=attr.source_publication_url,
        )
    if attr.title_raw is None or not str(attr.title_raw).strip():
        return IngestionError(
            code="EMPTY_TITLE",
            message="publication attribution has empty title_raw",
            source_publication_url=attr.source_publication_url,
        )
    if not is_valid_year(attr.published_year):
        return IngestionError(
            code="INVALID_YEAR",
            message=f"published_year={attr.published_year!r} outside [1000,9999]",
            source_publication_url=attr.source_publication_url,
        )
    return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class KnownPublicationIngestionService:
    """Preview (read-only) and apply (transactional) ingestion of
    ICTU-Craw publication evidence.

    The service is the authoritative writer for the
    ``lecturer_source_snapshots`` and ``lecturer_known_publications``
    tables in the M2.7A-4 path. It does not modify any other table.
    """

    # Hard-coded source-system identifier for the ICTU repository
    # provenance stream. Treated as a constant here; the existing
    # schema permits up to 50 characters (String(50)).
    SOURCE_SYSTEM_ICTU_CRAW = "ictu_craw"

    def __init__(
        self,
        *,
        source_system: str = SOURCE_SYSTEM_ICTU_CRAW,
        parser_version: str = "ictu_harvester/1.4-full",
    ) -> None:
        if not source_system or len(source_system) > 50:
            raise ValueError(f"invalid source_system length: {source_system!r}")
        if not parser_version or len(parser_version) > 100:
            raise ValueError(f"invalid parser_version length: {parser_version!r}")
        self._source_system = source_system
        self._parser_version = parser_version

    # ----------------------------------------------------------------
    # Lecturers index for deterministic mapping
    # ----------------------------------------------------------------
    @staticmethod
    def _build_lecturer_index(db: Session) -> dict[str, uuid.UUID]:
        """Map ``repository_profile_url`` -> ``lecturer.id``.

        Prefers non-null URLs. Lecturers without a profile URL cannot
        be matched from a Craw source and will be reported as unmapped.
        """
        rows = db.execute(
            select(Lecturer.id, Lecturer.repository_profile_url).where(
                Lecturer.repository_profile_url.is_not(None)
            )
        ).all()
        by_url: dict[str, uuid.UUID] = {}
        for lid, url in rows:
            if not url:
                continue
            by_url.setdefault(url, lid)
        return by_url

    # ----------------------------------------------------------------
    # Snapshot reuse query
    # ----------------------------------------------------------------
    def _existing_snapshot_hashes(
        self, db: Session, hashes: Iterable[str]
    ) -> dict[str, list[LecturerSourceSnapshot]]:
        """Map ``snapshot_hash`` -> list of matching existing snapshots.

        Multiple snapshots may share a hash if the same content was
        captured for two different lecturers (e.g., two lecturers with
        the same profile URL would be impossible, but the index is
        ``(hash, lecturer_id)`` so we keep the existing index as a
        list and let the caller filter).
        """
        hashes_list = list(set(hashes))
        if not hashes_list:
            return {}
        rows = db.execute(
            select(LecturerSourceSnapshot).where(
                LecturerSourceSnapshot.snapshot_hash.in_(hashes_list)
            )
        ).scalars().all()
        out: dict[str, list[LecturerSourceSnapshot]] = defaultdict(list)
        for r in rows:
            out[r.snapshot_hash].append(r)
        return out

    # ----------------------------------------------------------------
    # PREVIEW (read-only)
    # ----------------------------------------------------------------
    def preview(
        self, db: Session, sources: Sequence[CrawLecturerSource]
    ) -> IngestionPreview:
        by_url = self._build_lecturer_index(db)

        mapped: dict[str, uuid.UUID] = {}
        unmapped: list[str] = []
        ambiguous: list[str] = []
        seen_urls: dict[str, int] = defaultdict(int)

        # Validate and map
        all_hashes: list[str] = []
        per_source_hashes: dict[str, str] = {}
        per_source_pubs: dict[str, list[CrawPublicationAttribution]] = {}
        errors: list[IngestionError] = []
        invalid_records = 0
        source_dup_within = 0

        for src in sources:
            url = src.craw_source_id
            seen_urls[url] += 1
            if url in by_url:
                mapped[url] = by_url[url]
            else:
                unmapped.append(url)
                invalid_records += 1
                errors.append(
                    IngestionError(
                        code="UNMAPPED_LECTURER",
                        message="Craw lecturer profile URL has no canonical match",
                        craw_source_id=url,
                    )
                )
                continue

            # Compute deterministic snapshot hash over the immutable
            # Craw payload (the entire lecturer record).
            payload = src.raw_payload
            if not isinstance(payload, dict):
                invalid_records += 1
                errors.append(
                    IngestionError(
                        code="INVALID_RAW_PAYLOAD",
                        message="raw_payload must be a JSON object",
                        craw_source_id=url,
                    )
                )
                continue
            h = _hash_payload(payload)
            per_source_hashes[url] = h
            all_hashes.append(h)

            # Validate publications
            seen_pub_urls: set[str] = set()
            valid_attributions: list[CrawPublicationAttribution] = []
            for attr in src.publication_attributions:
                err = _validate_attribution(attr)
                if err is not None:
                    invalid_records += 1
                    errors.append(err)
                    continue
                if attr.source_publication_url in seen_pub_urls:
                    source_dup_within += 1
                    # Collapse within a snapshot (kept for diagnostics
                    # in the validation_errors JSONB of the snapshot)
                    continue
                seen_pub_urls.add(attr.source_publication_url)
                valid_attributions.append(attr)
            per_source_pubs[url] = valid_attributions

        # Existing snapshots and known-publication reuse
        existing_by_hash = self._existing_snapshot_hashes(db, all_hashes)
        existing_pub_keys = self._existing_known_publication_keys(
            db, mapped, per_source_hashes, per_source_pubs
        )

        snapshots_to_create = 0
        snapshots_already_present = 0
        kp_to_create = 0
        kp_already_present = 0
        for url, h in per_source_hashes.items():
            existing_snapshots_for_hash = existing_by_hash.get(h, [])
            existing_for_lecturer = [
                s for s in existing_snapshots_for_hash if str(s.lecturer_id) == str(mapped[url])
            ]
            if existing_for_lecturer:
                snapshots_already_present += 1
                snap = existing_for_lecturer[0]
                for pub in per_source_pubs[url]:
                    key = (str(snap.id), pub.source_publication_url)
                    if key in existing_pub_keys:
                        kp_already_present += 1
                    else:
                        kp_to_create += 1
            else:
                snapshots_to_create += 1
                for pub in per_source_pubs[url]:
                    kp_to_create += 1

        return IngestionPreview(
            source_lecturer_count=len(sources),
            source_publication_attribution_count=sum(
                len(s.publication_attributions) for s in sources
            ),
            mapped_lecturer_count=len(mapped),
            unmapped_lecturer_count=len(unmapped),
            ambiguous_lecturer_count=len(ambiguous),
            snapshots_to_create=snapshots_to_create,
            snapshots_already_present=snapshots_already_present,
            known_publications_to_create=kp_to_create,
            known_publications_already_present=kp_already_present,
            source_duplicates_within_snapshot=source_dup_within,
            invalid_records=invalid_records,
            conflicts=0,  # legacy field, kept for parity
            errors=tuple(errors),
        )

    # ----------------------------------------------------------------
    # Known-publication reuse lookup
    # ----------------------------------------------------------------
    @staticmethod
    def _existing_known_publication_keys(
        db: Session,
        mapped: dict[str, uuid.UUID],
        per_source_hashes: dict[str, str],
        per_source_pubs: dict[str, list[CrawPublicationAttribution]],
    ) -> set[tuple[str, str]]:
        """Return set of ``(snapshot_id_str, source_publication_url)``
        keys that are already present in the database.

        The set is computed by:

        1. finding existing snapshots for each (hash, lecturer_id),
        2. for each existing snapshot, scanning its
           ``lecturer_known_publications`` rows and producing a synthetic
           key from the snapshot id + one of {doi_normalized,
           title_normalized}.

        Note: there is no ``source_publication_url`` column in the
        schema, so the synthetic key is the best available approximation.
        The authoritative reuse decision is taken in :meth:`apply`.
        """
        keys: set[tuple[str, str]] = set()
        all_hashes = list(set(per_source_hashes.values()))
        if not all_hashes:
            return keys
        rows = db.execute(
            select(LecturerSourceSnapshot).where(
                LecturerSourceSnapshot.snapshot_hash.in_(all_hashes)
            )
        ).scalars().all()
        snap_by_key: dict[tuple[str, str], LecturerSourceSnapshot] = {}
        for s in rows:
            snap_by_key[(s.snapshot_hash, str(s.lecturer_id))] = s
        if not snap_by_key:
            return keys
        snap_ids = list({str(s.id) for s in snap_by_key.values()})
        kp_rows = db.execute(
            select(LecturerKnownPublication).where(
                LecturerKnownPublication.snapshot_id.in_(
                    [uuid.UUID(s) for s in snap_ids]
                )
            )
        ).scalars().all()
        kp_index: dict[
            tuple[str, str], list[LecturerKnownPublication]
        ] = defaultdict(list)
        for kp in kp_rows:
            if kp.doi_normalized:
                kp_index[(str(kp.snapshot_id), "doi:" + kp.doi_normalized)].append(kp)
            if kp.title_normalized:
                kp_index[(str(kp.snapshot_id), "t:" + kp.title_normalized)].append(kp)
        # Walk the planned (hash, url) -> attribution set and emit
        # synthetic keys only when the candidate snapshot exists. The
        # synthetic key carries source_publication_url, so reuse is
        # only reported when the same planned publication would hit an
        # existing known-publication row on either DOI or title match.
        for craw_url, h in per_source_hashes.items():
            lid = mapped.get(craw_url)
            if lid is None:
                continue
            s = snap_by_key.get((h, str(lid)))
            if s is None:
                continue
            sid = str(s.id)
            for pub in per_source_pubs[craw_url]:
                doi_n = normalize_doi_n0(pub.doi_raw)
                title_n = normalize_title_t0(pub.title_raw)
                matched = False
                if doi_n and kp_index.get((sid, "doi:" + doi_n)):
                    matched = True
                if not matched and title_n and kp_index.get((sid, "t:" + title_n)):
                    matched = True
                if matched:
                    keys.add((sid, pub.source_publication_url))
        return keys

    # ----------------------------------------------------------------
    # APPLY (transactional)
    # ----------------------------------------------------------------
    def apply(
        self, db: Session, sources: Sequence[CrawLecturerSource]
    ) -> IngestionResult:
        """Apply the ingestion in a single transaction.

        Reuses existing snapshots and known-publication rows when the
        content-addressed keys already exist. Never mutates the
        ``lecturers`` table. On any SQLAlchemy error the entire
        transaction is rolled back.
        """
        by_url = self._build_lecturer_index(db)
        now = datetime.now(UTC)

        unmapped: list[str] = []
        ambiguous: list[str] = []
        errors: list[IngestionError] = []
        invalid_records = 0

        # Pre-compute hashes and valid attributions
        per_source: list[tuple[CrawLecturerSource, str, list[CrawPublicationAttribution]]] = []
        for src in sources:
            url = src.craw_source_id
            if url not in by_url:
                unmapped.append(url)
                invalid_records += 1
                errors.append(
                    IngestionError(
                        code="UNMAPPED_LECTURER",
                        message="Craw lecturer profile URL has no canonical match",
                        craw_source_id=url,
                    )
                )
                continue
            if not isinstance(src.raw_payload, dict):
                invalid_records += 1
                errors.append(
                    IngestionError(
                        code="INVALID_RAW_PAYLOAD",
                        message="raw_payload must be a JSON object",
                        craw_source_id=url,
                    )
                )
                continue
            h = _hash_payload(src.raw_payload)
            valid_attributions: list[CrawPublicationAttribution] = []
            seen_pub_urls: set[str] = set()
            dups_collapsed_local = 0
            for attr in src.publication_attributions:
                err = _validate_attribution(attr)
                if err is not None:
                    invalid_records += 1
                    errors.append(err)
                    continue
                if attr.source_publication_url in seen_pub_urls:
                    dups_collapsed_local += 1
                    continue
                seen_pub_urls.add(attr.source_publication_url)
                valid_attributions.append(attr)
            per_source.append((src, h, valid_attributions))

        # Look up existing snapshots by (hash, lecturer_id)
        all_hashes = list({h for _, h, _ in per_source})
        existing_snapshots = self._existing_snapshot_hashes(db, all_hashes)
        snap_by_key: dict[tuple[str, str], LecturerSourceSnapshot] = {}
        for s_list in existing_snapshots.values():
            for s in s_list:
                snap_by_key[(s.snapshot_hash, str(s.lecturer_id))] = s

        # Look up existing known publications by (snapshot_id,
        # doi_normalized or title_normalized) so the apply path can
        # avoid double-writes even if preview was skipped.
        snap_ids_for_lookup = list({str(s.id) for s in snap_by_key.values()})
        existing_kp_index: dict[
            tuple[str, str], list[LecturerKnownPublication]
        ] = defaultdict(list)
        if snap_ids_for_lookup:
            kp_rows = db.execute(
                select(LecturerKnownPublication).where(
                    LecturerKnownPublication.snapshot_id.in_(
                        [uuid.UUID(s) for s in snap_ids_for_lookup]
                    )
                )
            ).scalars().all()
            for kp in kp_rows:
                key = str(kp.snapshot_id)
                if kp.doi_normalized:
                    existing_kp_index[(key, "doi:" + kp.doi_normalized)].append(kp)
                if kp.title_normalized:
                    existing_kp_index[(key, "t:" + kp.title_normalized)].append(kp)

        snapshots_created = 0
        snapshots_reused = 0
        kp_created = 0
        kp_reused = 0
        source_dups_collapsed = 0

        try:
            for src, h, valid_attributions in per_source:
                url = src.craw_source_id
                lecturer_id = by_url[url]
                snap = snap_by_key.get((h, str(lecturer_id)))
                if snap is None:
                    # Detect within-snapshot DOI/title collisions BEFORE
                    # collapsing, so the duplicate URLs can be surfaced
                    # in validation_errors instead of silently lost.
                    collision_keys: dict[tuple[str, str], list[str]] = defaultdict(list)
                    for attr in valid_attributions:
                        doi_n = normalize_doi_n0(attr.doi_raw)
                        title_n = normalize_title_t0(attr.title_raw)
                        if doi_n:
                            collision_keys[("doi", doi_n)].append(
                                attr.source_publication_url
                            )
                        elif title_n:
                            collision_keys[("t", title_n)].append(
                                attr.source_publication_url
                            )
                    snapshot_collisions: list[dict] = []
                    for (kind, key), urls in collision_keys.items():
                        if len(urls) > 1:
                            snapshot_collisions.append(
                                {
                                    "code": "SOURCE_URL_COLLISION",
                                    "match_kind": kind,
                                    "match_value": key,
                                    "source_publication_urls": urls,
                                    "message": (
                                        f"{len(urls)} distinct Craw source URLs "
                                        f"matched the same {('DOI' if kind == 'doi' else 'title')}; "
                                        f"only one was persisted as a KP row. "
                                        f"Recover all URLs via snapshot.raw_payload.public_publication_links."
                                    ),
                                }
                            )
                    # New snapshot
                    duplicate_count = len(src.publication_attributions) - len(valid_attributions)
                    source_dups_collapsed += duplicate_count
                    validation_errors_payload: list[dict] = list(snapshot_collisions)
                    if duplicate_count > 0:
                        validation_errors_payload.append(
                            {
                                "code": "SOURCE_DUPLICATE",
                                "message": (
                                    f"Collapsed {duplicate_count} duplicate "
                                    f"source_publication_url(s) within snapshot."
                                ),
                                "count": duplicate_count,
                            }
                        )
                    snap = LecturerSourceSnapshot(
                        id=uuid.uuid4(),
                        lecturer_id=lecturer_id,
                        source_system=self._source_system,
                        source_url=url,
                        snapshot_hash=h,
                        raw_payload=src.raw_payload,
                        parser_version=self._parser_version,
                        validation_status="VALID",
                        validation_errors=validation_errors_payload,
                        fetched_at=now,
                        created_at=now,
                    )
                    db.add(snap)
                    db.flush()
                    snap_by_key[(h, str(lecturer_id))] = snap
                    snapshots_created += 1
                else:
                    snapshots_reused += 1
                    # For reused snapshots, if a new within-snapshot
                    # collision is detected that was NOT recorded in
                    # the original snapshot's validation_errors, we
                    # surface it as a structured warning. This is
                    # important so that the second URL is NOT silently
                    # lost: it stays in snapshot.raw_payload AND is now
                    # listed in snapshot.validation_errors.
                    collision_keys: dict[tuple[str, str], list[str]] = defaultdict(list)
                    for attr in valid_attributions:
                        doi_n = normalize_doi_n0(attr.doi_raw)
                        title_n = normalize_title_t0(attr.title_raw)
                        if doi_n:
                            collision_keys[("doi", doi_n)].append(
                                attr.source_publication_url
                            )
                        elif title_n:
                            collision_keys[("t", title_n)].append(
                                attr.source_publication_url
                            )
                    new_collisions: list[dict] = []
                    for (kind, key), urls in collision_keys.items():
                        if len(urls) > 1:
                            existing_match = any(
                                e.get("code") == "SOURCE_URL_COLLISION"
                                and e.get("match_kind") == kind
                                and e.get("match_value") == key
                                for e in (snap.validation_errors or [])
                            )
                            if not existing_match:
                                new_collisions.append(
                                    {
                                        "code": "SOURCE_URL_COLLISION",
                                        "match_kind": kind,
                                        "match_value": key,
                                        "source_publication_urls": urls,
                                        "message": (
                                            f"{len(urls)} distinct Craw source URLs "
                                            f"matched the same {('DOI' if kind == 'doi' else 'title')}; "
                                            f"only one was persisted as a KP row. "
                                            f"Recover all URLs via snapshot.raw_payload.public_publication_links."
                                        ),
                                    }
                                )
                    if new_collisions:
                        # Append new collisions to the snapshot's
                        # validation_errors JSONB. This is a single,
                        # additive update to an existing row's
                        # JSONB field — no new rows are created.
                        updated_errors = list(snap.validation_errors or []) + new_collisions
                        snap.validation_errors = updated_errors
                        db.flush()

                # Known publications — every distinct source_publication_url
                # is mapped to exactly one KP row, but the within-snapshot
                # DOI/title secondary idempotency still collapses the
                # duplicate into the FIRST occurrence. The second URL
                # remains in snapshot.raw_payload.public_publication_links
                # AND is now listed in snapshot.validation_errors.
                for attr in valid_attributions:
                    doi_n = normalize_doi_n0(attr.doi_raw)
                    title_n = normalize_title_t0(attr.title_raw)
                    # Idempotency check: same snapshot + same
                    # doi_normalized, or same snapshot + same
                    # title_normalized.
                    reused = False
                    if doi_n:
                        if existing_kp_index.get(
                            (str(snap.id), "doi:" + doi_n)
                        ):
                            reused = True
                    if not reused and title_n:
                        if existing_kp_index.get(
                            (str(snap.id), "t:" + title_n)
                        ):
                            reused = True
                    if reused:
                        kp_reused += 1
                        continue
                    kp = LecturerKnownPublication(
                        id=uuid.uuid4(),
                        lecturer_id=lecturer_id,
                        snapshot_id=snap.id,
                        title_raw=str(attr.title_raw),
                        title_normalized=title_n,
                        doi_raw=attr.doi_raw,
                        doi_normalized=doi_n,
                        source_title_raw=attr.title_raw,
                        published_year=attr.published_year,
                        created_at=now,
                    )
                    db.add(kp)
                    # Track locally so subsequent attrs in the same
                    # snapshot also see the row.
                    if doi_n:
                        existing_kp_index.setdefault(
                            (str(snap.id), "doi:" + doi_n), []
                        ).append(kp)
                    if title_n:
                        existing_kp_index.setdefault(
                            (str(snap.id), "t:" + title_n), []
                        ).append(kp)
                    kp_created += 1

            db.commit()
        except Exception:
            db.rollback()
            raise

        return IngestionResult(
            snapshots_created=snapshots_created,
            snapshots_reused=snapshots_reused,
            known_publications_created=kp_created,
            known_publications_reused=kp_reused,
            source_duplicates_collapsed=source_dups_collapsed,
            unmapped_lecturers=tuple(unmapped),
            ambiguous_lecturers=tuple(ambiguous),
            invalid_records=invalid_records,
            errors=tuple(errors),
        )


__all__ = [
    "CrawLecturerSource",
    "CrawPublicationAttribution",
    "IngestionError",
    "IngestionPreview",
    "IngestionResult",
    "KnownPublicationIngestionService",
    "normalize_doi_n0",
    "normalize_title_t0",
]