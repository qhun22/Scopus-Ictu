"""Gate E.3 / P2-A — pure adapters from real ICTU capture formats to the E3-P1 contract.

Synthetic fixtures only. They copy the *structure* of the real Craw harvest and Scopus-guide
snapshots (field names, nesting, label texts, the trailing link icon on ORCID labels), never
their values: reserved ``example.invalid`` domains, fake 570000000xx Scopus IDs, ORCID's own
documentation iDs and placeholder personal values. No database, configuration or network.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema  # mandatory: the schema-parity guarantee must not silently skip
import pytest

from app.services.source_claims import adapters, analysis
from app.services.source_claims.adapters import AdapterError
from app.services.source_claims.analysis import PresenceStatus as P
from app.services.source_claims.contract import (
    ClaimType,
    KeyMethod,
    KeyStrength,
    RecordKind,
    ValidationStatus,
)
from app.services.source_claims.parser import parse_artifact, parse_artifact_bytes

BACKEND = Path(__file__).resolve().parents[2]
SCHEMA = BACKEND.parent / "data" / "source_claims" / "schema" / "ictu_source_claims.schema.json"
ORCID_A = "0000-0002-1825-0097"
ORCID_B = "0000-0001-5109-3700"
SHA = "a" * 64
REPO = "https://repository.example.invalid"
GUIDE_URL = f"{REPO}/huong-dan-gop-tai-khoan-scopus/"
PERSONAL = {"Ngày sinh": "01/01/1900", "Giới tính": "SYNTHETIC-GENDER",
            "Điện thoại": "0999000111"}


def sid(n: int) -> str:
    return str(57000000000 + n)


def lecturer(n, *, orcid=None, pubs=0, name=None, email=None, retrieved="2026-10-03T18:44:10Z"):
    url = f"{REPO}/giang-vien/synthetic-{n}/"
    name = name or f"Synthetic Lecturer {n}"
    email = email or f"lecturer{n}@example.invalid"
    links = [f"{REPO}/items/{n}-{i}" for i in range(pubs)]
    labels = {"Họ và tên": name, "Email": email, "Học vị": "Tiến sĩ", **PERSONAL}
    if orcid:
        labels["ORCID"] = f"{orcid} ↗"
    counts = {"article_count": pubs}
    return {
        "source_id": url, "source_display_name": f"TS. {name}", "full_name": name,
        "institutional_email": email, "academic_degree": "Tiến sĩ", "academic_rank": None,
        "position": None, "faculty": None, "department": None, "specialisation": None,
        "profile_url": url, "orcid": orcid,
        "orcid_url": f"https://orcid.org/{orcid}" if orcid else None,
        "google_scholar_url": None, "public_publication_links": links, "is_active": True,
        "provenance": {"source_url": url, "retrieved_at": retrieved,
                       "content_sha256": hashlib.sha256(url.encode()).hexdigest(),
                       "parser_version": "ictu_harvester/1.2",
                       "source_field_catalog": {label: 1 for label in labels},
                       "snapshot_path": f"snapshots/synthetic-{n}.html",
                       "snapshot_status_code": 200},
        "source": {"display_name": f"TS. {name}", "institutional_email": email, "orcid": orcid,
                   "category_counts": counts, "linked_records": links},
        "normalized": {"full_name": name, "institutional_email": email, "orcid": orcid},
        "extra_fields": dict(PERSONAL),
        "source_fields": labels,
        "observed_labels": sorted(labels), "preserved_labels": sorted(labels), "lost_labels": [],
        "counts": counts,
        "discovery_source": {"method": "lecturer_archive_card",
                             "archive_url": f"{REPO}/giang-vien/"},
    }


LECTURERS_SEMANTIC_HASH = "b" * 64


def manifest(cards, *, completed="2026-10-03T21:31:10Z", drift=False, lecturers=None,
             status="COMPLETE"):
    return {"harvest_started_at": "2026-10-03T20:05:14Z", "harvest_completed_at": completed,
            "source_base_url": REPO, "parser_version": "ictu_harvester/1.4-full",
            "source_card_count": cards,
            "lecturer_count": cards if lecturers is None else lecturers,
            "status": status, "source_drift_detected": drift,
            "semantic_file_hashes": {"lecturers.json": LECTURERS_SEMANTIC_HASH}}


def report(*failure_types):
    return {"source_entity_failures": [{"entity_type": t} for t in failure_types],
            "duplicate_profile_url_count": 0}


def replay(ok=True, lecturers_hash=LECTURERS_SEMANTIC_HASH):
    """Shape of Craw's semantic_replay.json: three passes over the same harvest state."""
    runs = ("A_cached_write", "B_cached_replay", "C_offline_replay")
    return {"a_equals_b_equals_c": ok, "combined_hash": "e" * 64,
            "file_hashes": {run: {"lecturers.json": lecturers_hash} for run in runs}}


def harvester_status(crawl):
    """What the harvester writes: COMPLETE, or COMPLETE_WITH_SOURCE_FAILURES if anything failed."""
    failures = crawl.get("source_entity_failures") if isinstance(crawl, dict) else None
    return "COMPLETE_WITH_SOURCE_FAILURES" if failures else "COMPLETE"


_DEFAULT = object()


def harvest(items, cards=None, *, crawl=None, semantic=_DEFAULT, **manifest_kwargs):
    cards = len(items) if cards is None else cards
    crawl = report("master_thesis") if crawl is None else crawl
    manifest_kwargs.setdefault("status", harvester_status(crawl))
    return adapters.profiles_artifact(items, manifest(cards, **manifest_kwargs), crawl,
                                      replay() if semantic is _DEFAULT else semantic,
                                      lecturers_sha256=SHA)


HEADER = ["Tên trên Scopus", "Scopus ID", "Số bài"]
HEADINGS = {"1": "Scopus ID nhập nhằng cần xác nhận chủ sở hữu — synthetic section",
            "2": "Scopus ID chưa xác định chủ sở hữu thuộc ICTU — synthetic section"}


def tables_snapshot(ambiguous=(), unassigned=(), *, ts="2026-10-29T01:37:29.388Z"):
    return {"ts": ts, "url": GUIDE_URL, "sha256": "c" * 64, "capture_note": "synthetic",
            "n_tables_total": 3, "section_headings": dict(HEADINGS),
            "page_summary_text": "synthetic summary",
            "tables": [{"ti": 1, "heading": "", "rows": [list(HEADER), *map(list, ambiguous)]},
                       {"ti": 2, "heading": "", "rows": [list(HEADER), *map(list, unassigned)]}]}


def rows_snapshot(rows, *, ts="2026-10-29T00:32:28.817Z", stated=None):
    return {"ts": ts, "url": GUIDE_URL, "title": "Synthetic guide page", "total_tr": 99,
            "multi_id_rows": len(rows) if stated is None else stated, "rows_sha256": "d" * 64,
            "capture_note": "synthetic", "rows": [list(r) for r in rows]}


def multi_row(n, ids, primary=None):
    return [f"GV {n}", f"gv{n}@example.invalid", str(len(ids)), "3", primary or ids[0],
            "; ".join(ids)]


def guide(snapshot, completeness="COMPLETE", **kwargs):
    return adapters.guide_tables_artifact(snapshot, snapshot_sha256=SHA,
                                          completeness=completeness, **kwargs)


def multi(snapshot, completeness="PARTIAL", **kwargs):
    return adapters.guide_multi_id_artifact(snapshot, snapshot_sha256=SHA,
                                            completeness=completeness, **kwargs)


def claims_of(snapshot, claim_type):
    return [c for c in snapshot.claims if c.claim_type is claim_type]


def codes(record):
    return {issue.code for issue in record.issues}


def entry(report_, dimension, key):
    found = [e for e in report_.entries if e.dimension == dimension and e.key == key]
    assert len(found) == 1, (dimension, key)
    return found[0]


# ---------------------------------------------------------------------------
# Profiles: actual Craw format
# ---------------------------------------------------------------------------

def test_every_profile_is_kept_including_those_without_publications():
    snap = parse_artifact(harvest([lecturer(1, orcid=ORCID_A, pubs=2), lecturer(2),
                                   lecturer(3)]))
    assert len(snap.records) == 3 and snap.completeness.value == "COMPLETE"
    assert [r.raw["public_publication_links"] for r in snap.records][1:] == [[], []]
    assert {r.record_key.method for r in snap.records} == {KeyMethod.PROFILE_SOURCE_ID_V1}
    assert {r.record_key.strength for r in snap.records} == {KeyStrength.STRONG}
    assert len(claims_of(snap, ClaimType.EMAIL_DECLARED)) == 3
    assert len(claims_of(snap, ClaimType.ORCID_DECLARED)) == 1
    assert dict(snap.declared_counts) == {"PROFILES": 3} and snap.issues == ()


def test_institutional_email_is_mapped_and_raw_labels_are_kept_verbatim():
    artifact = harvest([lecturer(1, orcid=ORCID_A)])
    profile = artifact["content"]["profiles"][0]
    assert "institutional_email" not in profile
    assert profile["email"] == "lecturer1@example.invalid"
    assert profile["source_fields"]["ORCID"] == f"{ORCID_A} ↗"
    snap = parse_artifact(artifact)
    orcid, = claims_of(snap, ClaimType.ORCID_DECLARED)
    assert orcid.value.valid and orcid.value.raw == ORCID_A
    assert snap.records[0].validation_status is ValidationStatus.VALID


def test_personal_fields_never_reach_the_artifact():
    artifact = harvest([lecturer(1), lecturer(2)])
    text = adapters.artifact_bytes(artifact).decode("utf-8")
    for value in PERSONAL.values():
        assert value not in text
    assert "extra_fields" not in text.split('"capture"')[0]
    assert artifact["capture"]["excluded"] == {
        "field:extra_fields": 2, "source_field_label:Giới tính": 2,
        "source_field_label:Ngày sinh": 2, "source_field_label:Điện thoại": 2}


def test_observation_metadata_goes_to_capture_not_content():
    artifact = harvest([lecturer(1)])
    profile = artifact["content"]["profiles"][0]
    assert not set(profile) & set(adapters.PROFILE_CAPTURE_FIELDS + adapters.PROFILE_DERIVED_FIELDS)
    observation, = artifact["capture"]["observations"]
    assert observation["position"] == 1 and "provenance" in observation
    assert artifact["capture"]["upstream"]["bytes_sha256"] == SHA


def test_unclassified_profile_field_fails_closed():
    item = lecturer(1)
    item["home_address"] = "synthetic"
    with pytest.raises(AdapterError) as raised:
        harvest([item])
    assert raised.value.code == "UNMAPPED_PROFILE_FIELD"


def test_names_are_never_keys():
    same = [lecturer(1, name="Nguyễn Văn Nam"), lecturer(2, name="Nguyễn Văn Nam")]
    snap = parse_artifact(harvest(same))
    assert len({r.record_key.value for r in snap.records}) == 2
    no_ids = [{k: v for k, v in lecturer(n, name="Nguyễn Văn Nam").items()
               if k not in ("source_id", "institutional_email")} for n in (1, 2)]
    for item in no_ids:
        item["source_fields"].pop("Email")
    weak = parse_artifact(harvest(no_ids))
    assert {r.record_key.method for r in weak.records} == {KeyMethod.CONTENT_V1}
    assert all("nam" not in r.record_key.value for r in weak.records)


# ---------------------------------------------------------------------------
# Replay, reordering and idempotency inputs for P2 REUSED
# ---------------------------------------------------------------------------

def test_same_content_recaptured_keeps_content_hash_and_changes_capture_hash():
    first = parse_artifact(harvest([lecturer(1), lecturer(2)]))
    later = parse_artifact(harvest([lecturer(1, retrieved="2026-11-03T08:00:00Z"),
                                    lecturer(2, retrieved="2026-11-03T08:00:01Z")],
                                   completed="2026-11-03T09:00:00Z"))
    assert first.content_hash == later.content_hash
    assert first.records == later.records and first.claims == later.claims
    assert first.capture.capture_hash != later.capture.capture_hash


def test_identical_upstream_gives_identical_artifact_bytes():
    items = [lecturer(1, orcid=ORCID_A, pubs=1), lecturer(2)]
    one = adapters.artifact_bytes(harvest(copy.deepcopy(items)))
    two = adapters.artifact_bytes(harvest(copy.deepcopy(items)))
    assert one == two
    by_bytes = parse_artifact_bytes(one)
    assert by_bytes.artifact_bytes_sha256 == hashlib.sha256(one).hexdigest()
    assert by_bytes.content_hash == parse_artifact(json.loads(one)).content_hash


def test_reordered_equivalent_json_objects_hash_identically():
    items = [lecturer(1, orcid=ORCID_A), lecturer(2)]
    reordered = json.loads(json.dumps(items), object_pairs_hook=lambda p: dict(reversed(p)))
    assert list(reordered[0]) != list(items[0])
    assert adapters.artifact_bytes(harvest(items)) == adapters.artifact_bytes(harvest(reordered))


def test_profile_order_changes_positions_not_record_hashes():
    one = parse_artifact(harvest([lecturer(1), lecturer(2)]))
    swapped = parse_artifact(harvest([lecturer(2), lecturer(1)]))
    assert {r.record_hash for r in one.records} == {r.record_hash for r in swapped.records}
    assert one.content_hash != swapped.content_hash  # source order is part of the assertion


# ---------------------------------------------------------------------------
# Collisions, counts, completeness, malformed input
# ---------------------------------------------------------------------------

def test_orcid_collision_keeps_both_profiles_and_claims():
    snap = parse_artifact(harvest([lecturer(1, orcid=ORCID_B), lecturer(2, orcid=ORCID_B)]))
    group, = analysis.orcid_collision_groups(snap)
    assert group.record_refs == ("PROFILE#1", "PROFILE#2")
    assert len(claims_of(snap, ClaimType.ORCID_DECLARED)) == 2


@pytest.mark.parametrize(("kwargs", "crawl", "expected"), [
    ({}, report("master_thesis"), "COMPLETE"),
    ({}, report(), "COMPLETE"),
    ({"cards": 4}, report(), "PARTIAL"),                 # a listed profile is missing
    ({"drift": True}, report(), "PARTIAL"),
    ({}, report("lecturer"), "PARTIAL"),
    ({}, {}, "PARTIAL"),                                 # failures not reported
])
def test_completeness_is_proven_from_the_harvest(kwargs, crawl, expected):
    artifact = harvest([lecturer(1), lecturer(2), lecturer(3)], crawl=crawl, **kwargs)
    assert artifact["capture"]["completeness"] == expected


# ---------------------------------------------------------------------------
# P2A-S2: completeness fails closed on the harvest's own success evidence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("status", "failures", "expected"), [
    ("COMPLETE", (), "COMPLETE"),
    ("COMPLETE_WITH_SOURCE_FAILURES", ("master_thesis",), "COMPLETE"),
    ("COMPLETE_WITH_SOURCE_FAILURES", ("publication_listing", "project"), "COMPLETE"),
    ("COMPLETE_WITH_SOURCE_FAILURES", ("lecturer",), "PARTIAL"),   # a profile fetch failed
    ("COMPLETE", ("master_thesis",), "PARTIAL"),                    # status contradicts failures
    ("COMPLETE_WITH_SOURCE_FAILURES", (), "PARTIAL"),               # status contradicts failures
    ("FAILED", (), "PARTIAL"),                                       # not a success status
    ("BLOCKED", (), "PARTIAL"),
    (None, (), "PARTIAL"),
])
def test_harvest_status_must_be_a_consistent_success(status, failures, expected):
    artifact = harvest([lecturer(1), lecturer(2)], crawl=report(*failures), status=status)
    capture = artifact["capture"]
    assert capture["completeness"] == expected
    assert capture["completeness_basis"]["manifest_status"] == status


def test_failed_status_with_matching_zero_counts_is_partial():
    """The reviewer's counterexample: counts agree, no drift, no failures, status FAILED."""
    artifact = harvest([], cards=0, crawl=report(), status="FAILED")
    assert artifact["capture"]["completeness"] == "PARTIAL"


@pytest.mark.parametrize(("semantic", "reason"), [
    (None, "no replay report"),
    (replay(ok=False), "replay mismatch: the harvester ends such a run BLOCKED"),
    (replay(lecturers_hash="f" * 64), "replay of a different lecturers file"),
    ({"a_equals_b_equals_c": True, "file_hashes": {}}, "replay without file hashes"),
])
def test_success_status_without_verified_replay_is_partial(semantic, reason):
    artifact = harvest([lecturer(1)], crawl=report(), semantic=semantic)
    assert artifact["capture"]["completeness_basis"]["manifest_status"] == "COMPLETE"
    assert artifact["capture"]["completeness"] == "PARTIAL", reason
    assert artifact["capture"]["completeness_basis"]["semantic_replay_verified"] is False


def test_failed_harvest_never_authorizes_withdrawal():
    before = parse_artifact(harvest([lecturer(1), lecturer(2)]))
    failed = parse_artifact(harvest([lecturer(1)], crawl=report(), status="FAILED",
                                    completed="2026-11-03T09:00:00Z"))
    blocked = parse_artifact(harvest([lecturer(1)], crawl=report(), semantic=replay(ok=False),
                                     completed="2026-11-03T09:00:00Z"))
    key = f"{REPO}/giang-vien/synthetic-2"
    for after in (failed, blocked):
        report_ = analysis.presence_diff(before, after)
        assert not report_.comparable and report_.by_status(P.WITHDRAWN) == ()
        assert entry(report_, "RECORD:PROFILE", key).status is P.NOT_OBSERVED


def test_semantic_replay_must_be_an_object():
    with pytest.raises(AdapterError) as raised:
        adapters.profiles_artifact([lecturer(1)], manifest(1), report(), ["not", "a", "report"],
                                   lecturers_sha256=SHA)
    assert raised.value.code == "SEMANTIC_REPLAY_INVALID"


# ---------------------------------------------------------------------------
# P2A-S1: contract version is part of artifact identity, not of content or capture
# ---------------------------------------------------------------------------

def _versions(*versions):
    base = harvest([lecturer(1, orcid=ORCID_A), lecturer(2)])
    snaps = []
    for version in versions:
        artifact = copy.deepcopy(base)
        artifact["contract_version"] = version
        snaps.append(parse_artifact_bytes(adapters.artifact_bytes(artifact)))
    return snaps


def test_contract_minor_versions_share_content_and_capture_but_not_artifact():
    v10, v11 = _versions("1.0", "1.1")
    assert v10.content_hash == v11.content_hash
    assert v10.capture.capture_hash == v11.capture.capture_hash
    assert v10.artifact_bytes_sha256 != v11.artifact_bytes_sha256
    k10, k11 = adapters.staging_keys(v10), adapters.staging_keys(v11)
    assert k10["content"] == k11["content"] and k10["capture"] == k11["capture"]
    assert k10["artifact"] != k11["artifact"]


def test_proposed_unique_keys_keep_both_contract_versions():
    """Simulates the revised schema's UNIQUE constraints with sets."""
    contents, captures, artifacts = set(), set(), set()
    old_capture_unique = set()  # superseded proposal: UNIQUE(content_id, capture_hash)
    snaps = _versions("1.0", "1.1", "1.0")  # the third is a re-ingest of the first
    for snap in snaps:
        keys = adapters.staging_keys(snap)
        contents.add(keys["content"])
        captures.add(keys["capture"])
        artifacts.add(keys["artifact"])
        old_capture_unique.add(keys["capture"])
    assert (len(contents), len(captures), len(artifacts)) == (1, 1, 2)
    assert len(old_capture_unique) == 1             # the old design would have kept only one


def test_artifact_bytes_are_rebuilt_only_with_the_stored_contract_version():
    v10, v11 = _versions("1.0", "1.1")
    for snap, other in ((v10, v11), (v11, v10)):
        def rebuilt(version, s=snap):
            return hashlib.sha256(adapters.reconstruct_artifact_bytes(
                source_system=s.source_system.value, contract_version=version,
                capture_json=s.capture.capture_json, content_json=s.content_json)).hexdigest()
        assert rebuilt(snap.contract_version) == snap.artifact_bytes_sha256
        assert rebuilt(other.contract_version) == other.artifact_bytes_sha256
        assert rebuilt(other.contract_version) != snap.artifact_bytes_sha256


def test_staging_keys_require_canonical_artifact_bytes():
    artifact = harvest([lecturer(1)])
    with pytest.raises(AdapterError) as raised:
        adapters.staging_keys(parse_artifact(artifact))           # dict input: no byte identity
    assert raised.value.code == "ARTIFACT_BYTES_REQUIRED"
    pretty = json.dumps(artifact, ensure_ascii=False, indent=2).encode("utf-8")
    with pytest.raises(AdapterError) as raised:
        adapters.staging_keys(parse_artifact_bytes(pretty))       # valid, but not canonical
    assert raised.value.code == "ARTIFACT_NOT_CANONICAL"


def test_missing_profile_is_a_source_count_discrepancy():
    snap = parse_artifact(harvest([lecturer(1), lecturer(2)], cards=3))
    assert snap.completeness.value == "PARTIAL"
    assert [i.code for i in snap.issues] == ["SOURCE_COUNT_MISMATCH"]
    assert analysis.declared_vs_actual(snap)["PROFILES"] == {
        "declared": 3, "actual": 2, "consistent": False}


def test_partial_harvest_never_proves_withdrawal():
    before = parse_artifact(harvest([lecturer(1), lecturer(2), lecturer(3)]))
    after = parse_artifact(harvest([lecturer(1), lecturer(2)], cards=3,
                                   completed="2026-11-03T09:00:00Z"))
    report_ = analysis.presence_diff(before, after)
    assert not report_.comparable and report_.by_status(P.WITHDRAWN) == ()
    assert entry(report_, "RECORD:PROFILE", f"{REPO}/giang-vien/synthetic-3").status is (
        P.NOT_OBSERVED)


def test_complete_harvests_report_withdrawal():
    before = parse_artifact(harvest([lecturer(1), lecturer(2)]))
    after = parse_artifact(harvest([lecturer(1)], completed="2026-11-03T09:00:00Z"))
    report_ = analysis.presence_diff(before, after)
    assert report_.comparable
    assert entry(report_, "RECORD:PROFILE", f"{REPO}/giang-vien/synthetic-2").status is (
        P.WITHDRAWN)


def test_malformed_profile_items_are_kept_and_flagged():
    broken = lecturer(2)
    del broken["institutional_email"]
    broken["source_fields"].pop("Email")
    broken["orcid"] = 12345
    snap = parse_artifact(harvest([lecturer(1), "not a profile", broken]))
    assert len(snap.records) == 3
    assert "PROFILE_NOT_OBJECT" in codes(snap.records[1])
    assert snap.records[1].raw == "not a profile"
    assert "ORCID_MISSING" in codes(snap.records[2]) or "ORCID_FORMAT_INVALID" in codes(
        snap.records[2])
    assert snap.records[2].raw.get("email") is None


def test_extracted_values_not_traceable_to_page_text_are_reported():
    item = lecturer(1, orcid=ORCID_A)
    item["source_fields"]["ORCID"] = f"{ORCID_B} ↗"
    item["source_fields"]["Email"] = "someone.else@example.invalid"
    checks = harvest([lecturer(2), item])["capture"]["checks"]
    assert checks == {"Email_NOT_IN_SOURCE_TEXT": [2], "ORCID_NOT_IN_SOURCE_TEXT": [2]}


@pytest.mark.parametrize(("mutate", "code"), [
    (lambda a: a.update(items="x"), "LECTURERS_NOT_LIST"),
    (lambda a: a.update(manifest=[]), "MANIFEST_INVALID"),
    (lambda a: a["manifest"].pop("source_card_count"), "MANIFEST_INVALID"),
    (lambda a: a["manifest"].update(source_card_count=True), "MANIFEST_INVALID"),
    (lambda a: a["manifest"].pop("harvest_completed_at"), "MANIFEST_INVALID"),
    (lambda a: a["manifest"].update(source_base_url="opaque-origin"), "ORIGIN_URL_INVALID"),
    (lambda a: a["manifest"].update(source_base_url="https:///no-host"), "ORIGIN_URL_INVALID"),
    (lambda a: a.update(crawl=[]), "CRAWL_REPORT_INVALID"),
    (lambda a: a.update(sha="ABC"), "UPSTREAM_SHA256_INVALID"),
    (lambda a: a["items"][0].update(counts={"article_count": 1.5}), "NON_CANONICAL_VALUE"),
])
def test_malformed_harvest_inputs_raise(mutate, code):
    args = {"items": [lecturer(1)], "manifest": manifest(1), "crawl": report(), "sha": SHA}
    mutate(args)
    with pytest.raises(AdapterError) as raised:
        adapters.profiles_artifact(args["items"], args["manifest"], args["crawl"],
                                   lecturers_sha256=args["sha"])
    assert raised.value.code == code


# ---------------------------------------------------------------------------
# Scopus-guide snapshots: three distinct ID categories
# ---------------------------------------------------------------------------

def test_tables_snapshot_maps_sections_headers_and_rows():
    snapshot = tables_snapshot([["X", sid(1), "2"]], [["Y", sid(2), "1"], ["Z", sid(3), "1"]])
    artifact = guide(snapshot, declared_counts={"AMBIGUOUS_IDS": 1, "UNASSIGNED_IDS": 2})
    tables = artifact["content"]["tables"]
    assert set(tables) == {"AMBIGUOUS", "UNASSIGNED"}
    assert [c["role"] for c in tables["AMBIGUOUS"]["columns"]] == [
        "SCOPUS_NAME", "SCOPUS_ID", "DECLARED_PUB_COUNT"]
    assert [c["header"] for c in tables["UNASSIGNED"]["columns"]] == HEADER
    assert tables["AMBIGUOUS"]["heading"] == HEADINGS["1"]
    snap = parse_artifact(artifact)
    assert [c.claim_type for c in snap.claims] == [ClaimType.SCOPUS_ID_AMBIGUOUS,
                                                   ClaimType.SCOPUS_ID_UNASSIGNED,
                                                   ClaimType.SCOPUS_ID_UNASSIGNED]
    assert all(c.subject_key is None for c in snap.claims) and snap.issues == ()


def test_multi_id_rows_snapshot_uses_fixed_layout_and_emits_owned_and_email_claims():
    artifact = multi(rows_snapshot([multi_row(1, [sid(10), sid(11)], primary=sid(11))]))
    columns = artifact["content"]["tables"]["MULTI_ID"]["columns"]
    assert [c["role"] for c in columns] == [r.value for r in adapters.MULTI_ID_LAYOUT]
    assert {c["header"] for c in columns} == {""}
    assert artifact["capture"]["upstream"]["header_captured"] is False
    snap = parse_artifact(artifact)
    owned = claims_of(snap, ClaimType.SCOPUS_ID_OWNED)
    assert [(c.value.normalized, c.flag("is_primary_claimed")) for c in owned] == [
        (sid(10), False), (sid(11), True)]
    assert {c.subject_key for c in owned} == {"gv1@example.invalid"}
    assert len(claims_of(snap, ClaimType.EMAIL_DECLARED)) == 1


def test_three_id_categories_stay_distinct_across_captures():
    owned = parse_artifact(multi(rows_snapshot([multi_row(1, [sid(1)])])))
    unowned = parse_artifact(guide(tables_snapshot([["X", sid(1), "1"]], [["Y", sid(1), "1"]])))
    assert analysis.distinct_scopus_ids(owned) == {"SCOPUS_ID_OWNED": 1, "ALL": 1}
    assert analysis.distinct_scopus_ids(unowned) == {
        "SCOPUS_ID_AMBIGUOUS": 1, "SCOPUS_ID_UNASSIGNED": 1, "ALL": 1}
    collision, = analysis.scopus_id_collisions(unowned)
    assert collision.kinds == (analysis.ScopusCollisionKind.CROSS_TABLE,)
    assert "SCOPE_DIFFERS" in analysis.presence_diff(owned, unowned).reasons


def test_duplicate_scopus_ids_are_kept_and_flagged():
    snap = parse_artifact(guide(tables_snapshot([], [["Y", sid(2), "1"], ["Y", sid(2), "1"]])))
    assert len(snap.records) == 2
    assert all("DUPLICATE_RECORD_KEY" in codes(r) for r in snap.records)
    assert analysis.scopus_id_collisions(snap)[0].kinds == (
        analysis.ScopusCollisionKind.REPEATED_ROW,)
    row = parse_artifact(multi(rows_snapshot([["GV", "gv@example.invalid", "2", "1", sid(5),
                                                f"{sid(5)}; {sid(5)}"]])))
    assert "DUPLICATE_ID_IN_ROW" in codes(row.records[0])
    two_owners = parse_artifact(multi(rows_snapshot([multi_row(1, [sid(7)]),
                                                     multi_row(2, [sid(7)])])))
    assert analysis.scopus_id_collisions(two_owners)[0].kinds == (
        analysis.ScopusCollisionKind.MULTI_OWNER,)


def test_reclassified_id_between_comparable_captures():
    before = parse_artifact(guide(tables_snapshot([["X", sid(4), "1"]], [])))
    after = parse_artifact(guide(tables_snapshot([], [["X", sid(4), "1"]],
                                                 ts="2026-11-29T00:00:00Z")))
    report_ = analysis.presence_diff(before, after)
    assert report_.comparable
    moved = entry(report_, "SCOPUS_ID", sid(4))
    assert moved.status is P.RECLASSIFIED
    assert (moved.before, moved.after) == (("SCOPUS_ID_AMBIGUOUS",), ("SCOPUS_ID_UNASSIGNED",))


def test_partial_guide_capture_never_proves_withdrawal():
    before = parse_artifact(guide(tables_snapshot([], [["Y", sid(2), "1"], ["Z", sid(3), "1"]])))
    after = parse_artifact(guide(tables_snapshot([], [["Y", sid(2), "1"]],
                                                 ts="2026-11-29T00:00:00Z"), "PARTIAL"))
    report_ = analysis.presence_diff(before, after)
    assert report_.by_status(P.WITHDRAWN) == ()
    assert entry(report_, "SCOPUS_ID", sid(3)).status is P.NOT_OBSERVED


def test_guide_count_discrepancy_is_kept_not_corrected():
    snap = parse_artifact(guide(tables_snapshot([["X", sid(1), "1"]], []),
                                declared_counts={"AMBIGUOUS_IDS": 2}))
    assert [i.code for i in snap.issues] == ["SOURCE_COUNT_MISMATCH"]
    rows = parse_artifact(multi(rows_snapshot([multi_row(1, [sid(1)])]),
                                declared_counts={"MULTI_ID_LECTURERS": 2}))
    assert dict(rows.declared_counts) == {"MULTI_ID_LECTURERS": 2}
    assert [i.code for i in rows.issues] == ["SOURCE_COUNT_MISMATCH"]


def test_malformed_guide_rows_are_kept():
    snap = parse_artifact(guide(tables_snapshot([["X", "57-BAD", "1"], ["short"]], [])))
    assert [r.validation_status for r in snap.records] == [ValidationStatus.INVALID] * 2
    assert snap.records[0].raw == ["X", "57-BAD", "1"]
    assert "ROW_CELL_COUNT_MISMATCH" in codes(snap.records[1])


def _tables(mutate):
    snapshot = tables_snapshot([["X", sid(1), "1"]], [["Y", sid(2), "1"]])
    mutate(snapshot)
    return snapshot


@pytest.mark.parametrize(("build", "code"), [
    (lambda: guide(_tables(lambda s: s["section_headings"].update({"2": "Other section"}))),
     "TABLE_KIND_UNRESOLVED"),
    (lambda: guide(_tables(lambda s: s["section_headings"].update({"2": HEADINGS["1"]}))),
     "TABLE_KIND_DUPLICATED"),
    (lambda: guide(_tables(lambda s: s["tables"][0]["rows"].pop(0))), "HEADER_ROW_MISSING"),
    (lambda: guide(_tables(lambda s: s.pop("section_headings"))), "SECTION_HEADINGS_MISSING"),
    (lambda: guide(_tables(lambda s: s.update(tables=[]))), "TABLES_MISSING"),
    (lambda: guide(_tables(lambda s: s.update(url="not-a-url"))), "ORIGIN_URL_INVALID"),
    (lambda: guide(_tables(lambda s: None), "MOSTLY"), "COMPLETENESS_INVALID"),
    (lambda: guide(_tables(lambda s: None), declared_counts={"MULTI_ID_LECTURERS": 35}),
     "DECLARED_COUNT_FOR_ABSENT_TABLE"),
    (lambda: multi(rows_snapshot([multi_row(1, [sid(1)])], stated=2)),
     "SNAPSHOT_ROW_COUNT_MISMATCH"),
    (lambda: multi(rows_snapshot([multi_row(1, [sid(1)])]),
                   declared_counts={"AMBIGUOUS_IDS": 1}), "DECLARED_COUNT_FOR_ABSENT_TABLE"),
    (lambda: adapters.guide_multi_id_artifact({"ts": "x"}, snapshot_sha256="bad",
                                              completeness="PARTIAL"), "UPSTREAM_SHA256_INVALID"),
])
def test_malformed_guide_snapshots_raise(build, code):
    with pytest.raises(AdapterError) as raised:
        build()
    assert raised.value.code == code


# ---------------------------------------------------------------------------
# Contract boundaries
# ---------------------------------------------------------------------------

def test_every_adapter_output_validates_against_the_json_schema():
    """Well-formed upstream gives schema-valid artifacts. A malformed item (e.g. a non-object
    profile) is schema-invalid by design: the parser still keeps it as an INVALID record."""
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    malformed = harvest([lecturer(1), "not a profile"])
    assert not validator.is_valid(malformed) and len(parse_artifact(malformed).records) == 2
    outputs = [harvest([lecturer(1, orcid=ORCID_A, pubs=1), lecturer(2)]),
               guide(tables_snapshot([["X", sid(1), "1"]], [["Y", sid(2), "1"]]),
                     declared_counts={"AMBIGUOUS_IDS": 1}),
               multi(rows_snapshot([multi_row(1, [sid(3), sid(4)])]))]
    for artifact in outputs:
        errors = [e.message for e in validator.iter_errors(artifact)]
        assert errors == []


def test_adapter_output_carries_no_identity_decision():
    forbidden = {"lecturer_id", "scopus_author_id", "approved", "decision", "reviewer",
                 "identity_id"}

    def keys(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from keys(value)
        elif isinstance(node, list):
            for item in node:
                yield from keys(item)

    artifact = harvest([lecturer(1, orcid=ORCID_A)])
    assert not set(keys(artifact)) & forbidden
    assert {r.record_kind for r in parse_artifact(artifact).records} == {RecordKind.PROFILE}


def test_adapters_import_no_database_app_or_network_modules():
    bad = ("sqlalchemy", "psycopg2", "fastapi", "pydantic_settings", "app.main", "app.core",
           "app.models", "app.api", "requests", "httpx", "urllib.request", "http.client",
           "socket")
    code = (
        "import json, sys; sys.path.insert(0, '.');"
        f"bad = {bad!r};"
        "hit = lambda names: sorted(m for m in names"
        " if any(m == b or m.startswith(b + '.') for b in bad));"
        "before = set(sys.modules);"
        "import app.services.source_claims.adapters;"
        "print(json.dumps({'preloaded': hit(before), 'new': hit(set(sys.modules) - before)}))"
    )
    result = subprocess.run([sys.executable, "-I", "-S", "-c", code], cwd=BACKEND,
                            capture_output=True, text=True, timeout=60, check=True)
    assert json.loads(result.stdout)["new"] == [], result.stdout + result.stderr
