"""Task 11: input building / fail-closed guards of the affiliation importer CLI (synthetic data)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.services.author_affiliation import (
    align_paper,
    parse_crossref_authors,
    parse_openalex_authorships,
    parse_orcid_scopus_ids,
    parse_scopus_author_slots,
    unresolved_no_work,
)
from scripts import generate_matching_candidates as guards
from scripts import import_author_affiliations as cli

ORCID = "0000-0001-0000-0042"
RETRIEVED = "2026-10-09T01:00:00+00:00"


def _openalex(doi: str, names: list[tuple[str, str | None]]) -> dict:
    return {
        "retrieved_at": RETRIEVED,
        "source": "openalex",
        "query_doi": doi,
        "work": {
            "id": f"https://openalex.org/W{abs(hash(doi)) % 1000}",
            "doi": f"https://doi.org/{doi}",
            "authorships": [
                {
                    "author": {"display_name": n, "orcid": f"https://orcid.org/{o}" if o else None},
                    "raw_affiliation_strings": [f"Dept of {n}, Univ X"],
                    "affiliations": [{"raw_affiliation_string": f"Dept of {n}, Univ X", "institution_ids": ["I1"]}],
                    "institutions": [{"id": "I1", "display_name": "Univ X", "ror": None, "country_code": "VN"}],
                }
                for n, o in names
            ],
        },
    }


def _survey(tmp_path: Path, rows: list[dict], works: list[dict]) -> tuple[Path, Path]:
    survey = tmp_path / "survey"
    survey.mkdir()
    csv_path = tmp_path / "scopus.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["EID", "DOI", "Author(s) ID", "Author full names"])
        writer.writeheader()
        writer.writerows(rows)
    (survey / "openalex_works.jsonl").write_text("\n".join(json.dumps(w) for w in works) + "\n", encoding="utf-8")
    (survey / "crossref_works.jsonl").write_text(
        json.dumps({"retrieved_at": RETRIEVED, "source": "crossref", "query_doi": "none", "http": 404}) + "\n", encoding="utf-8"
    )
    (survey / "orcid_external_ids.json").write_text(
        json.dumps({ORCID: {"retrieved_at": RETRIEVED, "http": 200, "external_identifiers": [
            {"type": "Scopus Author ID", "value": "111111", "url": None, "source": "Scopus - Elsevier"}]}}),
        encoding="utf-8",
    )
    # JSONL as the survey tool would produce it: one row per slot per source
    bridge = {ORCID: parse_orcid_scopus_ids([{"type": "Scopus Author ID", "value": "111111"}])}
    by_doi = {w["query_doi"]: w for w in works}
    out = []
    for row in rows:
        slots = parse_scopus_author_slots(row["Author(s) ID"], row["Author full names"])
        doi = row["DOI"].strip().lower() or None
        for source in ("openalex", "crossref"):
            if source == "openalex" and doi in by_doi:
                links = align_paper(slots, parse_openalex_authorships(by_doi[doi]["work"]), bridge, source=source)
            else:
                links = unresolved_no_work(slots, source=source)
            for l in links:
                out.append({"eid": row["EID"], "doi": doi, "scopus_author_id": l.scopus_id, "author_order": l.author_order,
                            "source": source, "link_status": l.status, "unresolved_reason": l.reason, "evidence": l.evidence,
                            "external_position": l.external_position})
    (survey / "author_affiliation_links.jsonl").write_text("\n".join(json.dumps(r) for r in out) + "\n", encoding="utf-8")
    return survey, csv_path


ROWS = [{"EID": "E1", "DOI": "10.1/one", "Author(s) ID": "111111; 222222", "Author full names": "Alpha, Ann (111111); Beta, Bob (222222)"}]
WORKS = [_openalex("10.1/one", [("Ann A.", ORCID), ("Bob Beta", None)])]


def test_inputs_are_rebuilt_from_raw_metadata_and_consistent(tmp_path) -> None:
    survey, csv_path = _survey(tmp_path, ROWS, WORKS)
    built = cli.build_inputs(survey, csv_path)
    assert built.mismatches == [] and built.stats["inputs"] == 4  # 2 authors x 2 sources
    by = {(i.scopus_id, i.source_system): i for i in built.inputs}
    verified = by[("111111", "openalex")]
    assert verified.link_status == "VERIFIED" and verified.external_author_orcid == ORCID
    assert verified.evidence["declared_by"] == ["Scopus - Elsevier"] and verified.link_method == "ORCID_SCOPUS_ID_BRIDGE"
    assert [e.raw_text for e in verified.entries] == ["Dept of Ann A., Univ X"]
    assert verified.entries[0].organization.source_org_id == "I1"
    assert by[("222222", "openalex")].link_status == "CORROBORATED" and by[("222222", "openalex")].evidence["name_tokens_equal"]
    assert by[("111111", "crossref")].link_status == "UNRESOLVED" and not by[("111111", "crossref")].entries
    # payload version is the same for every author of one paper+source and differs between sources
    assert by[("111111", "openalex")].payload_sha256 == by[("222222", "openalex")].payload_sha256
    assert by[("111111", "openalex")].payload_sha256 != by[("111111", "crossref")].payload_sha256


def test_tampered_or_stale_jsonl_is_detected(tmp_path) -> None:
    survey, csv_path = _survey(tmp_path, ROWS, WORKS)
    path = survey / "author_affiliation_links.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    for r in rows:
        if r["scopus_author_id"] == "222222" and r["source"] == "openalex":
            r["link_status"] = "VERIFIED"  # claims a higher confidence than the raw data supports
    rows.append({"eid": "E-GHOST", "scopus_author_id": "9", "source": "openalex", "author_order": 1, "link_status": "VERIFIED",
                 "unresolved_reason": None, "evidence": None, "external_position": 1})
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    built = cli.build_inputs(survey, csv_path)
    assert {(m["eid"], m["scopus_author_id"]) for m in built.mismatches} == {("E1", "222222"), ("E-GHOST", "9")}
    # the tampered claim is never turned into an import input
    assert not any(i.scopus_id == "222222" and i.source_system == "openalex" for i in built.inputs)


def test_duplicate_doi_never_yields_a_trusted_link(tmp_path) -> None:
    rows = ROWS + [{"EID": "E2", "DOI": "10.1/ONE", "Author(s) ID": "111111", "Author full names": "Alpha, Ann (111111)"}]
    survey, csv_path = _survey(tmp_path, rows, WORKS)
    built = cli.build_inputs(survey, csv_path)
    assert built.stats["duplicate_dois"] == 1
    assert not any(i.link_status != "UNRESOLVED" for i in built.inputs)  # ambiguous paper identity -> nothing trusted
    assert built.mismatches  # and the stale JSONL that claims links is flagged


def test_main_refuses_wrong_database_5432_and_missing_manifest(tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    survey, csv_path = _survey(tmp_path, ROWS, WORKS)
    common = ["--survey-dir", str(survey), "--scopus-csv", str(csv_path)]
    monkeypatch.setattr(settings, "db_port", 5432)
    assert cli.main(["--dry-run", *common, "--expected-database", settings.db_name]) == guards.EXIT_REFUSED
    monkeypatch.setattr(settings, "db_port", 55432)
    assert cli.main(["--dry-run", *common, "--expected-database", "some_other_db"]) == guards.EXIT_REFUSED
    assert cli.main(["--apply", *common, "--expected-database", settings.db_name]) == guards.EXIT_REFUSED
    inside_repo = guards.REPO_ROOT / "backend" / "m.json"
    assert cli.main(["--apply", *common, "--expected-database", settings.db_name, "--manifest", str(inside_repo)]) == guards.EXIT_REFUSED


def test_crossref_only_work_stays_corroborated_and_keeps_raw_text(tmp_path) -> None:
    work = {"DOI": "10.1/x", "author": [{"given": "Ann", "family": "Alpha", "affiliation": [{"name": "Univ Crossref"}]}]}
    slots = parse_scopus_author_slots("111111", "Alpha, Ann (111111)")
    link = align_paper(slots, parse_crossref_authors(work), {}, source="crossref")[0]
    assert link.status == "CORROBORATED" and link.evidence == "POSITION+COUNT+NAME"
    assert [e.raw_text for e in cli._entries(link)] == ["Univ Crossref"] and cli._entries(link)[0].organization is None
