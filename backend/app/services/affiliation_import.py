"""Idempotent importer of author-level affiliation resolutions (Task 11).

Writes ONLY ``organizations``, ``publication_author_affiliation_resolutions``
and ``publication_author_affiliations``.  It never creates or changes Scopus
authors, publications, publication authors, lecturers, candidates or
identities, and it never upgrades a link's confidence.

Input is a list of :class:`ResolutionInput` - one per (Scopus author position,
source system) - produced by a caller from the committed alignment module.
``preview`` and ``apply`` share one planner so their numbers cannot drift.

Decision per input (counted per source system and link status):

``inserted``    new row(s) written
``reused``      an identical resolution (same author position, source and
                payload version) already exists - nothing written
``skipped``     structurally invalid / duplicate input - nothing written
``conflicted``  contradicts the database or another source, or an existing
                row with the same key has different content - nothing written
                (for a withheld link an UNRESOLVED row records the reason)

Cross-source policy (fail-closed): if any source reports an identifier-level
contradiction (``ID_CONFLICT`` / ``ID_AMBIGUOUS``) for an author position, the
trusted links of the *other* sources for that position are withheld and stored
as UNRESOLVED ``WITHHELD_SOURCE_CONFLICT``.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.affiliation import (
    LINK_METHODS,
    Organization,
    PublicationAuthorAffiliation,
    PublicationAuthorAffiliationResolution,
)
from app.models.publication import Publication, PublicationAuthor, ScopusAuthor

IMPORTER_VERSION = "affiliation-import/1"
CONFLICT_REASONS = frozenset({"ID_CONFLICT", "ID_AMBIGUOUS"})
WITHHELD_REASON = "WITHHELD_SOURCE_CONFLICT"
TRUSTED = ("VERIFIED", "CORROBORATED")


@dataclass(frozen=True, slots=True)
class OrgInput:
    source_system: str
    source_org_id: str | None
    display_name: str
    ror: str | None = None
    country_code: str | None = None

    @property
    def key(self) -> tuple[str, str | None, str | None]:
        # (source, source id, None) or (source, None, exact name): never merged by similarity
        return (self.source_system, self.source_org_id, None if self.source_org_id else self.display_name)


@dataclass(frozen=True, slots=True)
class EntryInput:
    raw_index: int | None
    raw_text: str | None
    organization: OrgInput | None = None


@dataclass(frozen=True, slots=True)
class ResolutionInput:
    eid: str
    scopus_id: str
    author_order: int
    source_system: str
    payload_sha256: str
    link_status: str
    doi: str | None = None  # DOI the source was queried with (normalized)
    link_method: str | None = None
    unresolved_reason: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    source_doi: str | None = None
    source_work_id: str | None = None
    external_position: int | None = None
    external_author_name: str | None = None
    external_author_orcid: str | None = None
    retrieved_at: datetime | None = None
    entries: tuple[EntryInput, ...] = ()

    @property
    def affiliation_presence(self) -> str | None:
        if self.link_status == "UNRESOLVED":
            return None
        return "PRESENT" if self.entries else "ABSENT"


@dataclass(slots=True)
class ImportReport:
    by_source_status: dict[tuple[str, str], Counter] = field(default_factory=lambda: defaultdict(Counter))
    conflict_reasons: Counter = field(default_factory=Counter)
    skipped_reasons: Counter = field(default_factory=Counter)
    resolutions_to_insert: int = 0
    affiliations_to_insert: int = 0
    organizations_to_insert: int = 0
    organizations_reused: int = 0
    organization_attribute_drift: int = 0

    def count(self, item: ResolutionInput, outcome: str) -> None:
        self.by_source_status[(item.source_system, item.link_status)][outcome] += 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "by_source_and_confidence": {
                f"{s}/{l}": dict(c) for (s, l), c in sorted(self.by_source_status.items())
            },
            "conflict_reasons": dict(self.conflict_reasons),
            "skipped_reasons": dict(self.skipped_reasons),
            "resolutions_to_insert": self.resolutions_to_insert,
            "affiliations_to_insert": self.affiliations_to_insert,
            "organizations_to_insert": self.organizations_to_insert,
            "organizations_reused": self.organizations_reused,
            "organization_attribute_drift": self.organization_attribute_drift,
        }


# ----------------------------------------------------------------------------
def _validate(item: ResolutionInput) -> str | None:
    if item.link_status not in ("VERIFIED", "CORROBORATED", "UNRESOLVED"):
        return "INVALID_LINK_STATUS"
    if item.link_status == "UNRESOLVED":
        if item.entries:
            return "UNRESOLVED_WITH_AFFILIATION"
        if not item.unresolved_reason or item.link_method:
            return "INVALID_UNRESOLVED"
        return None
    if item.link_method != LINK_METHODS[item.link_status]:
        return "INVALID_LINK_METHOD"
    if item.unresolved_reason or item.external_position is None or item.retrieved_at is None:
        return "INVALID_TRUSTED_LINK"
    if item.link_status == "VERIFIED" and not item.external_author_orcid:
        return "VERIFIED_WITHOUT_IDENTIFIER"
    return None


def apply_cross_source_policy(inputs: Sequence[ResolutionInput]) -> tuple[list[ResolutionInput], set[int]]:
    """Withhold trusted links of other sources when a source reports an ID contradiction.

    Returns the (possibly rewritten) inputs and the indexes that were withheld.
    """
    groups: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    for i, item in enumerate(inputs):
        groups[(item.eid, item.scopus_id, item.author_order)].append(i)
    out = list(inputs)
    withheld: set[int] = set()
    for idxs in groups.values():
        culprits = [inputs[i] for i in idxs if inputs[i].unresolved_reason in CONFLICT_REASONS]
        if not culprits:
            continue
        for i in idxs:
            item = inputs[i]
            if item.link_status in TRUSTED:
                out[i] = replace(
                    item,
                    link_status="UNRESOLVED",
                    link_method=None,
                    unresolved_reason=WITHHELD_REASON,
                    evidence={
                        "withheld_link_status": item.link_status,
                        "conflicting_sources": sorted({c.source_system for c in culprits}),
                        "conflict_reasons": sorted({c.unresolved_reason for c in culprits}),
                    },
                    entries=(),
                )
                withheld.add(i)
    return out, withheld


def _signature(item: ResolutionInput) -> tuple:
    return (
        item.link_status,
        item.link_method,
        item.unresolved_reason,
        item.affiliation_presence,
        item.external_position,
        item.external_author_orcid,
        item.source_work_id,
        item.source_doi,
        tuple(
            (e.raw_index, e.raw_text, e.organization.key if e.organization else None) for e in item.entries
        ),
    )


class AffiliationImportService:
    """Preview (read-only) and apply (single transaction)."""

    def preview(self, db: Session, inputs: Sequence[ResolutionInput]) -> ImportReport:
        return self._plan(db, inputs)[0]

    def apply(self, db: Session, inputs: Sequence[ResolutionInput]) -> ImportReport:
        report, writes = self._plan(db, inputs)
        try:
            org_ids = self._ensure_organizations(db, writes, report, create=True)
            for item, pa_id in writes:
                res = PublicationAuthorAffiliationResolution(
                    id=uuid.uuid4(),
                    publication_author_id=pa_id,
                    source_system=item.source_system,
                    source_payload_sha256=item.payload_sha256,
                    link_status=item.link_status,
                    link_method=item.link_method,
                    unresolved_reason=item.unresolved_reason,
                    affiliation_presence=item.affiliation_presence,
                    evidence=item.evidence,
                    source_doi=item.source_doi,
                    source_work_id=item.source_work_id,
                    external_position=item.external_position,
                    external_author_name=item.external_author_name,
                    external_author_orcid=item.external_author_orcid,
                    retrieved_at=item.retrieved_at,
                    importer_version=IMPORTER_VERSION,
                )
                db.add(res)
                db.flush()
                for ord_, entry in enumerate(item.entries, start=1):
                    db.add(
                        PublicationAuthorAffiliation(
                            resolution_id=res.id,
                            link_status=item.link_status,
                            ord=ord_,
                            raw_index=entry.raw_index,
                            raw_affiliation_text=entry.raw_text,
                            organization_id=org_ids[entry.organization.key] if entry.organization else None,
                        )
                    )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return report

    # ------------------------------------------------------------------
    def _plan(
        self, db: Session, raw_inputs: Sequence[ResolutionInput]
    ) -> tuple[ImportReport, list[tuple[ResolutionInput, uuid.UUID]]]:
        report = ImportReport()
        inputs, withheld = apply_cross_source_policy(raw_inputs)

        eids = {i.eid for i in inputs}
        slots: dict[tuple[str, str], tuple[uuid.UUID, int, str | None]] = {}
        if eids:
            rows = db.execute(
                select(Publication.eid, ScopusAuthor.scopus_id, PublicationAuthor.id, PublicationAuthor.author_order, Publication.doi)
                .join(PublicationAuthor, PublicationAuthor.publication_id == Publication.id)
                .join(ScopusAuthor, ScopusAuthor.id == PublicationAuthor.scopus_author_id)
                .where(Publication.eid.in_(eids))
            ).all()
            slots = {(eid, sid): (pa_id, order, doi) for eid, sid, pa_id, order, doi in rows}
        pa_ids = {v[0] for v in slots.values()}
        existing = self._load_existing(db, pa_ids)

        writes: list[tuple[ResolutionInput, uuid.UUID]] = []
        seen: dict[tuple[uuid.UUID, str, str], tuple] = {}
        for idx, item in enumerate(inputs):
            was_withheld = idx in withheld
            original = raw_inputs[idx]
            bucket = original  # statistics are reported under the ORIGINAL confidence
            problem = _validate(item)
            if problem:
                report.skipped_reasons[problem] += 1
                report.count(bucket, "skipped")
                continue
            slot = slots.get((item.eid, item.scopus_id))
            if slot is None:
                report.conflict_reasons["AUTHOR_POSITION_NOT_FOUND"] += 1
                report.count(bucket, "conflicted")
                continue
            pa_id, order, pub_doi = slot
            if order != item.author_order:
                report.conflict_reasons["AUTHOR_ORDER_MISMATCH"] += 1
                report.count(bucket, "conflicted")
                continue
            if item.doi and (pub_doi or "").strip().lower() != item.doi.strip().lower():
                report.conflict_reasons["DOI_MISMATCH"] += 1
                report.count(bucket, "conflicted")
                continue
            key = (pa_id, item.source_system, item.payload_sha256)
            sig = _signature(item)
            if key in seen:
                if seen[key] == sig:
                    report.skipped_reasons["DUPLICATE_INPUT"] += 1
                    report.count(bucket, "skipped")
                else:
                    report.conflict_reasons["DUPLICATE_KEY_DIFFERENT_CONTENT"] += 1
                    report.count(bucket, "conflicted")
                continue
            seen[key] = sig
            if key in existing:
                if existing[key] == sig:
                    report.count(bucket, "reused")
                else:
                    report.conflict_reasons["EXISTING_DIFFERENT_CONTENT"] += 1
                    report.count(bucket, "conflicted")
                continue
            if was_withheld:
                report.conflict_reasons[WITHHELD_REASON] += 1
                report.count(bucket, "conflicted")  # recorded as UNRESOLVED, not as a link
            else:
                report.count(bucket, "inserted")
            writes.append((item, pa_id))
            report.resolutions_to_insert += 1
            report.affiliations_to_insert += len(item.entries)
        self._ensure_organizations(db, writes, report, create=False)
        return report, writes

    @staticmethod
    def _load_existing(db: Session, pa_ids: Iterable[uuid.UUID]) -> dict[tuple[uuid.UUID, str, str], tuple]:
        ids = list(pa_ids)
        out: dict[tuple[uuid.UUID, str, str], tuple] = {}
        if not ids:
            return out
        res_rows = db.execute(
            select(PublicationAuthorAffiliationResolution).where(
                PublicationAuthorAffiliationResolution.publication_author_id.in_(ids)
            )
        ).scalars().all()
        by_res = {r.id: r for r in res_rows}
        entries: dict[uuid.UUID, list] = defaultdict(list)
        if by_res:
            for aff, org in db.execute(
                select(PublicationAuthorAffiliation, Organization)
                .outerjoin(Organization, Organization.id == PublicationAuthorAffiliation.organization_id)
                .where(PublicationAuthorAffiliation.resolution_id.in_(list(by_res)))
                .order_by(PublicationAuthorAffiliation.ord)
            ).all():
                org_key = None
                if org is not None:
                    org_key = (org.source_system, org.source_org_id, None if org.source_org_id else org.display_name)
                entries[aff.resolution_id].append((aff.raw_index, aff.raw_affiliation_text, org_key))
        for r in res_rows:
            out[(r.publication_author_id, r.source_system, r.source_payload_sha256)] = (
                r.link_status, r.link_method, r.unresolved_reason, r.affiliation_presence, r.external_position,
                r.external_author_orcid, r.source_work_id, r.source_doi, tuple(entries.get(r.id, [])),
            )
        return out

    @staticmethod
    def _ensure_organizations(
        db: Session,
        writes: Sequence[tuple[ResolutionInput, uuid.UUID]],
        report: ImportReport,
        *,
        create: bool,
    ) -> dict[tuple, uuid.UUID]:
        wanted: dict[tuple, OrgInput] = {}
        for item, _ in writes:
            for e in item.entries:
                if e.organization is not None:
                    wanted.setdefault(e.organization.key, e.organization)
        existing: dict[tuple, Organization] = {}
        if wanted:
            for org in db.execute(
                select(Organization).where(Organization.source_system.in_({o.source_system for o in wanted.values()}))
            ).scalars():
                existing[(org.source_system, org.source_org_id, None if org.source_org_id else org.display_name)] = org
        ids: dict[tuple, uuid.UUID] = {}
        to_insert = reused = drift = 0
        for key, org in wanted.items():
            found = existing.get(key)
            if found is not None:
                reused += 1
                ids[key] = found.id
                if (found.display_name, found.ror, found.country_code) != (org.display_name, org.ror, org.country_code):
                    drift += 1  # kept as-is: never overwritten or merged
                continue
            to_insert += 1
            if create:
                row = Organization(
                    id=uuid.uuid4(), source_system=org.source_system, source_org_id=org.source_org_id,
                    ror=org.ror, display_name=org.display_name, country_code=org.country_code,
                )
                db.add(row)
                ids[key] = row.id
        if create:
            db.flush()
        report.organizations_to_insert, report.organizations_reused, report.organization_attribute_drift = to_insert, reused, drift
        return ids


__all__ = [
    "AffiliationImportService",
    "CONFLICT_REASONS",
    "EntryInput",
    "IMPORTER_VERSION",
    "ImportReport",
    "OrgInput",
    "ResolutionInput",
    "WITHHELD_REASON",
    "apply_cross_source_policy",
]
