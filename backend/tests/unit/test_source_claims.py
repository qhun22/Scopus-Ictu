"""Gate E.3 / P1 — pure source-claim contracts, parsing and analysis.

Synthetic fixtures only: reserved ``example.invalid`` domains, fake Scopus IDs
(570000000xx) and ORCID's own documentation example iDs. No database, no
application configuration, no network. TC-SC numbers refer to the E.3 design.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.source_claims import analysis, canonical, contract, parser
from app.services.source_claims.analysis import PresenceStatus as P
from app.services.source_claims.contract import (
    ClaimType,
    Completeness,
    KeyMethod,
    KeyStrength,
    RecordKind,
    ValidationStatus,
)
from app.services.source_claims.parser import ArtifactError, parse_artifact, parse_artifact_bytes

BACKEND = Path(__file__).resolve().parents[2]
SCHEMA = BACKEND.parent / "data" / "source_claims" / "schema" / "ictu_source_claims.schema.json"

ORCID_A = "0000-0002-1825-0097"   # ORCID documentation examples (valid check digits)
ORCID_B = "0000-0001-5109-3700"
ORCID_X = "0000-0002-1694-233X"


def sid(n: int) -> str:
    return str(57000000000 + n)


MULTI_COLUMNS = [
    {"header": "Họ tên", "role": "NAME"},
    {"header": "Email", "role": "EMAIL"},
    {"header": "Số ID", "role": "DECLARED_ID_COUNT"},
    {"header": "Số bài", "role": "DECLARED_PUB_COUNT"},
    {"header": "ID chính", "role": "PRIMARY_SCOPUS_ID"},
    {"header": "Danh sách ID", "role": "SCOPUS_ID_LIST"},
]
ID_COLUMNS = [
    {"header": "Tên Scopus", "role": "SCOPUS_NAME"},
    {"header": "Scopus ID", "role": "SCOPUS_ID"},
    {"header": "Số bài", "role": "DECLARED_PUB_COUNT"},
]


def _rows(rows):
    """Copy rows; a deliberately malformed non-list row is passed through as-is."""
    return [list(r) if isinstance(r, (list, tuple)) else r for r in rows]


def multi_row(name, email, ids, primary=None, count=None, pubs="3"):
    count = str(len(ids)) if count is None else count
    return [name, email, count, pubs, primary or ids[0], "; ".join(ids)]


def guide(multi=(), ambiguous=(), unassigned=(), *, declared=None, captured="2026-10-29T00:00:00Z",
          completeness="COMPLETE", tables=("MULTI_ID", "AMBIGUOUS", "UNASSIGNED"),
          extra_capture=None):
    all_tables = {
        "MULTI_ID": {"heading": "Giảng viên nhiều ID", "columns": [dict(c) for c in MULTI_COLUMNS],
                     "rows": _rows(multi)},
        "AMBIGUOUS": {"heading": "ID chưa rõ", "columns": [dict(c) for c in ID_COLUMNS],
                      "rows": _rows(ambiguous)},
        "UNASSIGNED": {"heading": "ID chưa gán", "columns": [dict(c) for c in ID_COLUMNS],
                       "rows": _rows(unassigned)},
    }
    content = {
        "source_url": "https://repository.example.invalid/huong-dan/",
        "tables": {name: all_tables[name] for name in tables},
    }
    if declared is not None:
        content["page_summary"] = {"text": "Tóm tắt nguồn tổng hợp", "declared_counts": declared}
    return {
        "contract": "ictu-source-claims", "contract_version": "1.0",
        "source_system": "ICTU_REPO_SCOPUS_GUIDE",
        "capture": {"captured_at": captured, "completeness": completeness, **(extra_capture or {})},
        "content": content,
    }


def profile(n, name=None, email=None, orcid=None, source_id=True, **extra):
    item = {"full_name": name or f"Synthetic Lecturer {n}",
            "email": email if email is not None else f"lecturer{n}@example.invalid", **extra}
    if source_id:
        item["source_id"] = f"https://repository.example.invalid/profile/{n}"
    if orcid is not None:
        item["orcid"] = orcid
    return item


def profiles(*items, declared=None, captured="2026-10-29T00:00:00Z", completeness="COMPLETE"):
    content = {"source_url": "https://repository.example.invalid/profiles",
               "profiles": [copy.deepcopy(i) for i in items]}
    if declared is not None:
        content["declared_counts"] = {"PROFILES": declared}
    return {
        "contract": "ictu-source-claims", "contract_version": "1.0",
        "source_system": "ICTU_REPO_PROFILES",
        "capture": {"captured_at": captured, "completeness": completeness},
        "content": content,
    }


def claims_of(snapshot, claim_type):
    return [c for c in snapshot.claims if c.claim_type is claim_type]


def codes(record):
    return {issue.code for issue in record.issues}


def entry(report, dimension, key):
    found = [e for e in report.entries if e.dimension == dimension and e.key == key]
    assert len(found) == 1, (dimension, key, report.entries)
    return found[0]


# ---------------------------------------------------------------------------
# TC-SC-01/02 — ORCID collisions keep every claim
# ---------------------------------------------------------------------------

def test_tc_sc_01_same_name_shared_orcid_keeps_both_profiles():
    snap = parse_artifact(profiles(
        profile(1, name="Nguyễn Văn A", orcid=ORCID_A),
        profile(2, name="Nguyễn Văn A", email="other.a@example.invalid", orcid=ORCID_A),
    ))
    assert len(snap.records) == 2 and len(claims_of(snap, ClaimType.ORCID_DECLARED)) == 2
    group, = analysis.orcid_collision_groups(snap)
    assert group.value == ORCID_A and group.record_refs == ("PROFILE#1", "PROFILE#2")


def test_tc_sc_02_different_names_shared_orcid_are_reported_not_resolved():
    snap = parse_artifact(profiles(profile(1, name="Trần B", orcid=ORCID_B),
                                   profile(2, name="Lê C", orcid=ORCID_B)))
    group, = analysis.orcid_collision_groups(snap)
    assert group.record_refs == ("PROFILE#1", "PROFILE#2")
    assert {r.record_key.value for r in snap.records} == {
        "https://repository.example.invalid/profile/1",
        "https://repository.example.invalid/profile/2"}


# ---------------------------------------------------------------------------
# TC-SC-03..08 — multi-ID rows, cross-table conflicts, unowned IDs
# ---------------------------------------------------------------------------

def test_tc_sc_03_three_ids_primary_flag_and_declared_count_mismatch_kept():
    snap = parse_artifact(guide(multi=[
        multi_row("GV A", "a@example.invalid", [sid(1), sid(2), sid(3)], primary=sid(2), count="4"),
    ]))
    record, = snap.records
    assert record.validation_status is ValidationStatus.WARNING
    assert "ID_COUNT_MISMATCH" in codes(record)
    owned = claims_of(snap, ClaimType.SCOPUS_ID_OWNED)
    assert [c.value.normalized for c in owned] == [sid(1), sid(2), sid(3)]
    assert [c.flag("is_primary_claimed") for c in owned] == [False, True, False]
    assert all(c.subject_key == "a@example.invalid" for c in owned)


def test_primary_outside_list_is_kept_as_unlisted_claim():
    snap = parse_artifact(guide(multi=[
        multi_row("GV A", "a@example.invalid", [sid(1)], primary=sid(9), count="1")]))
    assert "PRIMARY_NOT_IN_LIST" in codes(snap.records[0])
    unlisted = [c for c in claims_of(snap, ClaimType.SCOPUS_ID_OWNED) if not c.flag("listed")]
    pairs = [(c.value.normalized, c.flag("is_primary_claimed")) for c in unlisted]
    assert pairs == [(sid(9), True)]


def test_tc_sc_04_id_in_owned_and_unassigned_tables_is_cross_table_collision():
    snap = parse_artifact(guide(
        multi=[multi_row("GV A", "a@example.invalid", [sid(1)])],
        unassigned=[["A. Synthetic", sid(1), "2"]]))
    collision, = analysis.scopus_id_collisions(snap)
    assert collision.kinds == (analysis.ScopusCollisionKind.CROSS_TABLE,)
    assert len(snap.claims) == 3  # owned + e-mail + unassigned: nothing merged


def test_tc_sc_05_two_rows_claiming_one_id_is_multi_owner():
    snap = parse_artifact(guide(multi=[
        multi_row("GV A", "a@example.invalid", [sid(1), sid(2)]),
        multi_row("GV B", "b@example.invalid", [sid(2)]),
    ]))
    collision, = analysis.scopus_id_collisions(snap)
    assert collision.scopus_id == sid(2)
    assert collision.kinds == (analysis.ScopusCollisionKind.MULTI_OWNER,)


def test_tc_sc_06_ambiguous_and_unassigned_ids_are_never_attributed():
    snap = parse_artifact(guide(ambiguous=[["X", sid(5), "1"]], unassigned=[["Y", sid(6), "1"]]))
    unowned = [c for c in snap.claims if c.claim_type is not ClaimType.SCOPUS_ID_OWNED]
    assert {c.claim_type for c in unowned} == {ClaimType.SCOPUS_ID_AMBIGUOUS,
                                              ClaimType.SCOPUS_ID_UNASSIGNED}
    assert all(c.subject_key is None for c in unowned)


def test_tc_sc_07_owner_absent_from_profiles_stays_an_unresolved_source_claim():
    guide_snap = parse_artifact(guide(multi=[multi_row("GV Z", "z@example.invalid", [sid(7)])]))
    profile_snap = parse_artifact(profiles(profile(1)))
    owned, = claims_of(guide_snap, ClaimType.SCOPUS_ID_OWNED)
    # P1 never links sources; resolution against lecturers is P3 and reported, not inferred.
    assert owned.subject_key == "z@example.invalid"
    assert all(r.record_key.value != "z@example.invalid" for r in profile_snap.records)


def test_tc_sc_08_two_profiles_sharing_one_email_are_both_kept_and_grouped():
    snap = parse_artifact(profiles(profile(1, email="shared@example.invalid"),
                                   profile(2, email="Shared@Example.invalid")))
    group, = analysis.declared_value_collisions(snap, ClaimType.EMAIL_DECLARED)
    assert group.record_refs == ("PROFILE#1", "PROFILE#2")
    assert group.raw_values == ("Shared@Example.invalid", "shared@example.invalid")


# ---------------------------------------------------------------------------
# TC-SC-09 + hashing: content hash vs capture metadata, key order, bytes
# ---------------------------------------------------------------------------

def base_guide(**kwargs):
    return guide(multi=[multi_row("GV A", "a@example.invalid", [sid(1), sid(2)])],
                 ambiguous=[["X", sid(5), "1"]], unassigned=[["Y", sid(6), "2"]],
                 declared={"MULTI_ID_LECTURERS": 1}, **kwargs)


def test_tc_sc_09_identical_artifact_parses_identically():
    first, second = parse_artifact(base_guide()), parse_artifact(base_guide())
    assert first == second


def test_captured_at_change_keeps_content_hash_and_changes_capture_hash():
    first = parse_artifact(base_guide())
    later = parse_artifact(base_guide(captured="2026-11-05T08:30:00+07:00",
                                      extra_capture={"tool": "synthetic-capture 2"}))
    assert first.content_hash == later.content_hash
    assert first.records == later.records and first.claims == later.claims
    assert first.capture.capture_hash != later.capture.capture_hash


def test_reordered_json_keys_and_whitespace_hash_identically():
    artifact = base_guide()
    reordered = json.loads(json.dumps(artifact), object_pairs_hook=lambda p: dict(reversed(p)))
    assert list(reordered["content"]) != list(artifact["content"])
    compact = json.dumps(artifact, ensure_ascii=False, separators=(",", ":")).encode()
    spaced = json.dumps(reordered, ensure_ascii=False, indent=4).encode()
    a, b = parse_artifact_bytes(compact), parse_artifact_bytes(spaced)
    assert a.content_hash == b.content_hash and a.records == b.records
    assert a.artifact_bytes_sha256 != b.artifact_bytes_sha256  # byte identity kept separately
    assert parse_artifact(artifact).artifact_bytes_sha256 is None  # dict input: no byte claim


def test_content_change_changes_content_hash():
    changed = base_guide()
    changed["content"]["tables"]["UNASSIGNED"]["rows"][0][2] = "3"
    assert parse_artifact(changed).content_hash != parse_artifact(base_guide()).content_hash


def test_raw_values_that_normalize_alike_stay_distinct():
    first = parse_artifact(profiles(profile(1, orcid=ORCID_A)))
    second = parse_artifact(profiles(profile(1, orcid=f"https://orcid.org/{ORCID_A}")))
    assert first.content_hash != second.content_hash
    assert first.records[0].record_hash != second.records[0].record_hash
    orcid_1, = claims_of(first, ClaimType.ORCID_DECLARED)
    orcid_2, = claims_of(second, ClaimType.ORCID_DECLARED)
    assert orcid_1.value.normalized == orcid_2.value.normalized == ORCID_A
    assert orcid_1.value.raw != orcid_2.value.raw


def test_record_hash_ignores_position_but_record_keeps_it():
    one = parse_artifact(profiles(profile(1), profile(2)))
    swapped = parse_artifact(profiles(profile(2), profile(1)))
    by_key = {r.record_key.value: r for r in swapped.records}
    for record in one.records:
        assert by_key[record.record_key.value].record_hash == record.record_hash
    assert [r.source_position for r in swapped.records] == [1, 2]


# ---------------------------------------------------------------------------
# Record identity: names are never keys; duplicates never overwrite
# ---------------------------------------------------------------------------

def test_same_name_lecturers_remain_separate_records():
    snap = parse_artifact(guide(multi=[
        multi_row("Nguyễn Văn Nam", "nam1@example.invalid", [sid(1)]),
        multi_row("Nguyễn Văn Nam", "nam2@example.invalid", [sid(2)]),
    ]))
    keys = [r.record_key for r in snap.records]
    assert [k.value for k in keys] == ["nam1@example.invalid", "nam2@example.invalid"]
    assert all(k.method is KeyMethod.EMAIL_V1 for k in keys)


def test_rows_without_email_get_content_keys_never_name_keys():
    snap = parse_artifact(guide(multi=[
        multi_row("Nguyễn Văn Nam", "", [sid(1)]),
        multi_row("Nguyễn Văn Nam", "", [sid(2)]),
    ]))
    keys = [r.record_key for r in snap.records]
    assert all(k.method is KeyMethod.CONTENT_V1 and k.strength is KeyStrength.WEAK for k in keys)
    assert keys[0].value != keys[1].value
    assert all("nam" not in k.value for k in keys)


def test_duplicate_source_keys_are_flagged_on_both_records_and_both_kept():
    snap = parse_artifact(profiles(profile(1), profile(1, name="Different Name")))
    assert len(snap.records) == 2
    assert all("DUPLICATE_RECORD_KEY" in codes(r) for r in snap.records)
    identical = parse_artifact(guide(unassigned=[["Y", sid(6), "2"], ["Y", sid(6), "2"]]))
    assert len(identical.records) == 2
    assert all("DUPLICATE_RECORD_KEY" in codes(r) for r in identical.records)
    assert analysis.scopus_id_collisions(identical)[0].kinds == (
        analysis.ScopusCollisionKind.REPEATED_ROW,)


def test_profile_key_falls_back_to_email_then_content():
    snap = parse_artifact(profiles(profile(1, source_id=False),
                                   profile(2, source_id=False, email="")))
    assert [r.record_key.method for r in snap.records] == [KeyMethod.EMAIL_V1, KeyMethod.CONTENT_V1]


# ---------------------------------------------------------------------------
# TC-SC-10..12 — withdrawal only between comparable COMPLETE snapshots
# ---------------------------------------------------------------------------

def test_tc_sc_10_id_dropped_between_complete_snapshots_is_withdrawn():
    before = parse_artifact(guide(multi=[multi_row("GV A", "a@example.invalid", [sid(1), sid(2)])]))
    after = parse_artifact(guide(multi=[multi_row("GV A", "a@example.invalid", [sid(1)])],
                                 captured="2026-12-01T00:00:00Z"))
    report = analysis.presence_diff(before, after)
    assert report.comparable
    assert entry(report, "SCOPUS_ID", sid(2)).status is P.WITHDRAWN
    assert entry(report, "SCOPUS_ID", sid(1)).status is P.UNCHANGED
    assert entry(report, "RECORD:MULTI_ID_ROW", "a@example.invalid").status is P.CHANGED


def test_tc_sc_11_move_from_unassigned_to_owned_is_reclassified_not_deleted():
    before = parse_artifact(guide(unassigned=[["Y", sid(6), "2"]]))
    after = parse_artifact(guide(multi=[multi_row("GV A", "a@example.invalid", [sid(6)])],
                                 captured="2026-12-01T00:00:00Z"))
    moved = entry(analysis.presence_diff(before, after), "SCOPUS_ID", sid(6))
    assert moved.status is P.RECLASSIFIED
    assert moved.before == ("SCOPUS_ID_UNASSIGNED",)
    assert moved.after == ("SCOPUS_ID_OWNED:a@example.invalid",)


@pytest.mark.parametrize("which", ["previous", "current"])
def test_tc_sc_12_partial_snapshot_never_proves_withdrawal(which):
    kwargs = {"completeness": "PARTIAL"}
    before = parse_artifact(guide(unassigned=[["Y", sid(6), "2"], ["Z", sid(7), "1"]],
                                  **(kwargs if which == "previous" else {})))
    after = parse_artifact(guide(unassigned=[["Y", sid(6), "2"]], captured="2026-12-01T00:00:00Z",
                                 **(kwargs if which == "current" else {})))
    report = analysis.presence_diff(before, after)
    assert not report.comparable and report.by_status(P.WITHDRAWN) == ()
    assert entry(report, "SCOPUS_ID", sid(7)).status is P.NOT_OBSERVED


def test_different_table_scope_is_not_comparable():
    before = parse_artifact(guide(unassigned=[["Y", sid(6), "2"]]))
    after = parse_artifact(guide(ambiguous=[["X", sid(5), "1"]], tables=("AMBIGUOUS",),
                                 captured="2026-12-01T00:00:00Z"))
    report = analysis.presence_diff(before, after)
    assert "SCOPE_DIFFERS" in report.reasons
    assert entry(report, "SCOPUS_ID", sid(6)).status is P.NOT_OBSERVED


def test_out_of_order_or_rule_version_change_is_not_comparable(monkeypatch):
    early = parse_artifact(guide(unassigned=[["Y", sid(6), "2"]]))
    late = parse_artifact(guide(unassigned=[], captured="2026-12-01T00:00:00Z"))
    assert "OUT_OF_ORDER" in analysis.presence_diff(late, early).reasons
    monkeypatch.setattr(parser, "IDENTITY_RULES_VERSION", "2")
    newer_rules = parse_artifact(guide(unassigned=[], captured="2026-12-01T00:00:00Z"))
    report = analysis.presence_diff(early, newer_rules)
    assert "IDENTITY_RULES_DIFFER" in report.reasons and report.by_status(P.WITHDRAWN) == ()


def test_different_source_systems_are_never_compared():
    with pytest.raises(ValueError):
        analysis.presence_diff(parse_artifact(base_guide()), parse_artifact(profiles(profile(1))))


def test_weak_key_absence_is_unstable_not_withdrawn():
    before = parse_artifact(guide(multi=[multi_row("GV A", "", [sid(1)], pubs="3")]))
    after = parse_artifact(guide(multi=[multi_row("GV A", "", [sid(1)], pubs="4")],
                                 captured="2026-12-01T00:00:00Z"))
    report = analysis.presence_diff(before, after)
    statuses = {e.status for e in report.entries if e.dimension == "RECORD:MULTI_ID_ROW"}
    assert statuses == {P.KEY_UNSTABLE, P.NEW}
    assert entry(report, "SCOPUS_ID", sid(1)).status is P.OWNER_UNVERIFIABLE


def test_owner_change_between_strong_keys_is_reported():
    before = parse_artifact(guide(multi=[multi_row("GV A", "a@example.invalid", [sid(1)])]))
    after = parse_artifact(guide(multi=[multi_row("GV B", "b@example.invalid", [sid(1)])],
                                 captured="2026-12-01T00:00:00Z"))
    report = analysis.presence_diff(before, after)
    assert entry(report, "SCOPUS_ID", sid(1)).status is P.OWNER_CHANGED


def test_profile_withdrawal_and_declared_value_change():
    before = parse_artifact(profiles(profile(1, orcid=ORCID_A), profile(2)))
    after = parse_artifact(profiles(profile(1, orcid=ORCID_B), captured="2026-12-01T00:00:00Z"))
    report = analysis.presence_diff(before, after)
    key_2 = "https://repository.example.invalid/profile/2"
    assert entry(report, "RECORD:PROFILE", key_2).status is P.WITHDRAWN
    key_1 = "https://repository.example.invalid/profile/1"
    assert entry(report, "ORCID_DECLARED", key_1).status is P.CHANGED


def test_duplicate_keys_make_presence_a_key_collision():
    before = parse_artifact(profiles(profile(1), profile(1, name="Twin")))
    after = parse_artifact(profiles(profile(1)))
    key = "https://repository.example.invalid/profile/1"
    report = analysis.presence_diff(before, after)
    assert entry(report, "RECORD:PROFILE", key).status is P.KEY_COLLISION


def test_presence_diff_does_not_modify_snapshots():
    before = parse_artifact(base_guide())
    after = parse_artifact(guide(captured="2026-12-01T00:00:00Z"))
    frozen = (copy.deepcopy(before), copy.deepcopy(after))
    analysis.presence_diff(before, after)
    assert (before, after) == frozen
    with pytest.raises(AttributeError):
        before.records[0].record_hash = "x"  # frozen dataclass


# ---------------------------------------------------------------------------
# TC-SC-13..17 — counts, invalid values, profiles, normalization
# ---------------------------------------------------------------------------

def test_tc_sc_13_source_declares_35_lecturers_with_34_rows_kept_as_discrepancy():
    rows = [multi_row(f"GV {i}", f"gv{i}@example.invalid", [sid(100 + i)]) for i in range(34)]
    snap = parse_artifact(guide(multi=rows, declared={"MULTI_ID_LECTURERS": 35}))
    assert len(snap.records) == 34
    assert dict(snap.declared_counts) == {"MULTI_ID_LECTURERS": 35}
    mismatch, = [i for i in snap.issues if i.code == "SOURCE_COUNT_MISMATCH"]
    assert "35" in mismatch.message and "34" in mismatch.message
    assert analysis.declared_vs_actual(snap)["MULTI_ID_LECTURERS"] == {
        "declared": 35, "actual": 34, "consistent": False}


def test_tc_sc_14_invalid_scopus_id_and_orcid_are_preserved_raw():
    snap = parse_artifact(guide(unassigned=[["Y", "57-BAD-ID", "1"]]))
    record, = snap.records
    claim, = snap.claims
    assert record.validation_status is ValidationStatus.INVALID
    assert record.raw == ["Y", "57-BAD-ID", "1"]
    assert claim.value.raw == "57-BAD-ID" and claim.value.normalized is None
    assert claim.claim_key.startswith("SCOPUS_ID_UNASSIGNED|-|raw-sha256:")
    bad_checksum = "0000-0002-1825-0098"
    p_snap = parse_artifact(profiles(profile(1, orcid=bad_checksum),
                                     profile(2, orcid="not-an-orcid")))
    raws = [c.value.raw for c in claims_of(p_snap, ClaimType.ORCID_DECLARED)]
    assert raws == [bad_checksum, "not-an-orcid"]
    orcid_codes = {"ORCID_CHECKSUM_INVALID", "ORCID_FORMAT_INVALID"}
    assert [codes(r) & orcid_codes for r in p_snap.records] == [
        {"ORCID_CHECKSUM_INVALID"}, {"ORCID_FORMAT_INVALID"}]


def test_invalid_token_in_id_list_does_not_drop_valid_ids():
    snap = parse_artifact(guide(multi=[["GV A", "a@example.invalid", "3", "1", sid(1),
                                        f"{sid(1)}, x12, {sid(2)}"]]))
    owned = claims_of(snap, ClaimType.SCOPUS_ID_OWNED)
    assert [c.value.raw for c in owned] == [sid(1), "x12", sid(2)]
    assert [c.value.valid for c in owned] == [True, False, True]


def test_malformed_rows_are_kept_with_issues():
    artifact = guide(unassigned=[["Y", sid(6)], "not a row"])
    snap = parse_artifact(artifact)
    assert [r.validation_status for r in snap.records] == [ValidationStatus.INVALID] * 2
    assert "ROW_CELL_COUNT_MISMATCH" in codes(snap.records[0])
    assert "ROW_NOT_LIST" in codes(snap.records[1]) and snap.records[1].raw == "not a row"


def test_tc_sc_15_profiles_without_publications_are_kept():
    snap = parse_artifact(profiles(profile(1), profile(2, publications=[]),
                                   profile(3, department="Synthetic Faculty"), declared=3))
    assert len(snap.records) == 3 and snap.issues == ()
    assert snap.records[1].raw["publications"] == []


def test_tc_sc_17_unicode_and_whitespace_variants_normalize_deterministically():
    decomposed = "Nguyễn  Văn\tA"
    composed = "Nguyễn Văn A"
    assert (canonical.normalize_name(decomposed).normalized
            == canonical.normalize_name(composed).normalized == "nguyễn văn a")
    assert canonical.normalize_email("  A@Example.INVALID ").normalized == "a@example.invalid"
    fullwidth = "５７０００００００１２"
    assert canonical.normalize_scopus_id(fullwidth).normalized == "57000000012"
    assert canonical.normalize_scopus_id(fullwidth).raw == fullwidth
    assert canonical.normalize_orcid(f" HTTPS://ORCID.ORG/{ORCID_X.lower()} ").normalized == ORCID_X
    assert canonical.normalize_source_id(
        "HTTPS://Repository.Example.invalid:443/Profile/7/").normalized == (
        "https://repository.example.invalid/Profile/7")


def test_repeated_parsing_is_byte_for_byte_deterministic():
    outputs = set()
    for _ in range(3):
        snap = parse_artifact(base_guide())
        outputs.add(canonical.canonical_json([
            snap.content_hash, snap.scope_key,
            [[r.ref, r.record_hash, r.record_key.value, r.validation_status.value,
              [i.to_dict() for i in r.issues]] for r in snap.records],
            [[c.claim_key, c.record_ref, [list(f) for f in c.flags]] for c in snap.claims],
        ]))
    assert len(outputs) == 1


def test_records_reconstruct_the_source_content_losslessly():
    artifact = base_guide()
    snap = parse_artifact(artifact)
    rebuilt = {kind: [r.raw for r in snap.records if r.record_kind is kind]
               for kind in (RecordKind.MULTI_ID_ROW, RecordKind.AMBIGUOUS_ID_ROW,
                            RecordKind.UNASSIGNED_ID_ROW)}
    tables = artifact["content"]["tables"]
    assert rebuilt[RecordKind.MULTI_ID_ROW] == tables["MULTI_ID"]["rows"]
    assert rebuilt[RecordKind.AMBIGUOUS_ID_ROW] == tables["AMBIGUOUS"]["rows"]
    assert rebuilt[RecordKind.UNASSIGNED_ID_ROW] == tables["UNASSIGNED"]["rows"]
    assert snap.content == artifact["content"]


def test_inventory_counts_on_a_synthetic_snapshot():
    snap = parse_artifact(guide(
        multi=[multi_row("GV A", "a@example.invalid", [sid(1), sid(2)]),
               multi_row("GV B", "b@example.invalid", [sid(3)])],
        ambiguous=[["X", sid(5), "1"]], unassigned=[["Y", sid(6), "1"], ["Z", sid(7), "1"]]))
    assert analysis.distinct_scopus_ids(snap) == {
        "SCOPUS_ID_AMBIGUOUS": 1, "SCOPUS_ID_OWNED": 3, "SCOPUS_ID_UNASSIGNED": 2, "ALL": 6}


# ---------------------------------------------------------------------------
# Envelope contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("mutate", "code"), [
    (lambda a: a.update(contract="other"), "WRONG_CONTRACT"),
    (lambda a: a.update(contract_version="2.0"), "UNSUPPORTED_CONTRACT_VERSION"),
    (lambda a: a.update(source_system="X"), "UNKNOWN_SOURCE_SYSTEM"),
    (lambda a: a.update(extra=1), "UNKNOWN_ENVELOPE_FIELD"),
    (lambda a: a["capture"].pop("captured_at"), "CAPTURED_AT_MISSING"),
    (lambda a: a["capture"].update(captured_at="2026-10-29T00:00:00"), "CAPTURED_AT_NO_OFFSET"),
    (lambda a: a["capture"].update(completeness="MOSTLY"), "COMPLETENESS_INVALID"),
    (lambda a: a["content"]["tables"].update(OTHER={}), "UNKNOWN_TABLE"),
    (lambda a: a["content"]["tables"]["AMBIGUOUS"]["columns"][1].update(role="EMAIL"),
     "COLUMN_ROLE_NOT_ALLOWED"),
    (lambda a: a["content"]["tables"]["AMBIGUOUS"]["columns"].pop(1), "COLUMN_ROLE_REQUIRED"),
    (lambda a: a["content"]["tables"]["AMBIGUOUS"]["rows"].append(["X", 1.5, "1"]),
     "NON_CANONICAL_VALUE"),
])
def test_envelope_violations_raise(mutate, code):
    artifact = base_guide()
    mutate(artifact)
    with pytest.raises(ArtifactError) as raised:
        parse_artifact(artifact)
    assert raised.value.code == code


@pytest.mark.parametrize(("data", "code"), [
    (b'{"contract": "a", "contract": "b"}', "DUPLICATE_JSON_KEY"),
    (b'{"x": 1.0}', "FLOAT_NOT_ALLOWED"),
    (b"\xff\xfe", "NOT_UTF8"),
    (b"{", "NOT_JSON"),
])
def test_byte_level_violations_raise(data, code):
    with pytest.raises(ArtifactError) as raised:
        parse_artifact_bytes(data)
    assert raised.value.code == code


# ---------------------------------------------------------------------------
# Boundaries: schema in sync, no identity semantics, no heavy imports
# ---------------------------------------------------------------------------

def test_schema_file_matches_code_vocabularies():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    assert props["contract"]["const"] == contract.CONTRACT_NAME
    assert set(props["source_system"]["enum"]) == {s.value for s in contract.SourceSystem}
    assert set(props["capture"]["properties"]["completeness"]["enum"]) == {
        c.value for c in Completeness}
    assert set(schema["$defs"]["column"]["properties"]["role"]["enum"]) == {
        r.value for r in contract.ColumnRole}
    tables = schema["$defs"]["guideContent"]["properties"]["tables"]["properties"]
    assert set(tables) == {t.value for t in contract.TableKind}
    declared = schema["$defs"]["guideContent"]["properties"]["page_summary"]["properties"][
        "declared_counts"]["properties"]
    assert set(declared) == set(contract.DECLARED_COUNT_KEYS)


def test_claims_carry_no_identity_decision():
    fields = set(contract.ClaimItem.__dataclass_fields__) | set(
        contract.SourceRecord.__dataclass_fields__)
    forbidden = {"lecturer_id", "scopus_author_id", "approved", "status", "identity_id",
                 "decision", "reviewer"}
    assert not fields & forbidden


# ---------------------------------------------------------------------------
# P1-R1 — Invalid source URL must not crash row parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_url", [
    "http://host:notanumber/path",
    "http://[::1malformed]/",
])
def test_r1_malformed_source_id_in_profile_returns_issue_not_crash(bad_url):
    bad_profile = {"full_name": "Test Lecturer", "email": "x@example.invalid",
                   "source_id": bad_url}
    snap = parse_artifact(profiles(bad_profile))
    record, = snap.records
    assert "SOURCE_URL_MALFORMED" in codes(record)
    # Preserved raw but no normalized value
    source_id_pair = dict(record.normalized).get("source_id")
    assert source_id_pair is not None
    assert source_id_pair["normalized"] is None
    assert source_id_pair["raw"] == bad_url
    # Falls back to email key, not the malformed source_id
    assert record.record_key.method is KeyMethod.EMAIL_V1


def test_r1_valid_source_id_url_still_normalizes_correctly():
    snap = parse_artifact(profiles(profile(1)))
    record, = snap.records
    assert record.record_key.method.value == "PROFILE_SOURCE_ID_V1"
    source_id_pair = dict(record.normalized)["source_id"]
    assert source_id_pair["normalized"] is not None


@pytest.mark.parametrize("bad_url", [
    "http://host:notanumber/path",
    "http://[::1malformed]/",
])
def test_r1_malformed_content_source_url_raises_artifact_error(bad_url):
    artifact = profiles(profile(1))
    artifact["content"]["source_url"] = bad_url
    with pytest.raises(ArtifactError) as raised:
        parse_artifact(artifact)
    assert raised.value.code == "SOURCE_URL_MALFORMED"


# ---------------------------------------------------------------------------
# P1-R2 — Stored normalized evidence is deeply immutable
# ---------------------------------------------------------------------------

def test_r2_normalized_evidence_inner_mapping_is_immutable():
    snap = parse_artifact(profiles(profile(1)))
    record = snap.records[0]
    assert len(record.normalized) > 0
    _field_name, field_map = record.normalized[0]
    original_raw = field_map["raw"]
    with pytest.raises(TypeError):
        field_map["raw"] = "tampered"  # MappingProxyType blocks __setitem__
    assert field_map["raw"] == original_raw


def test_r2_all_normalized_pairs_are_immutable():
    snap = parse_artifact(profiles(profile(1, orcid=ORCID_A)))
    for _name, mapping in snap.records[0].normalized:
        with pytest.raises(TypeError):
            mapping["raw"] = "tampered"


def test_r2_hashes_and_raw_json_are_unchanged_after_mutation_attempt():
    snap = parse_artifact(profiles(profile(1)))
    record = snap.records[0]
    original_hash = record.record_hash
    original_raw_json = record.raw_json
    for _name, mapping in record.normalized:
        try:
            mapping["raw"] = "tampered"
        except TypeError:
            pass
    assert record.record_hash == original_hash
    assert record.raw_json == original_raw_json


# ---------------------------------------------------------------------------
# P1-R3 / OPEN-3 — strict contract version: parser and JSON Schema agree
# ---------------------------------------------------------------------------

VALID_VERSIONS = ["1.0", "1.1", "1.99", "1.00", "1.10"]
INVALID_VERSIONS = ["1.x", "1.0.1", "1", "2.0", "0.9", "10.0", "1.", ".1", "01.0", "001.5",
                    "1.0\n", "1.0\r", "1.0\r\n", " 1.0", "1.0 ", "\n1.0", "1.-1", "1.١",
                    "١.0"]


@pytest.mark.parametrize("version", VALID_VERSIONS)
def test_r3_valid_contract_versions_are_accepted(version):
    artifact = base_guide()
    artifact["contract_version"] = version
    snap = parse_artifact(artifact)
    assert snap.contract_version == version


@pytest.mark.parametrize("version", INVALID_VERSIONS)
def test_r3_invalid_contract_versions_are_rejected(version):
    artifact = base_guide()
    artifact["contract_version"] = version
    with pytest.raises(ArtifactError) as raised:
        parse_artifact(artifact)
    assert raised.value.code == "UNSUPPORTED_CONTRACT_VERSION"


@pytest.mark.parametrize("version", [1, 1.0, None, ["1.0"]])
def test_r3_non_string_contract_version_is_rejected(version):
    artifact = base_guide()
    artifact["contract_version"] = version
    with pytest.raises(ArtifactError) as raised:
        parse_artifact(artifact)
    assert raised.value.code in {"UNSUPPORTED_CONTRACT_VERSION", "NON_CANONICAL_VALUE"}


def test_r3_parser_and_json_schema_validator_accept_the_same_versions():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    version_schema = schema["properties"]["contract_version"]
    checker = jsonschema.Draft202012Validator(version_schema)
    artifact_checker = jsonschema.Draft202012Validator(schema)
    for version in VALID_VERSIONS + INVALID_VERSIONS:
        artifact = base_guide()
        artifact["contract_version"] = version
        try:
            parse_artifact(artifact)
            parser_ok = True
        except ArtifactError:
            parser_ok = False
        assert checker.is_valid(version) is parser_ok, repr(version)
        assert artifact_checker.is_valid(artifact) is parser_ok, repr(version)


# ---------------------------------------------------------------------------
# P1-R1 completion — no-host URLs and bracketed IPv6
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_url", ["https:///profile/123", "https://", "http://:80/",
                                     "http://?q=1", "http://#frag"])
def test_r1_url_without_host_is_not_a_source_key(bad_url):
    value = canonical.normalize_source_id(bad_url, "source_id")
    assert value.normalized is None and value.raw == bad_url
    assert [i.code for i in value.issues] == ["SOURCE_URL_MALFORMED"]
    snap = parse_artifact(profiles({"full_name": "T", "email": "t@example.invalid",
                                    "source_id": bad_url}))
    record, = snap.records
    assert record.raw["source_id"] == bad_url
    assert "SOURCE_URL_MALFORMED" in codes(record)
    assert record.record_key.method is KeyMethod.EMAIL_V1
    no_fallback = parse_artifact(profiles({"full_name": "T", "source_id": bad_url}))
    assert no_fallback.records[0].record_key.strength is KeyStrength.WEAK


@pytest.mark.parametrize("bad_url", ["https:///profile/123", "https://"])
def test_r1_artifact_source_url_without_host_raises(bad_url):
    artifact = profiles(profile(1))
    artifact["content"]["source_url"] = bad_url
    with pytest.raises(ArtifactError) as raised:
        parse_artifact(artifact)
    assert raised.value.code == "SOURCE_URL_MALFORMED"


@pytest.mark.parametrize(("raw", "expected"), [
    ("http://[::1]/a", "http://[::1]/a"),
    ("http://[::1]:8080/a/", "http://[::1]:8080/a"),
    ("https://[2001:DB8::1]:443/x", "https://[2001:db8::1]/x"),
    ("http://[2001:db8::1]:80/", "http://[2001:db8::1]/"),
    ("HTTPS://Repository.Example.invalid:443/Profile/7/",
     "https://repository.example.invalid/Profile/7"),
    ("http://repository.example.invalid:8080/p?id=A#top",
     "http://repository.example.invalid:8080/p?id=A"),
    ("http://192.0.2.10:80/p/", "http://192.0.2.10/p"),
    ("orcid-profile-42 ", "orcid-profile-42"),
])
def test_r1_valid_hosts_normalize_to_parseable_idempotent_urls(raw, expected):
    from urllib.parse import urlsplit
    value = canonical.normalize_source_id(raw)
    assert value.normalized == expected and value.issues == ()
    assert canonical.normalize_source_id(value.normalized).normalized == expected
    if expected.startswith("http"):
        original, again = urlsplit(raw.strip()), urlsplit(expected)
        assert again.hostname == original.hostname.lower()
        assert again.port in (original.port, None)


def test_r1_ipv6_profile_keeps_strong_key():
    snap = parse_artifact(profiles({"full_name": "T", "source_id": "http://[::1]:8080/p/9"}))
    key = snap.records[0].record_key
    assert key.value == "http://[::1]:8080/p/9" and key.strength is KeyStrength.STRONG


# ---------------------------------------------------------------------------
# Errata handover evidence
# ---------------------------------------------------------------------------

def test_errata_nested_normalized_access_cannot_mutate_stored_evidence():
    snap = parse_artifact(profiles(profile(1, orcid=ORCID_A)))
    record = snap.records[0]
    before = [(name, dict(mapping)) for name, mapping in record.normalized]
    assert all(isinstance(v, (str, type(None)))
               for _, mapping in record.normalized for v in mapping.values())
    with pytest.raises(TypeError):
        record.normalized["email"]["raw"] = "Changed"  # tuple: no string index
    by_name = dict(record.normalized)
    for attempt in (lambda m: m.__setitem__("raw", "Changed"),
                    lambda m: m.__delitem__("raw"),
                    lambda m: m.update(raw="Changed"),
                    lambda m: m.pop("raw"),
                    lambda m: m.popitem(),
                    lambda m: m.clear(),
                    lambda m: m.setdefault("extra", "Changed"),
                    lambda m: m.__ior__({"raw": "Changed"})):
        with pytest.raises(TypeError):
            attempt(by_name["email"])
    by_name["email"] = {"raw": "Changed"}  # rebinding a local copy of the index only
    assert [(name, dict(mapping)) for name, mapping in record.normalized] == before
    assert copy.deepcopy(snap) == snap


def test_errata_major_version_2_is_rejected():
    artifact = base_guide()
    artifact["contract_version"] = "2.0"
    with pytest.raises(ArtifactError) as raised:
        parse_artifact(artifact)
    assert raised.value.code == "UNSUPPORTED_CONTRACT_VERSION"


def test_errata_malformed_url_keeps_record_raw_and_claims():
    bad = {"full_name": "Test Lecturer", "email": "x@example.invalid",
           "orcid": ORCID_A, "source_id": "http://host:99999999/p"}
    snap = parse_artifact(profiles(bad, profile(2)))
    assert len(snap.records) == 2
    record = snap.records[0]
    assert record.raw == bad
    assert record.validation_status is ValidationStatus.INVALID
    assert record.record_key.strength is not KeyStrength.STRONG
    assert {c.claim_type for c in snap.claims if c.record_ref == record.ref} == {
        ClaimType.EMAIL_DECLARED, ClaimType.ORCID_DECLARED}


# ---------------------------------------------------------------------------
# OPEN-1 / OPEN-2 — in-place union and pickle (trusted, self-produced data only)
# ---------------------------------------------------------------------------

def test_open_1_inplace_or_does_not_mutate_normalized():
    record = parse_artifact(profiles(profile(1))).records[0]
    mapping = dict(record.normalized)["email"]
    original = dict(mapping)
    with pytest.raises(TypeError):
        mapping |= {"raw": "Changed"}
    assert dict(dict(record.normalized)["email"]) == original
    merged = mapping | {"raw": "Changed"}  # non-mutating union returns a new plain dict
    assert type(merged) is dict and dict(mapping) == original


def test_open_1_frozen_map_keeps_read_equality_copy_and_json_behaviour():
    record = parse_artifact(profiles(profile(1))).records[0]
    mapping = dict(record.normalized)["email"]
    plain = dict(mapping)
    assert mapping == plain and mapping["normalized"] == "lecturer1@example.invalid"
    assert json.dumps(mapping, sort_keys=True) == json.dumps(plain, sort_keys=True)
    for clone in (copy.copy(mapping), copy.deepcopy(mapping)):
        assert clone == plain and type(clone) is type(mapping)
        with pytest.raises(TypeError):
            clone["raw"] = "Changed"


def test_open_2_snapshot_pickle_roundtrip_stays_equal_and_immutable():
    import pickle
    snap = parse_artifact(base_guide())
    for protocol in range(2, pickle.HIGHEST_PROTOCOL + 1):
        clone = pickle.loads(pickle.dumps(snap, protocol=protocol))
        assert clone == snap
        assert clone.content_hash == snap.content_hash
        assert [(r.raw_json, r.record_hash) for r in clone.records] == [
            (r.raw_json, r.record_hash) for r in snap.records]
        assert copy.deepcopy(clone) == snap
        for record in clone.records:
            for _name, mapping in record.normalized:
                assert type(mapping).__name__ == "_FrozenMap"
                for attempt in (lambda m: m.__setitem__("raw", "x"),
                                lambda m: m.update(raw="x"),
                                lambda m: m.__ior__({"raw": "x"})):
                    with pytest.raises(TypeError):
                        attempt(mapping)


# ---------------------------------------------------------------------------
# Purity: only modules newly imported by source_claims count
# ---------------------------------------------------------------------------

_FORBIDDEN_MODULES = ("sqlalchemy", "psycopg2", "fastapi", "pydantic_settings", "app.main",
                      "app.core", "app.models", "app.api", "requests", "httpx",
                      "urllib.request", "http.client", "socket")


@pytest.mark.parametrize("flags", [("-I", "-S"), ("-I",)], ids=["no-site", "with-site"])
def test_package_imports_without_database_app_or_network_modules(flags):
    """Measures sys.modules before and after the import, so modules an interpreter
    preloads through site configuration are reported but not blamed on the package.
    The no-site run has no such preload, so it also catches a forbidden import that
    a with-site run could hide."""
    code = (
        "import json, sys; sys.path.insert(0, '.');"
        f"bad = {_FORBIDDEN_MODULES!r};"
        "hit = lambda names: sorted(m for m in names"
        " if any(m == b or m.startswith(b + '.') for b in bad));"
        "before = set(sys.modules);"
        "import app.services.source_claims.parser, app.services.source_claims.analysis;"
        "print(json.dumps({'preloaded': hit(before), 'new': hit(set(sys.modules) - before)}))"
    )
    result = subprocess.run([sys.executable, *flags, "-c", code], cwd=BACKEND,
                            capture_output=True, text=True, timeout=60, check=True)
    report = json.loads(result.stdout)
    print(flags, report)
    assert report["new"] == [], result.stdout + result.stderr
