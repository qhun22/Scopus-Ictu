"""Per-author-position affiliation view shared by the publication export and the
"affiliation gaps" list (week-7 API contract: ``Hun1/0511/HOP_DONG_API_TUAN7.md``).

Read-only. Two layers:

* ``decide_position`` is a pure function over plain data (no database): given the
  CURRENT resolution of each source and the ACTIVE ADMIN overrides of one author
  position it returns the units to show, the best automatic status and, when no
  unit can be shown, exactly one gap reason.
* ``load_positions`` fetches those inputs set-based (a fixed number of queries per
  chunk of publications, never per publication).

Rules (contract section 2):
  1. ACTIVE override with confidence CORROBORATED -> only those units, labelled
     MANUAL_REVIEW / admin. They never become VERIFIED.
  2. Otherwise every unit of the current VERIFIED/CORROBORATED resolutions, each
     with the confidence of its own resolution. Sources are never merged.
  3. Otherwise no unit and a single gap reason.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.affiliation import Organization
from app.models.affiliation import PublicationAuthorAffiliation as Aff
from app.models.affiliation import PublicationAuthorAffiliationResolution as Res
from app.models.affiliation_override import PublicationAuthorAffiliationOverride as Override
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import PublicationAuthor, ScopusAuthor
from app.services.publication_exclusions import not_excluded

MANUAL_REVIEW = "MANUAL_REVIEW"
ADMIN_SOURCE = "admin"
NOT_RECONCILED = "NOT_RECONCILED"

# Order = priority when several reasons could apply (contract section 6): the code that says the
# matching got furthest wins, because it tells the ADMIN where to act.
GAP_REASONS: tuple[str, ...] = (
    "ADMIN_MARKED_UNRESOLVED",
    "SOURCE_HAS_NO_AFFILIATION",
    "ID_CONFLICT",
    "ID_AMBIGUOUS",
    "POSITION_CLAIMED_BY_OTHER_ID",
    "ORDER_INCONSISTENT_WITH_VERIFIED_ID",
    "WITHHELD_SOURCE_CONFLICT",
    "OPENALEX_ENTITY_NAME_CONFLICT",
    "NAME_MISMATCH",
    "NO_RAW_AUTHOR_NAME",
    "AUTHOR_COUNT_MISMATCH",
    "NO_EXTERNAL_AUTHOR_LIST",
    "DUPLICATE_DOI_IN_SOURCE",
    "NO_EXTERNAL_WORK",
    "NOT_RECONCILED",
    "UNKNOWN",
)
_REASON_RANK = {code: i for i, code in enumerate(GAP_REASONS)}
_STATUS_RANK = {"VERIFIED": 2, "CORROBORATED": 1, "UNRESOLVED": 0}
_TRUSTED = ("VERIFIED", "CORROBORATED")

CSV_COLUMNS: tuple[str, ...] = (
    "eid", "doi", "title", "year", "source_title", "author_count", "author_order", "scopus_id",
    "author_name", "affiliation", "confidence", "source", "evidence_url", "affiliation_status",
    "gap_reason", "ictu_lecturer",
)
GAPS_CSV_COLUMNS: tuple[str, ...] = (
    "eid", "doi", "title", "year", "author_count", "author_order", "scopus_id", "author_name",
    "affiliation_status", "reason", "by_source", "admin_reviewed", "ictu_lecturer",
)
_JOIN = " | "
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
CHUNK = 300  # publications per set of queries


# ----------------------------------------------------------------------------- plain data
@dataclass(frozen=True, slots=True)
class Unit:
    text: str | None
    organizations: tuple[tuple[str, str | None], ...]  # (name, country_code)
    confidence: str  # VERIFIED | CORROBORATED | MANUAL_REVIEW
    source: str  # openalex | crossref | admin
    evidence_url: str | None


@dataclass(frozen=True, slots=True)
class ResolutionInput:
    source: str
    link_status: str
    unresolved_reason: str | None
    presence: str | None  # PRESENT | ABSENT | None
    units: tuple[Unit, ...] = ()  # only for VERIFIED / CORROBORATED


@dataclass(frozen=True, slots=True)
class OverrideInput:
    affiliation_text: str
    confidence: str  # CORROBORATED | UNRESOLVED
    evidence_url: str


@dataclass(frozen=True, slots=True)
class SourceOutcome:
    source: str
    link_status: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class Decision:
    affiliation_status: str
    units: tuple[Unit, ...]
    gap_reason: str | None
    by_source: tuple[SourceOutcome, ...]
    admin_reviewed: bool


@dataclass(slots=True)
class Position:
    publication_author_id: uuid.UUID
    publication_id: uuid.UUID
    author_order: int
    scopus_id: str
    author_name: str
    decision: Decision
    ictu_lecturers: tuple[str, ...] = ()
    overrides: list[Override] = field(default_factory=list)


# ----------------------------------------------------------------------------- decision
def evidence_url_for(source: str, source_work_id: str | None, source_doi: str | None) -> str | None:
    """A link a human can open. OpenAlex stores a URL; Crossref stores the DOI."""

    if source_work_id and source_work_id.lower().startswith(("http://", "https://")):
        return source_work_id
    doi = (source_doi or (source_work_id if source == "crossref" else None) or "").strip()
    return f"https://doi.org/{doi}" if doi else None


def _gap_reason(
    resolutions: Sequence[ResolutionInput], active_overrides: Sequence[OverrideInput]
) -> str:
    if any(o.confidence == "UNRESOLVED" for o in active_overrides):
        return "ADMIN_MARKED_UNRESOLVED"
    if not resolutions:
        return "NOT_RECONCILED"
    candidates: list[str] = []
    for res in resolutions:
        if res.link_status in _TRUSTED:
            # Matched, but the source lists no unit (or lists one we hold no row for).
            absent = res.presence == "ABSENT"
            candidates.append("SOURCE_HAS_NO_AFFILIATION" if absent else "UNKNOWN")
        else:
            code = res.unresolved_reason or "UNKNOWN"
            candidates.append(code if code in _REASON_RANK else "UNKNOWN")
    return min(candidates, key=_REASON_RANK.__getitem__)


def decide_position(
    resolutions: Sequence[ResolutionInput], active_overrides: Sequence[OverrideInput]
) -> Decision:
    """``resolutions`` must be the CURRENT one per source; ``active_overrides`` oldest first."""

    status = (
        max((r.link_status for r in resolutions), key=_STATUS_RANK.__getitem__)
        if resolutions
        else NOT_RECONCILED
    )
    by_source = tuple(
        SourceOutcome(
            source=r.source,
            link_status=r.link_status,
            reason=r.unresolved_reason
            or ("SOURCE_HAS_NO_AFFILIATION" if r.presence == "ABSENT" else None),
        )
        for r in sorted(resolutions, key=lambda r: r.source)
    )
    admin_reviewed = bool(active_overrides)

    manual = [o for o in active_overrides if o.confidence == "CORROBORATED"]
    if manual:
        units = tuple(
            Unit(o.affiliation_text, (), MANUAL_REVIEW, ADMIN_SOURCE, o.evidence_url or None)
            for o in manual
        )
        return Decision(status, units, None, by_source, admin_reviewed)

    ordered = sorted(
        (r for r in resolutions if r.link_status in _TRUSTED),
        key=lambda r: (-_STATUS_RANK[r.link_status], r.source),
    )
    units = tuple(u for r in ordered for u in r.units)
    if units:
        return Decision(status, units, None, by_source, admin_reviewed)
    reason = _gap_reason(resolutions, active_overrides)
    return Decision(status, (), reason, by_source, admin_reviewed)


def unit_label(unit: Unit) -> str:
    """The text shown for a unit: the source's own words, else its first organization."""

    return unit.text or (unit.organizations[0][0] if unit.organizations else "")


# ----------------------------------------------------------------------------- loading
def _chunks(ids: Sequence[uuid.UUID], size: int = CHUNK) -> Iterable[Sequence[uuid.UUID]]:
    for i in range(0, len(ids), size):
        yield ids[i : i + size]


@dataclass(frozen=True, slots=True)
class _CurrentResolution:
    """The columns of a resolution that the decision needs (no ``evidence`` JSON)."""

    id: uuid.UUID
    publication_author_id: uuid.UUID
    source_system: str
    link_status: str
    unresolved_reason: str | None
    affiliation_presence: str | None
    source_work_id: str | None
    source_doi: str | None


@dataclass(frozen=True, slots=True)
class _AffRow:
    id: uuid.UUID
    resolution_id: uuid.UUID
    raw_index: int | None
    raw_affiliation_text: str | None


@dataclass(frozen=True, slots=True)
class _OrgRow:
    display_name: str
    country_code: str | None


def _build_units(
    resolution: _CurrentResolution,
    rows: Sequence[tuple[_AffRow, _OrgRow | None]],
) -> tuple[Unit, ...]:
    """One unit per raw affiliation string; organizations of the same string are grouped.
    Rows without a raw string (organization only) are one unit each."""

    url = evidence_url_for(
        resolution.source_system, resolution.source_work_id, resolution.source_doi
    )
    groups: dict[object, tuple[str | None, list[tuple[str, str | None]]]] = {}
    for aff, org in rows:
        key = aff.raw_index if aff.raw_index is not None else ("org", aff.id)
        text, orgs = groups.setdefault(key, (aff.raw_affiliation_text, []))
        if org is not None:
            orgs.append((org.display_name, org.country_code))
    return tuple(
        Unit(text, tuple(orgs), resolution.link_status, resolution.source_system, url)
        for text, orgs in groups.values()
    )


def load_positions(
    session: Session, publication_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[Position]]:
    """Positions of the given publications, each with its decision. Publications without
    authors map to an empty list. Read-only; four-to-five queries per chunk of publications."""

    result: dict[uuid.UUID, list[Position]] = {pid: [] for pid in publication_ids}
    for chunk in _chunks(list(publication_ids)):
        pos_rows = session.execute(
            select(
                PublicationAuthor.id,
                PublicationAuthor.publication_id,
                PublicationAuthor.author_order,
                ScopusAuthor.scopus_id,
                ScopusAuthor.preferred_name,
            )
            .join(ScopusAuthor, ScopusAuthor.id == PublicationAuthor.scopus_author_id)
            .where(PublicationAuthor.publication_id.in_(chunk))
            .order_by(
                PublicationAuthor.publication_id.asc(),
                PublicationAuthor.author_order.asc(),
                ScopusAuthor.scopus_id.asc(),
            )
        ).all()
        if not pos_rows:
            continue

        # Only the newest resolution per (position, source) is current; older ones are history.
        # Rows come sorted so the first one per key is the current one (same tie-break as
        # before: newest created_at, then smallest id). Only the columns the decision uses are
        # read, not the ``evidence`` JSON, which was most of the cost (08/11/2026: 1.28 s ->
        # ~0.3 s on 660 publications, same result). Plain ORDER BY rather than DISTINCT ON so
        # the query behaves the same on every database (SQLite would silently ignore it).
        current: dict[tuple[uuid.UUID, str], _CurrentResolution] = {}
        for row in session.execute(
            select(
                Res.id,
                Res.publication_author_id,
                Res.source_system,
                Res.link_status,
                Res.unresolved_reason,
                Res.affiliation_presence,
                Res.source_work_id,
                Res.source_doi,
            )
            .join(
                PublicationAuthor,
                PublicationAuthor.id == Res.publication_author_id,
            )
            .where(PublicationAuthor.publication_id.in_(chunk))
            .order_by(
                Res.publication_author_id,
                Res.source_system,
                Res.created_at.desc(),
                Res.id.asc(),
            )
        ).all():
            res = _CurrentResolution(*row)
            current.setdefault((res.publication_author_id, res.source_system), res)

        trusted_ids = [r.id for r in current.values() if r.link_status in _TRUSTED]
        aff_by_res: dict[uuid.UUID, list[tuple[_AffRow, _OrgRow | None]]] = defaultdict(list)
        for ids in _chunks(trusted_ids, 1000):
            for aff_id, res_id, raw_index, raw_text, org_name, org_country in session.execute(
                select(
                    Aff.id,
                    Aff.resolution_id,
                    Aff.raw_index,
                    Aff.raw_affiliation_text,
                    Organization.display_name,
                    Organization.country_code,
                )
                .outerjoin(Organization, Organization.id == Aff.organization_id)
                .where(Aff.resolution_id.in_(ids))
                .order_by(Aff.resolution_id, Aff.ord)
            ).all():
                org = _OrgRow(org_name, org_country) if org_name is not None else None
                aff_by_res[res_id].append((_AffRow(aff_id, res_id, raw_index, raw_text), org))

        overrides_by_pos: dict[uuid.UUID, list[Override]] = defaultdict(list)
        for ov in session.scalars(
            select(Override)
            .join(
                PublicationAuthor,
                PublicationAuthor.id == Override.publication_author_id,
            )
            .where(PublicationAuthor.publication_id.in_(chunk))
            .order_by(
                Override.created_at.desc(),
                Override.id.asc(),
            )
        ).all():
            overrides_by_pos[ov.publication_author_id].append(ov)

        lecturers_by_pos: dict[uuid.UUID, list[str]] = defaultdict(list)
        for pa_id, full_name in session.execute(
            select(PublicationAuthor.id, Lecturer.full_name)
            .join(
                LecturerScopusIdentity,
                LecturerScopusIdentity.scopus_author_id == PublicationAuthor.scopus_author_id,
            )
            .join(Lecturer, Lecturer.id == LecturerScopusIdentity.lecturer_id)
            .where(
                PublicationAuthor.publication_id.in_(chunk),
                LecturerScopusIdentity.status == "APPROVED",
                not_excluded(LecturerScopusIdentity.lecturer_id, PublicationAuthor.publication_id),
            )
            .order_by(PublicationAuthor.id, Lecturer.full_name.asc(), Lecturer.id.asc())
        ).all():
            if full_name not in lecturers_by_pos[pa_id]:
                lecturers_by_pos[pa_id].append(full_name)

        res_by_pos: dict[uuid.UUID, list[_CurrentResolution]] = defaultdict(list)
        for (pa_id, _source), res in current.items():
            res_by_pos[pa_id].append(res)

        for pa_id, pub_id, order, scopus_id, name in pos_rows:
            inputs = [
                ResolutionInput(
                    source=r.source_system,
                    link_status=r.link_status,
                    unresolved_reason=r.unresolved_reason,
                    presence=r.affiliation_presence,
                    units=(
                        _build_units(r, aff_by_res.get(r.id, []))
                        if r.link_status in _TRUSTED
                        else ()
                    ),
                )
                for r in res_by_pos.get(pa_id, [])
            ]
            all_overrides = overrides_by_pos.get(pa_id, [])
            active = sorted(
                (o for o in all_overrides if o.status == "ACTIVE"), key=lambda o: o.created_at
            )
            decision = decide_position(
                inputs,
                [OverrideInput(o.affiliation_text, o.confidence, o.evidence_url) for o in active],
            )
            result[pub_id].append(
                Position(
                    publication_author_id=pa_id,
                    publication_id=pub_id,
                    author_order=order,
                    scopus_id=scopus_id,
                    author_name=name,
                    decision=decision,
                    ictu_lecturers=tuple(lecturers_by_pos.get(pa_id, [])),
                    overrides=list(all_overrides),
                )
            )
    return result


def publications_with_gaps(
    session: Session, publication_ids: Sequence[uuid.UUID]
) -> set[uuid.UUID]:
    """Of the given publications, those with at least one author position still
    missing a unit (``decide_position`` found no trusted unit for it).

    Used to prioritise online affiliation enrichment at publications that still
    need it, instead of a fixed, arbitrary order — so a run capped below the
    total publication count makes monotonic progress batch after batch rather
    than repeatedly re-fetching ones that already have a good result.
    """

    positions_by_pub = load_positions(session, publication_ids)
    return {
        pub_id
        for pub_id, positions in positions_by_pub.items()
        if any(p.decision.gap_reason is not None for p in positions)
    }


# ----------------------------------------------------------------------------- CSV
def _cell(value: object) -> object:
    """Neutralise spreadsheet formulas in text that comes from outside (titles, names, units)."""

    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _part(value: str | None) -> str:
    """One element of a ' | ' joined cell; a literal ' | ' inside it would break alignment."""

    return (value or "").replace(_JOIN, " / ")


def _joined(values: Iterable[str | None]) -> str:
    return _JOIN.join(_part(v) for v in values)


def csv_bytes(header: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    """UTF-8 with BOM (Excel needs it for Vietnamese), CRLF line ends, minimal quoting."""

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_cell("" if v is None else v) for v in row])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def export_csv_rows(items: Sequence[tuple[object, Sequence[Position]]]) -> list[list[object]]:
    """One row per author position; a publication with no authors still gets one row.

    ``items`` is ``[(publication, positions)]`` where ``publication`` has the Publication
    attributes used below. Several units stay on ONE row, joined by ' | ' in the same order
    in ``affiliation``, ``confidence``, ``source`` and ``evidence_url``.
    """

    rows: list[list[object]] = []
    for pub, positions in items:
        head = [pub.eid, pub.doi, pub.title, pub.year, pub.source_title, len(positions)]
        if not positions:
            rows.append(head + [None] * 10)
            continue
        for p in positions:
            d = p.decision
            rows.append(
                head
                + [
                    p.author_order,
                    p.scopus_id,
                    p.author_name,
                    _joined(unit_label(u) for u in d.units),
                    _joined(u.confidence for u in d.units),
                    _joined(u.source for u in d.units),
                    _joined(u.evidence_url for u in d.units),
                    d.affiliation_status,
                    d.gap_reason,
                    _joined(p.ictu_lecturers),
                ]
            )
    return rows


def gaps_csv_rows(items: Sequence[tuple[object, int, Position]]) -> list[list[object]]:
    """``items`` is ``[(publication, author_count, gap position)]``."""

    rows: list[list[object]] = []
    for pub, count, p in items:
        d = p.decision
        rows.append(
            [
                pub.eid, pub.doi, pub.title, pub.year, count, p.author_order, p.scopus_id,
                p.author_name, d.affiliation_status, d.gap_reason,
                _JOIN.join(f"{s.source}:{s.reason or s.link_status}" for s in d.by_source),
                "true" if d.admin_reviewed else "false",
                _joined(p.ictu_lecturers),
            ]
        )
    return rows


__all__ = [
    "ADMIN_SOURCE", "CSV_COLUMNS", "Decision", "GAPS_CSV_COLUMNS", "GAP_REASONS", "MANUAL_REVIEW",
    "NOT_RECONCILED", "OverrideInput", "Position", "ResolutionInput", "SourceOutcome", "Unit",
    "csv_bytes", "decide_position", "evidence_url_for", "export_csv_rows", "gaps_csv_rows",
    "load_positions", "publications_with_gaps", "unit_label",
]
