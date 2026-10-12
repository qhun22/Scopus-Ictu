"""Author-affiliation source bundle: inspection and input building.

A *bundle* is a directory of metadata downloaded from public sources
(OpenAlex works, Crossref works, ORCID external identifiers) plus, optionally,
the survey tool's own ``author_affiliation_links.jsonl``.  The bundle is the
only thing the affiliation workflow reads from disk, and the directory is fixed
by server configuration (``AFFILIATION_SOURCE_DIR``) - never by a request.

Everything here is pure with respect to the database: Scopus author slots come
from the rows handed in (the CSV rows for the CLI, the stored raw rows for the
ADMIN workflow), links are *recomputed* from the raw bundle metadata with the
committed alignment module, and when the survey tool's JSONL is present every
row must agree with the recomputation (otherwise the input is stale/tampered).

No network access happens here.  Authors without a matching external work get
an UNRESOLVED link (``NO_EXTERNAL_WORK``): a unit is never guessed.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.affiliation_import import EntryInput, OrgInput, ResolutionInput
from app.services.author_affiliation import (
    UNRESOLVED,
    VERIFIED,
    AuthorAffiliationLink,
    align_paper,
    parse_crossref_authors,
    parse_openalex_authorships,
    parse_orcid_scopus_ids,
    parse_scopus_author_slots,
    unresolved_no_work,
)
from app.services.matching.candidate_persistence import canonical_json

SOURCES = ("openalex", "crossref")
REQUIRED_FILES = ("openalex_works.jsonl", "crossref_works.jsonl", "orcid_external_ids.json")
EXPECTED_FILE = "author_affiliation_links.jsonl"
_ORCID_EVIDENCE = re.compile(r"^ORCID:(\d{4}-\d{4}-\d{4}-\d{3}[\dX])->SCOPUS:(\d+)$")


@dataclass(slots=True)
class BuiltInput:
    inputs: list[ResolutionInput]
    stats: dict[str, Any]
    mismatches: list[dict[str, str]] = field(default_factory=list)
    file_sha256: dict[str, str] = field(default_factory=dict)


# ----------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _norm_doi(value: str | None) -> str | None:
    return value.strip().lower() if value and value.strip() else None


def _jsonl(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def entries_of(link: AuthorAffiliationLink) -> tuple[EntryInput, ...]:
    out: list[EntryInput] = []
    raw_index = 0
    for entry in link.entries:
        if entry.raw_text is not None:
            raw_index += 1
        idx = raw_index if entry.raw_text is not None else None
        orgs = entry.organizations or (None,)
        for org in orgs:
            out.append(
                EntryInput(
                    raw_index=idx,
                    raw_text=entry.raw_text,
                    organization=None
                    if org is None
                    else OrgInput(
                        source_system=link.source,
                        source_org_id=org.source_org_id,
                        display_name=org.display_name or "",
                        ror=org.ror,
                        country_code=org.country_code,
                    ),
                )
            )
    return tuple(o for o in out if o.raw_text is not None or o.organization is not None)


# ----------------------------------------------------------------------------
@dataclass(slots=True)
class BundleFile:
    name: str
    required: bool
    present: bool
    size_bytes: int | None = None
    sha256: str | None = None


@dataclass(slots=True)
class BundleStatus:
    configured: bool
    directory_exists: bool
    files: list[BundleFile] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    openalex_works: int | None = None
    crossref_works: int | None = None
    orcid_records: int | None = None
    orcid_with_scopus_id: int | None = None
    retrieved_from: str | None = None
    retrieved_to: str | None = None
    cross_check_available: bool = False

    @property
    def ready(self) -> bool:
        return self.configured and self.directory_exists and not self.problems


def inspect_bundle(directory: Path | None) -> BundleStatus:
    """Describe a bundle without importing anything (cheap enough for a status call)."""

    if directory is None:
        return BundleStatus(configured=False, directory_exists=False, problems=["SOURCE_DIR_NOT_CONFIGURED"])
    status = BundleStatus(configured=True, directory_exists=directory.is_dir())
    if not status.directory_exists:
        status.problems.append("SOURCE_DIR_NOT_FOUND")
        return status
    for name in (*REQUIRED_FILES, EXPECTED_FILE):
        path = directory / name
        required = name in REQUIRED_FILES
        present = path.is_file()
        item = BundleFile(name=name, required=required, present=present)
        if present:
            item.size_bytes = path.stat().st_size
            item.sha256 = sha256_file(path)
        elif required:
            status.problems.append(f"MISSING_{name}")
        status.files.append(item)
    status.cross_check_available = (directory / EXPECTED_FILE).is_file()
    if status.problems:
        return status
    try:
        stamps: list[str] = []
        oa = 0
        for rec in _jsonl(directory / "openalex_works.jsonl"):
            oa += 1 if rec.get("work") else 0
            if rec.get("retrieved_at"):
                stamps.append(str(rec["retrieved_at"]))
        cr = 0
        for rec in _jsonl(directory / "crossref_works.jsonl"):
            cr += 1 if rec.get("work") else 0
            if rec.get("retrieved_at"):
                stamps.append(str(rec["retrieved_at"]))
        orcid = json.loads((directory / "orcid_external_ids.json").read_text(encoding="utf-8"))
        status.openalex_works, status.crossref_works = oa, cr
        status.orcid_records = len(orcid)
        status.orcid_with_scopus_id = sum(
            1 for rec in orcid.values() if parse_orcid_scopus_ids(rec.get("external_identifiers"))
        )
        if stamps:
            status.retrieved_from, status.retrieved_to = min(stamps), max(stamps)
    except (OSError, ValueError, AttributeError, TypeError):
        status.problems.append("BUNDLE_UNREADABLE")
    return status


# ----------------------------------------------------------------------------
def build_inputs(
    bundle_dir: Path,
    rows: Sequence[Mapping[str, str]],
    *,
    require_expected: bool = False,
    strict_cross_check: bool = False,
) -> BuiltInput:
    """Recompute every (Scopus author position, source) link of ``rows``.

    ``rows`` carry the Scopus CSV columns ``EID``, ``DOI``, ``Author(s) ID`` and
    ``Author full names``.  With ``require_expected`` the survey tool's JSONL
    must exist; whenever it exists it must agree with the recomputation.

    ``strict_cross_check`` (the CLI) demands that the JSONL covers exactly the
    given papers: a link without a JSONL row, or a JSONL row for another paper,
    is a mismatch.  The ADMIN workflow runs with it off: the JSONL is then only
    an optional cross-check for the papers it knows (a disagreement is still a
    mismatch); links it does not cover are counted, never trusted more, and
    rows of other papers are ignored - so a bundle prepared for a larger or a
    different CSV does not block an unrelated import.
    """

    sha = {name: sha256_file(bundle_dir / name) for name in REQUIRED_FILES}
    expected_path = bundle_dir / EXPECTED_FILE
    has_expected = expected_path.is_file()
    if require_expected and not has_expected:
        raise FileNotFoundError(EXPECTED_FILE)
    if has_expected:
        sha[EXPECTED_FILE] = sha256_file(expected_path)

    works: dict[str, dict[str, dict]] = {s: {} for s in SOURCES}
    for rec in _jsonl(bundle_dir / "openalex_works.jsonl"):
        if rec.get("work"):
            works["openalex"][rec["query_doi"]] = rec
    crossref_http: dict[str, int] = {}
    for rec in _jsonl(bundle_dir / "crossref_works.jsonl"):
        crossref_http[rec["query_doi"]] = rec.get("http", 0)
        if rec.get("work"):
            works["crossref"][rec["query_doi"]] = rec
    orcid_records = json.loads((bundle_dir / "orcid_external_ids.json").read_text(encoding="utf-8"))
    bridge = {
        o: ids
        for o, rec in orcid_records.items()
        if (ids := parse_orcid_scopus_ids(rec.get("external_identifiers")))
    }
    doi_count = Counter(_norm_doi(r["DOI"]) for r in rows if _norm_doi(r["DOI"]))

    expected: dict[tuple[str, str, str], dict] = {}
    if has_expected:
        for rec in _jsonl(expected_path):
            expected[(rec["eid"], rec["scopus_author_id"], rec["source"])] = rec

    inputs: list[ResolutionInput] = []
    mismatches: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    covered = {s: 0 for s in SOURCES}
    covered_any = without_doi = duplicate_doi = 0
    cross_matched = cross_uncovered = 0
    for row in rows:
        eid = row["EID"].strip()
        doi = _norm_doi(row["DOI"])
        slots = parse_scopus_author_slots(row["Author(s) ID"], row["Author full names"])
        found_any = False
        if doi is None:
            without_doi += 1
        elif doi_count[doi] > 1:
            duplicate_doi += 1
        for source in SOURCES:
            record = works[source].get(doi) if doi and doi_count[doi] == 1 else None
            if record is None:
                reason = "DUPLICATE_DOI_IN_SOURCE" if doi and doi_count[doi] > 1 else None
                links = unresolved_no_work(slots, source=source)
                if reason:
                    links = [
                        AuthorAffiliationLink(l.scopus_id, l.author_order, source, UNRESOLVED, reason=reason)
                        for l in links
                    ]
                payload = {"source": source, "query_doi": doi, "result": "none",
                           "http": crossref_http.get(doi) if source == "crossref" and doi else None}
                retrieved = work_id = None
                externals: list = []
            else:
                covered[source] += 1
                found_any = True
                work = record["work"]
                externals = (
                    parse_openalex_authorships(work) if source == "openalex" else parse_crossref_authors(work)
                )
                links = align_paper(slots, externals, bridge, source=source)
                orcids = sorted({e.orcid for e in externals if e.orcid})
                payload = {
                    "source": source,
                    "work": work,
                    "orcid_scopus_ids": {o: sorted(bridge.get(o, ())) for o in orcids},
                }
                retrieved = datetime.fromisoformat(record["retrieved_at"])
                work_id = work.get("id") if source == "openalex" else work.get("DOI")
            payload_sha = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
            n_slots, n_ext = len(slots), len(externals)
            for link in links:
                key = (eid, link.scopus_id, source)
                seen_keys.add(key)
                if has_expected:
                    exp = expected.get(key)
                    if exp is None and not strict_cross_check:
                        cross_uncovered += 1
                    elif (
                        exp is None
                        or exp["link_status"] != link.status
                        or exp["unresolved_reason"] != link.reason
                        or exp["external_position"] != link.external_position
                        or exp["evidence"] != link.evidence
                    ):
                        mismatches.append({"eid": eid, "scopus_author_id": link.scopus_id, "source": source})
                        continue
                    else:
                        cross_matched += 1
                evidence: dict[str, Any] = {}
                orcid = None
                if link.status == VERIFIED:
                    m = _ORCID_EVIDENCE.match(link.evidence or "")
                    orcid = m.group(1) if m else None
                    record_info = orcid_records.get(orcid or "", {})
                    declared_by = sorted(
                        {
                            i.get("source")
                            for i in (record_info.get("external_identifiers") or [])
                            if (i.get("type") or "").casefold() == "scopus author id" and i.get("source")
                        }
                    )
                    evidence = {
                        "orcid": orcid,
                        "scopus_id_declared_in_orcid_record": link.scopus_id,
                        "orcid_record_retrieved_at": record_info.get("retrieved_at"),
                        "declared_by": declared_by,
                    }
                elif link.status != UNRESOLVED:
                    evidence = {"scopus_author_count": n_slots, "external_author_count": n_ext,
                                "name_tokens_equal": True, "same_position": True}
                inputs.append(
                    ResolutionInput(
                        eid=eid,
                        scopus_id=link.scopus_id,
                        author_order=link.author_order,
                        source_system=source,
                        payload_sha256=payload_sha,
                        link_status=link.status,
                        doi=doi,
                        link_method=None
                        if link.status == UNRESOLVED
                        else ("ORCID_SCOPUS_ID_BRIDGE" if link.status == VERIFIED else "POSITION_COUNT_NAME"),
                        unresolved_reason=link.reason,
                        evidence=evidence,
                        source_doi=doi if record is not None else None,
                        source_work_id=work_id,
                        external_position=link.external_position,
                        external_author_name=link.external_name,
                        external_author_orcid=orcid,
                        retrieved_at=retrieved if link.status != UNRESOLVED else None,
                        entries=entries_of(link) if link.status != UNRESOLVED else (),
                    )
                )
        covered_any += 1 if found_any else 0
    if has_expected and strict_cross_check:
        for eid, sid, source in sorted(set(expected) - seen_keys):
            mismatches.append({"eid": eid, "scopus_author_id": sid, "source": source, "problem": "ROW_NOT_IN_SCOPUS_CSV"})
    stats = {
        "papers": len(rows),
        "author_slots": sum(len(parse_scopus_author_slots(r["Author(s) ID"], r["Author full names"])) for r in rows),
        "inputs": len(inputs),
        "jsonl_rows": len(expected),
        "duplicate_dois": sum(1 for n in doi_count.values() if n > 1),
        "orcid_records": len(orcid_records),
        "orcid_with_scopus_id": len(bridge),
        "papers_without_doi": without_doi,
        "papers_with_duplicate_doi": duplicate_doi,
        "papers_with_openalex_work": covered["openalex"],
        "papers_with_crossref_work": covered["crossref"],
        "papers_with_any_work": covered_any,
        "papers_without_any_work": len(rows) - covered_any,
        "cross_check_against_survey_jsonl": has_expected,
        "cross_check_links_matched": cross_matched,
        "cross_check_links_not_covered": cross_uncovered,
    }
    return BuiltInput(inputs, stats, mismatches, sha)


__all__ = [
    "BuiltInput",
    "BundleFile",
    "BundleStatus",
    "EXPECTED_FILE",
    "REQUIRED_FILES",
    "SOURCES",
    "build_inputs",
    "entries_of",
    "inspect_bundle",
    "sha256_file",
]
