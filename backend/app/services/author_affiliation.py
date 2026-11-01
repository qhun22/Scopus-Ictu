"""Pure author-level affiliation alignment (Task 10).

Takes the *authorship rows* of one paper from an external bibliographic source
(OpenAlex / Crossref) and decides, per Scopus author slot, whether the
external authorship can be attributed to that Scopus Author ID.  It performs
no database access and no network calls, never writes anything, and never
creates a Scopus identity.

Link status (how sure we are that external authorship == Scopus slot)
---------------------------------------------------------------------
``VERIFIED``     a publisher identifier chain connects the two systems:
                 a Crossref author's ORCID, and a public ORCID record that
                 itself declares the Scopus Author ID of the slot.  The
                 identifier is the proof; name/position are not used.
                 OpenAlex entity ORCIDs are observations, never this proof.
``CORROBORATED`` no shared identifier, but the author lists have the same
                 length, the external authorship sits at the same position and
                 its name tokens equal the Scopus name tokens, and nothing
                 contradicts it.  Reported separately - NOT verified.
``UNRESOLVED``   everything else.  The reason is recorded and no affiliation is
                 assigned.

Name similarity alone is never sufficient for ``VERIFIED``.  Raw affiliation
strings (verbatim publisher text) are kept apart from normalized
organizations (the source's own organization IDs/ROR).  Missing fields are
left empty, never inferred, and a publication-level unit is never copied to
authors.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

VERIFIED = "VERIFIED"
CORROBORATED = "CORROBORATED"
UNRESOLVED = "UNRESOLVED"
ALIGNMENT_POLICY_VERSION = "author-affiliation/2"

R_NO_EXTERNAL_WORK = "NO_EXTERNAL_WORK"
R_NO_AUTHOR_LIST = "NO_EXTERNAL_AUTHOR_LIST"
R_COUNT_MISMATCH = "AUTHOR_COUNT_MISMATCH"
R_NAME_MISMATCH = "NAME_MISMATCH"
R_ORDER_INCONSISTENT = "ORDER_INCONSISTENT_WITH_VERIFIED_ID"
R_ID_CONFLICT = "ID_CONFLICT"
R_ID_AMBIGUOUS = "ID_AMBIGUOUS"
R_POSITION_CLAIMED = "POSITION_CLAIMED_BY_OTHER_ID"
R_NO_RAW_NAME = "NO_RAW_AUTHOR_NAME"
R_ENTITY_NAME_CONFLICT = "OPENALEX_ENTITY_NAME_CONFLICT"

_SCOPUS_ID_RE = re.compile(r"(?:authorId=|authid/detail\.uri\?authorId=)?(\d{6,13})")
_ORCID_RE = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")


# --------------------------------------------------------------------------- types
@dataclass(frozen=True, slots=True)
class ScopusAuthorSlot:
    scopus_id: str
    author_order: int  # 1-based, as stored in publication_authors
    full_name: str  # e.g. "Nguyen, Thanh-Tung" (ID suffix already removed)


@dataclass(frozen=True, slots=True)
class ExternalOrganization:
    """A normalized organization as asserted by the *source* (not by us)."""

    source_org_id: str | None
    display_name: str | None
    ror: str | None = None
    country_code: str | None = None


@dataclass(frozen=True, slots=True)
class AffiliationEntry:
    """One raw affiliation string of the source and the organizations the source
    itself attached to that string (empty when the source could not normalize it)."""

    raw_text: str | None
    organizations: tuple[ExternalOrganization, ...] = ()


@dataclass(frozen=True, slots=True)
class ExternalAuthorship:
    source: str  # "openalex" | "crossref"
    position: int  # 1-based
    display_name: str
    orcid: str | None = None
    raw_affiliations: tuple[str, ...] = ()
    organizations: tuple[ExternalOrganization, ...] = ()
    entries: tuple[AffiliationEntry, ...] = ()
    raw_author_name: str | None = None
    entity_id: str | None = None
    entity_display_name: str | None = None
    entity_orcid: str | None = None  # as reported by the aggregator, not publisher proof


@dataclass(frozen=True, slots=True)
class AuthorAffiliationLink:
    scopus_id: str
    author_order: int
    source: str
    status: str  # VERIFIED | CORROBORATED | UNRESOLVED
    reason: str | None = None  # why UNRESOLVED
    evidence: str | None = None  # e.g. "ORCID:<orcid>->SCOPUS:<id>" / "POSITION+COUNT+NAME"
    external_position: int | None = None
    external_name: str | None = None
    raw_affiliations: tuple[str, ...] = ()
    organizations: tuple[ExternalOrganization, ...] = ()
    entries: tuple[AffiliationEntry, ...] = ()
    # Retain observations even when affiliation assignment is withheld.
    observation: dict = field(default_factory=dict)

    @property
    def has_affiliation(self) -> bool:
        return self.status != UNRESOLVED and bool(
            self.entries or self.raw_affiliations or self.organizations
        )


# --------------------------------------------------------------------------- names
def _strip_diacritics(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def name_tokens(name: str | None) -> tuple[str, ...]:
    """Order-insensitive, accent-insensitive token multiset of a person name."""
    if not name:
        return ()
    cleaned = re.sub(r"\(\s*\d+\s*\)", " ", name)  # "(58035626100)" suffix of Scopus full names
    cleaned = _strip_diacritics(cleaned).casefold()
    return tuple(sorted(t for t in re.split(r"[^a-z0-9]+", cleaned) if t))


def names_match(left: str | None, right: str | None) -> bool:
    """Equal token multisets (so "Nguyen, Thanh-Tung" == "Thanh-Tung Nguyen").

    Deliberately strict: initials-only or subset names do not match.
    """
    a, b = name_tokens(left), name_tokens(right)
    return bool(a) and a == b


# --------------------------------------------------------------------------- parsers
def parse_scopus_author_slots(
    author_ids: str | None, author_full_names: str | None
) -> list[ScopusAuthorSlot]:
    """Parse the Scopus CSV columns ``Author(s) ID`` / ``Author full names``.

    Slot order is the order of ``Author(s) ID``.  Full names are paired by ID
    (``"Name (123)"``), never by position, so a mismatched list cannot
    silently shift names.
    """
    ids = [x.strip() for x in (author_ids or "").split(";") if x.strip()]
    names: dict[str, str] = {}
    for part in (author_full_names or "").split(";"):
        match = re.match(r"^\s*(.*?)\s*\((\d+)\)\s*$", part)
        if match:
            names[match.group(2)] = match.group(1)
    return [ScopusAuthorSlot(sid, i, names.get(sid, "")) for i, sid in enumerate(ids, start=1)]


def _orcid(value: str | None) -> str | None:
    if not value:
        return None
    m = _ORCID_RE.search(value)
    return m.group(1) if m else None


def _openalex_entries(
    authorship: Mapping,
    orgs: tuple[ExternalOrganization, ...],
    raws: tuple[str, ...],
) -> tuple[AffiliationEntry, ...]:
    """Pair each raw string with the institutions OpenAlex attached to it.

    Uses the source's own ``affiliations`` pairing; nothing is inferred.  When
    that pairing is absent, raw strings are kept without organizations and the
    institutions are kept as organization-only entries.
    """
    by_id = {o.source_org_id: o for o in orgs}
    paired = authorship.get("affiliations")
    entries: list[AffiliationEntry] = []
    used: set[str | None] = set()
    if paired:
        for item in paired:
            raw = (item.get("raw_affiliation_string") or "").strip() or None
            ids = [i for i in (item.get("institution_ids") or []) if i in by_id]
            used.update(ids)
            if raw is None and not ids:
                continue
            entries.append(AffiliationEntry(raw, tuple(by_id[i] for i in ids)))
    else:
        entries.extend(AffiliationEntry(r) for r in raws)
    leftovers = tuple(o for o in orgs if o.source_org_id not in used)
    entries.extend(AffiliationEntry(None, (o,)) for o in leftovers)
    return tuple(entries)


def parse_openalex_authorships(work: Mapping) -> list[ExternalAuthorship]:
    out: list[ExternalAuthorship] = []
    for i, a in enumerate(work.get("authorships") or [], start=1):
        author = a.get("author") or {}
        orgs = tuple(
            ExternalOrganization(
                source_org_id=inst.get("id"),
                display_name=inst.get("display_name"),
                ror=inst.get("ror"),
                country_code=inst.get("country_code"),
            )
            for inst in (a.get("institutions") or [])
        )
        raws = tuple(s for s in (a.get("raw_affiliation_strings") or []) if s and s.strip())
        out.append(
            ExternalAuthorship(
                source="openalex",
                position=i,
                display_name=a.get("raw_author_name") or "",
                raw_affiliations=raws,
                organizations=orgs,
                entries=_openalex_entries(a, orgs, raws),
                raw_author_name=a.get("raw_author_name"),
                entity_id=author.get("id"),
                entity_display_name=author.get("display_name"),
                entity_orcid=author.get("orcid"),
            )
        )
    return out


def parse_crossref_authors(work: Mapping) -> list[ExternalAuthorship]:
    out: list[ExternalAuthorship] = []
    for i, a in enumerate(work.get("author") or [], start=1):
        name = " ".join(x for x in (a.get("given"), a.get("family")) if x) or (a.get("name") or "")
        raws = tuple(
            aff["name"].strip() for aff in (a.get("affiliation") or []) if aff.get("name") and aff["name"].strip()
        )
        out.append(
            ExternalAuthorship(
                source="crossref",
                position=i,
                display_name=name,
                orcid=_orcid(a.get("ORCID")),
                raw_affiliations=raws,
                entries=tuple(AffiliationEntry(r) for r in raws),
                raw_author_name=name,
            )
        )
    return out


def parse_orcid_scopus_ids(external_identifiers: Iterable[Mapping] | None) -> frozenset[str]:
    """Scopus Author IDs declared in a public ORCID record's external identifiers."""
    found: set[str] = set()
    for item in external_identifiers or ():
        if (item.get("type") or "").strip().casefold() != "scopus author id":
            continue
        for candidate in (item.get("value"), item.get("url")):
            if candidate:
                m = _SCOPUS_ID_RE.search(str(candidate))
                if m:
                    found.add(m.group(1))
                    break
    return frozenset(found)


# --------------------------------------------------------------------------- alignment
def _link(slot: ScopusAuthorSlot, ext: ExternalAuthorship | None, status: str, **kw) -> AuthorAffiliationLink:
    source = kw.pop("source")
    observation = {
        "source": source,
        "authorship_source": ext.source if ext else None,
        "source_tier": (
            "PUBLISHER" if ext and ext.source == "crossref"
            else "AGGREGATOR_RAW" if ext and ext.source == "openalex" else None
        ),
        "scopus_author_id": slot.scopus_id,
        "author_order": slot.author_order,
        "external_position": ext.position if ext else None,
        "raw_author_name": (ext.raw_author_name or ext.display_name or None) if ext else None,
        "raw_affiliations": list(ext.raw_affiliations) if ext else [],
        "publisher_orcid": ext.orcid if ext and ext.source == "crossref" else None,
        "openalex_author_entity": {
            "id": ext.entity_id,
            "display_name": ext.entity_display_name,
            "orcid": ext.entity_orcid or ext.orcid,
        } if ext and ext.source == "openalex" else None,
    }
    return AuthorAffiliationLink(
        scopus_id=slot.scopus_id,
        author_order=slot.author_order,
        source=source,
        status=status,
        external_position=ext.position if ext else None,
        external_name=ext.display_name if ext else None,
        raw_affiliations=ext.raw_affiliations if ext and status != UNRESOLVED else (),
        organizations=ext.organizations if ext and status != UNRESOLVED else (),
        entries=ext.entries if ext and status != UNRESOLVED else (),
        observation=observation,
        **kw,
    )


def align_paper(
    slots: Sequence[ScopusAuthorSlot],
    externals: Sequence[ExternalAuthorship],
    scopus_ids_by_orcid: Mapping[str, Iterable[str]] | None = None,
    *,
    source: str,
) -> list[AuthorAffiliationLink]:
    """Attribute external authorships to Scopus slots for ONE paper and ONE source."""
    bridge = {k: frozenset(v) for k, v in (scopus_ids_by_orcid or {}).items()}
    paper_ids = {s.scopus_id for s in slots}
    if not externals:
        return [_link(s, None, UNRESOLVED, source=source, reason=R_NO_AUTHOR_LIST) for s in slots]

    # 1. Publisher ORCID -> registry external ID -> Scopus author on this paper.
    # Gate on both the context and authorship: relabeling an OpenAlex observation
    # must not turn an aggregator entity identifier into publisher evidence.
    claims: dict[str, list[tuple[ExternalAuthorship, str]]] = {}
    ambiguous_external: set[int] = set()
    for ext in externals:
        if source != "crossref" or ext.source != "crossref" or not ext.orcid:
            continue
        hits = bridge.get(ext.orcid, frozenset()) & paper_ids
        if len(hits) == 1:
            sid = next(iter(hits))
            claims.setdefault(sid, []).append((ext, f"ORCID:{ext.orcid}->SCOPUS:{sid}"))
        elif len(hits) > 1:
            ambiguous_external.add(ext.position)

    by_id = {s.scopus_id: s for s in slots}
    verified: dict[str, tuple[ExternalAuthorship, str]] = {}
    conflicted: set[str] = set()
    for sid, items in claims.items():
        if len({e.position for e, _ in items}) == 1:
            verified[sid] = items[0]
        else:
            conflicted.add(sid)
    # one external authorship cannot verify two different Scopus IDs
    owners = Counter(e.position for e, _ in verified.values())
    for sid in [s for s, (e, _) in verified.items() if owners[e.position] > 1]:
        del verified[sid]
        conflicted.add(sid)

    same_length = len(slots) == len(externals)
    # a verified link that contradicts the positional alignment invalidates position-based claims
    order_consistent = all(e.position == by_id[sid].author_order for sid, (e, _) in verified.items()) if same_length else False
    claimed_positions = {e.position for e, _ in verified.values()}

    links: list[AuthorAffiliationLink] = []
    for slot in slots:
        sid = slot.scopus_id
        if sid in verified:
            ext, evidence = verified[sid]
            links.append(_link(slot, ext, VERIFIED, source=source, evidence=evidence))
            continue
        if sid in conflicted:
            links.append(_link(slot, None, UNRESOLVED, source=source, reason=R_ID_CONFLICT))
            continue
        if not same_length:
            links.append(_link(slot, None, UNRESOLVED, source=source, reason=R_COUNT_MISMATCH))
            continue
        ext = externals[slot.author_order - 1] if slot.author_order - 1 < len(externals) else None
        if ext is None:
            links.append(_link(slot, None, UNRESOLVED, source=source, reason=R_COUNT_MISMATCH))
        elif ext.source == "openalex" and not ext.display_name.strip():
            links.append(_link(slot, ext, UNRESOLVED, source=source, reason=R_NO_RAW_NAME))
        elif (
            ext.source == "openalex" and ext.entity_display_name
            and not names_match(ext.display_name, ext.entity_display_name)
        ):
            links.append(_link(slot, ext, UNRESOLVED, source=source, reason=R_ENTITY_NAME_CONFLICT))
        elif ext.position in ambiguous_external:
            links.append(_link(slot, ext, UNRESOLVED, source=source, reason=R_ID_AMBIGUOUS))
        elif ext.position in claimed_positions:
            links.append(_link(slot, ext, UNRESOLVED, source=source, reason=R_POSITION_CLAIMED))
        elif not order_consistent:
            links.append(_link(slot, ext, UNRESOLVED, source=source, reason=R_ORDER_INCONSISTENT))
        elif not names_match(slot.full_name, ext.display_name):
            links.append(_link(slot, ext, UNRESOLVED, source=source, reason=R_NAME_MISMATCH))
        else:
            links.append(_link(slot, ext, CORROBORATED, source=source, evidence="POSITION+COUNT+NAME"))
    return links


def unresolved_no_work(slots: Sequence[ScopusAuthorSlot], *, source: str) -> list[AuthorAffiliationLink]:
    return [_link(s, None, UNRESOLVED, source=source, reason=R_NO_EXTERNAL_WORK) for s in slots]


__all__ = [
    "ALIGNMENT_POLICY_VERSION",
    "AffiliationEntry",
    "AuthorAffiliationLink",
    "CORROBORATED",
    "ExternalAuthorship",
    "ExternalOrganization",
    "ScopusAuthorSlot",
    "UNRESOLVED",
    "VERIFIED",
    "align_paper",
    "name_tokens",
    "names_match",
    "parse_crossref_authors",
    "parse_openalex_authorships",
    "parse_orcid_scopus_ids",
    "parse_scopus_author_slots",
    "unresolved_no_work",
]
