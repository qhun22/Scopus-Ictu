"""Import author-level affiliation resolutions from the Task 10 survey files.

The survey directory (kept OUTSIDE Git) holds the downloaded OpenAlex /
Crossref / ORCID metadata and ``author_affiliation_links.jsonl``.  This CLI

* rebuilds every link from the RAW metadata with the committed alignment module,
* requires each JSONL row to agree with that recomputation (otherwise it
  refuses to apply: stale or tampered input),
* hands the result to ``AffiliationImportService`` (preview / apply).

It writes only the three affiliation tables; it never creates Scopus authors,
publication authors, identities or candidates.

Usage (from ``backend/``; DB_* variables as for the app)::

    python -m scripts.import_author_affiliations --dry-run --survey-dir <dir> \\
        --scopus-csv <csv> --expected-database <db> --expected-port <port>
    python -m scripts.import_author_affiliations --apply   ... --manifest <outside-repo>.json

Exit codes: 0 ok, 2 refused by a guard / input mismatch, 5 failure.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.services.affiliation_import import (
    AffiliationImportService,
    EntryInput,
    OrgInput,
    ResolutionInput,
)
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
from scripts.generate_matching_candidates import (
    EXIT_OK,
    EXIT_PERSIST_FAILED,
    CliRefused,
    make_read_only_engine,
    validate_manifest_path,
    validate_target_url,
    verify_server_identity,
)

SURVEY_FILES = (
    "openalex_works.jsonl",
    "crossref_works.jsonl",
    "orcid_external_ids.json",
    "author_affiliation_links.jsonl",
)
SOURCES = ("openalex", "crossref")
_ORCID_EVIDENCE = re.compile(r"^ORCID:(\d{4}-\d{4}-\d{4}-\d{3}[\dX])->SCOPUS:(\d+)$")


@dataclass(slots=True)
class BuiltInput:
    inputs: list[ResolutionInput]
    stats: dict[str, Any]
    mismatches: list[dict[str, str]] = field(default_factory=list)
    file_sha256: dict[str, str] = field(default_factory=dict)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _norm_doi(value: str | None) -> str | None:
    return value.strip().lower() if value and value.strip() else None


def _jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def _entries(link: AuthorAffiliationLink) -> tuple[EntryInput, ...]:
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


def build_inputs(survey_dir: Path, scopus_csv: Path) -> BuiltInput:
    sha = {name: _sha(survey_dir / name) for name in SURVEY_FILES}
    sha["scopus_csv"] = _sha(scopus_csv)
    rows = list(csv.DictReader(scopus_csv.open(encoding="utf-8-sig", newline="")))
    works: dict[str, dict[str, dict]] = {s: {} for s in SOURCES}
    for rec in _jsonl(survey_dir / "openalex_works.jsonl"):
        works["openalex"][rec["query_doi"]] = rec
    crossref_http: dict[str, int] = {}
    for rec in _jsonl(survey_dir / "crossref_works.jsonl"):
        crossref_http[rec["query_doi"]] = rec.get("http", 0)
        if rec.get("work"):
            works["crossref"][rec["query_doi"]] = rec
    orcid_records = json.loads((survey_dir / "orcid_external_ids.json").read_text(encoding="utf-8"))
    bridge = {
        o: ids
        for o, rec in orcid_records.items()
        if (ids := parse_orcid_scopus_ids(rec.get("external_identifiers")))
    }
    doi_count = Counter(_norm_doi(r["DOI"]) for r in rows if _norm_doi(r["DOI"]))

    expected: dict[tuple[str, str, str], dict] = {}
    for rec in _jsonl(survey_dir / "author_affiliation_links.jsonl"):
        expected[(rec["eid"], rec["scopus_author_id"], rec["source"])] = rec

    inputs: list[ResolutionInput] = []
    mismatches: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for row in rows:
        eid = row["EID"].strip()
        doi = _norm_doi(row["DOI"])
        slots = parse_scopus_author_slots(row["Author(s) ID"], row["Author full names"])
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
            else:
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
            n_slots, n_ext = len(slots), (len(externals) if record is not None else 0)
            for link in links:
                key = (eid, link.scopus_id, source)
                seen_keys.add(key)
                exp = expected.get(key)
                if (
                    exp is None
                    or exp["link_status"] != link.status
                    or exp["unresolved_reason"] != link.reason
                    or exp["external_position"] != link.external_position
                    or exp["evidence"] != link.evidence
                ):
                    mismatches.append({"eid": eid, "scopus_author_id": link.scopus_id, "source": source})
                    continue
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
                        entries=_entries(link) if link.status != UNRESOLVED else (),
                    )
                )
    extra = set(expected) - seen_keys
    for eid, sid, source in sorted(extra):
        mismatches.append({"eid": eid, "scopus_author_id": sid, "source": source, "problem": "ROW_NOT_IN_SCOPUS_CSV"})
    stats = {
        "papers": len(rows),
        "author_slots": sum(len(parse_scopus_author_slots(r["Author(s) ID"], r["Author full names"])) for r in rows),
        "inputs": len(inputs),
        "jsonl_rows": len(expected),
        "duplicate_dois": sum(1 for n in doi_count.values() if n > 1),
        "orcid_records": len(orcid_records),
        "orcid_with_scopus_id": len(bridge),
    }
    return BuiltInput(inputs, stats, mismatches, sha)


def _identity_report(reader, database: str, port: int | None) -> dict[str, Any]:
    return verify_server_identity(reader, database, port)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.import_author_affiliations")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--survey-dir", type=Path, required=True)
    p.add_argument("--scopus-csv", type=Path, required=True)
    p.add_argument("--expected-database", required=True)
    p.add_argument("--expected-port", type=int, default=None)
    p.add_argument("--manifest", type=Path, default=None)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from app.core.config import settings

        url = URL.create("postgresql+psycopg2", username=settings.db_user, password=settings.db_password,
                         host=settings.db_host, port=settings.db_port, database=settings.db_name)
        validate_target_url(url, args.expected_database, args.expected_port)
        manifest_path = validate_manifest_path(args.manifest) if args.manifest else None
        if args.apply and manifest_path is None:
            raise CliRefused("--apply requires --manifest (stored outside the repository)")
        built = build_inputs(args.survey_dir, args.scopus_csv)
        reader = make_read_only_engine(url)
        ident = _identity_report(reader, args.expected_database, args.expected_port)
        print(f"target: database={ident['database']} port={ident['port']} addr={ident['address']}")
        with Session(reader) as session:
            if session.execute(text("show transaction_read_only")).scalar_one() != "on":
                raise CliRefused("reader session is not read-only")
            report = AffiliationImportService().preview(session, built.inputs)
            session.rollback()
        summary = {"input": built.stats, "source_mismatches": len(built.mismatches), "preview": report.as_dict()}
        if args.dry_run:
            print(json.dumps({"mode": "dry-run", **summary}, sort_keys=True))
            return EXIT_OK
        if built.mismatches:
            raise CliRefused(f"{len(built.mismatches)} JSONL rows disagree with the recomputation from raw metadata")
        writer = create_engine(url, pool_pre_ping=True)
        try:
            verify_server_identity(writer, args.expected_database, args.expected_port)
            with Session(writer) as session:  # fresh session, no prior statements
                applied = AffiliationImportService().apply(session, built.inputs)
        finally:
            writer.dispose()
        manifest = {"schema_version": 1, "database": args.expected_database, "source_files": built.file_sha256,
                    "input": built.stats, "result": applied.as_dict()}
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"mode": "apply", "result": applied.as_dict()}, sort_keys=True))
        return EXIT_OK
    except CliRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}", file=sys.stderr)
        return EXIT_PERSIST_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
