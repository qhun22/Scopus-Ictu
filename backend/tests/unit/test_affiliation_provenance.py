"""G02: synthetic source-to-resolution provenance, with no database engine."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import Select

from app.models.affiliation import (
    PublicationAuthorAffiliation,
    PublicationAuthorAffiliationResolution,
)
from app.services import affiliation_sources as sources
from app.services.affiliation_import import (
    AffiliationImportService,
    ResolutionInput,
    apply_cross_source_policy,
)
from app.services.matching.candidate_persistence import canonical_json

ORCID = "0000-0001-0000-0042"
DOI = "10.99999/g02-synthetic"
SID = "11111111111"
EID = "2-s2.0-999000001"
RETRIEVED = "2026-10-29T01:00:00+00:00"
PA_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ROWS = [{"EID": EID, "DOI": DOI, "Author(s) ID": SID,
         "Author full names": f"Alpha, Ann ({SID})"}]


def bundle(directory: Path, *, entity_name="Ann Alpha", publisher=False) -> Path:
    directory.mkdir()
    oa = {"id": "https://openalex.org/W-SYNTHETIC", "authorships": [{
        "raw_author_name": "Ann Alpha",
        "raw_affiliation_strings": ["Raw Faculty A", "Raw Institute B"],
        "author": {"id": "https://openalex.org/A-SYNTHETIC",
                   "display_name": entity_name, "orcid": "https://orcid.org/" + ORCID},
    }]}
    crossref = {"DOI": DOI, "author": [{
        "given": "A.", "family": "Alpha", "ORCID": "https://orcid.org/" + ORCID,
        "affiliation": [{"name": "Publisher Faculty"}],
    }]} if publisher else None
    for source, work in [("openalex", oa), ("crossref", crossref)]:
        record = {"retrieved_at": RETRIEVED, "source": source,
                  "query_doi": DOI, "work": work}
        (directory / f"{source}_works.jsonl").write_text(
            json.dumps(record) + "\n", encoding="utf-8"
        )
    (directory / "orcid_external_ids.json").write_text(json.dumps({ORCID: {
        "retrieved_at": RETRIEVED, "external_identifiers": [
            {"type": "Scopus Author ID", "value": SID, "source": "Synthetic Registry"}
        ],
    }}), encoding="utf-8")
    return directory


@pytest.mark.parametrize("entity_name,status,reason", [
    ("Ann Alpha", "CORROBORATED", None),
    ("Bert Birch", "UNRESOLVED", "OPENALEX_ENTITY_NAME_CONFLICT"),
    (None, "CORROBORATED", None),
])
def test_input_builder_preserves_raw_and_entity_observations(tmp_path, entity_name, status, reason):
    data = sources.build_inputs(bundle(tmp_path / "source", entity_name=entity_name), ROWS)
    item = next(i for i in data.inputs if i.source_system == "openalex")

    assert item.link_status == status and item.unresolved_reason == reason
    assert item.external_author_orcid is None
    observation = item.evidence["source_observation"]
    assert observation["source_tier"] == "AGGREGATOR_RAW"
    assert observation["raw_author_name"] == item.external_author_name == "Ann Alpha"
    assert observation["raw_affiliations"] == ["Raw Faculty A", "Raw Institute B"]
    assert observation["openalex_author_entity"] == {
        "id": "https://openalex.org/A-SYNTHETIC",
        "display_name": entity_name,
        "orcid": "https://orcid.org/" + ORCID,
    }
    assert observation["scopus_author_id"] == SID
    assert observation["author_order"] == observation["external_position"] == 1
    assert observation["source_work_id"] == "https://openalex.org/W-SYNTHETIC"
    assert observation["source_doi"] == DOI and observation["retrieved_at"] == RETRIEVED
    assert observation["publisher_orcid"] is None
    assert bool(item.entries) == (status == "CORROBORATED")


def test_entity_conflict_does_not_veto_independent_publisher_proof(tmp_path):
    data = sources.build_inputs(bundle(tmp_path / "source", entity_name="Bert Birch",
                                      publisher=True), ROWS)
    planned, withheld = apply_cross_source_policy(data.inputs)
    by_source = {item.source_system: item for item in planned}

    assert withheld == set()
    assert by_source["openalex"].unresolved_reason == "OPENALEX_ENTITY_NAME_CONFLICT"
    publisher = by_source["crossref"]
    assert publisher.link_status == "VERIFIED"
    assert publisher.external_author_orcid == ORCID
    assert publisher.evidence["source_observation"]["source_tier"] == "PUBLISHER"
    assert publisher.evidence["source_observation"]["publisher_orcid"] == ORCID
    assert publisher.evidence["orcid"] == ORCID
    assert publisher.evidence["declared_by"] == ["Synthetic Registry"]


def test_count_mismatch_preserves_unassigned_authorship_observations(tmp_path):
    rows = [{**ROWS[0], "Author(s) ID": SID + "; 22222222222",
             "Author full names": f"Alpha, Ann ({SID}); Birch, Bert (22222222222)"}]
    data = sources.build_inputs(bundle(tmp_path / "source", entity_name="Bert Birch"), rows)
    items = [item for item in data.inputs if item.source_system == "openalex"]

    assert len(items) == 2
    for item in items:
        assert item.link_status == "UNRESOLVED" and item.entries == ()
        assert item.unresolved_reason == "AUTHOR_COUNT_MISMATCH"
        observations = item.evidence["source_authorship_observations"]
        assert len(observations) == 1 and observations[0]["position"] == 1
        assert observations[0]["raw_author_name"] == "Ann Alpha"
        assert observations[0]["entity_display_name"] == "Bert Birch"
        assert observations[0]["raw_affiliations"] == ("Raw Faculty A", "Raw Institute B")


def test_withholding_assignment_retains_original_source_observation(tmp_path):
    data = sources.build_inputs(bundle(tmp_path / "source"), ROWS)
    raw = next(item for item in data.inputs if item.source_system == "openalex")
    conflict = ResolutionInput(
        eid=EID, scopus_id=SID, author_order=1, source_system="crossref",
        payload_sha256="c" * 64, link_status="UNRESOLVED", unresolved_reason="ID_CONFLICT",
    )

    planned, withheld = apply_cross_source_policy([raw, conflict])

    assert withheld == {0}
    assert planned[0].link_status == "UNRESOLVED" and planned[0].entries == ()
    assert planned[0].evidence["source_observation"] == raw.evidence["source_observation"]
    assert planned[0].evidence["withheld_link_status"] == "CORROBORATED"
    assert planned[0].evidence["conflicting_sources"] == ["crossref"]


def test_policy_version_distinguishes_new_resolution_from_legacy_payload(tmp_path, monkeypatch):
    directory = bundle(tmp_path / "source", publisher=True)
    first = sources.build_inputs(directory, ROWS)
    again = sources.build_inputs(directory, ROWS)
    assert [i.payload_sha256 for i in first.inputs] == [i.payload_sha256 for i in again.inputs]

    record = json.loads((directory / "crossref_works.jsonl").read_text(encoding="utf-8"))
    legacy_payload = {"source": "crossref", "work": record["work"],
                      "orcid_scopus_ids": {ORCID: [SID]}}
    legacy_hash = hashlib.sha256(canonical_json(legacy_payload).encode("utf-8")).hexdigest()
    publisher = next(i for i in first.inputs if i.source_system == "crossref")
    assert publisher.payload_sha256 != legacy_hash
    assert publisher.evidence["alignment_policy_version"] == sources.ALIGNMENT_POLICY_VERSION

    monkeypatch.setattr(sources, "ALIGNMENT_POLICY_VERSION", "synthetic-next-policy")
    updated = sources.build_inputs(directory, ROWS)
    assert all(a.payload_sha256 != b.payload_sha256
               for a, b in zip(first.inputs, updated.inputs, strict=True))


class _Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def all(self):
        return self.rows

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self.rows)


class _Session:
    """Only compiled SELECT inspection and in-memory model collection; no engine."""

    def __init__(self):
        self.added = []
        self.commits = 0

    def execute(self, statement):
        assert isinstance(statement, Select)
        sql = str(statement).lower()
        if "join scopus_authors" in sql:
            return _Result([(EID, SID, PA_ID, 1, DOI)])
        assert "publication_author_affiliation_resolutions" in sql
        return _Result()

    def add(self, row):
        assert isinstance(row, (
            PublicationAuthorAffiliationResolution, PublicationAuthorAffiliation
        ))
        self.added.append(row)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        raise AssertionError("Unexpected rollback in fake-only provenance test")


def test_observations_reach_resolution_evidence_without_database(tmp_path):
    data = sources.build_inputs(bundle(tmp_path / "source", entity_name="Bert Birch",
                                      publisher=True), ROWS)
    session = _Session()
    report = AffiliationImportService().apply(session, data.inputs)

    resolutions = [r for r in session.added
                   if isinstance(r, PublicationAuthorAffiliationResolution)]
    by_source = {r.source_system: r for r in resolutions}
    assert report.resolutions_to_insert == 2 and session.commits == 1
    assert all(r.publication_author_id == PA_ID for r in resolutions)
    assert by_source["openalex"].link_status == "UNRESOLVED"
    assert by_source["crossref"].link_status == "VERIFIED"
    assert by_source["openalex"].evidence["source_observation"]["raw_author_name"] == "Ann Alpha"
    assert by_source["openalex"].evidence["source_observation"]["openalex_author_entity"][
        "display_name"
    ] == "Bert Birch"
    serialized = json.loads(json.dumps(by_source["openalex"].evidence))
    assert serialized["source_authorship_observations"][0]["raw_affiliations"] == [
        "Raw Faculty A", "Raw Institute B"
    ]
    assignments = [r for r in session.added if isinstance(r, PublicationAuthorAffiliation)]
    assert len(assignments) == 1 and assignments[0].resolution_id == by_source["crossref"].id
