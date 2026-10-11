"""Unit tests for the source_title correction CLI (pure planning + audit shape)."""

from __future__ import annotations

import re
import uuid

import pytest

from scripts import correct_publication_source_title as cli
from scripts.correct_publication_source_title import (
    AUDIT_ACTION,
    AUDIT_ACTOR_SERVICE,
    AUDIT_ENTITY_TYPE,
    SourceRow,
    Plan,
    build_plan,
    classify,
)

IMPORT_ID = uuid.uuid4()


def row(**kw) -> SourceRow:
    base = dict(
        publication_id=uuid.uuid4(),
        eid="2-s2.0-100",
        version=1,
        current_source_title="Scopus",
        raw_record_id=uuid.uuid4(),
        raw_eid="2-s2.0-100",
        payload_eid="2-s2.0-100",
        raw_validation_status="VALID",
        import_id=IMPORT_ID,
        import_status="APPLIED",
        raw_source="Scopus",
        raw_source_title="Lecture Notes in Networks and Systems",
        publication_raw_link_count=1,
        raw_record_link_count=1,
    )
    base.update(kw)
    return SourceRow(**base)


class TestClassify:
    def test_eligible_row_gets_source_title_not_provider(self) -> None:
        assert classify(row()) == ("Lecture Notes in Networks and Systems", None)

    def test_whitespace_is_trimmed(self) -> None:
        assert classify(row(raw_source_title="  Journal A \n"))[0] == "Journal A"

    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_missing_or_blank_source_title_is_skipped_never_filled_with_provider(self, blank) -> None:
        assert classify(row(raw_source_title=blank)) == (None, cli.R_SOURCE_TITLE_MISSING)

    def test_manual_edit_is_not_overwritten(self) -> None:
        assert classify(row(current_source_title="Edited by hand")) == (None, cli.R_NOT_WRONG_VALUE)

    def test_already_corrected_row_is_skipped_so_reruns_do_nothing(self) -> None:
        corrected = row(current_source_title="Lecture Notes in Networks and Systems")
        assert classify(corrected) == (None, cli.R_ALREADY_CORRECT)

    def test_stored_value_must_equal_raw_provider_value(self) -> None:
        assert classify(row(raw_source="Other provider")) == (None, cli.R_STORED_NOT_PROVIDER_VALUE)

    @pytest.mark.parametrize("kw", [{"publication_raw_link_count": 2}, {"raw_record_link_count": 2}])
    def test_provenance_must_be_one_to_one(self, kw) -> None:
        assert classify(row(**kw)) == (None, cli.R_PROVENANCE_NOT_1TO1)

    @pytest.mark.parametrize("status", ["CANCELLED", "STAGED", "FAILED", None])
    def test_import_must_be_applied(self, status) -> None:
        assert classify(row(import_status=status)) == (None, cli.R_IMPORT_NOT_APPLIED)

    def test_raw_record_must_be_valid(self) -> None:
        assert classify(row(raw_validation_status="INVALID")) == (None, cli.R_RAW_NOT_VALID)

    @pytest.mark.parametrize("kw", [{"raw_eid": "2-s2.0-999"}, {"payload_eid": "2-s2.0-999"}, {"raw_eid": None}])
    def test_eid_must_match(self, kw) -> None:
        assert classify(row(**kw)) == (None, cli.R_EID_MISMATCH)

    def test_eid_whitespace_is_tolerated_like_the_normalizer(self) -> None:
        assert classify(row(raw_eid=" 2-s2.0-100 "))[1] is None

    def test_real_source_title_equal_to_provider_name_is_not_a_change(self) -> None:
        assert classify(row(raw_source_title="Scopus")) == (None, cli.R_NO_CHANGE)


class TestBuildPlan:
    def test_counts_fingerprint_and_distinct_titles(self) -> None:
        rows = [
            row(eid="2-s2.0-1", raw_eid="2-s2.0-1", payload_eid="2-s2.0-1", raw_source_title="Journal A"),
            row(eid="2-s2.0-2", raw_eid="2-s2.0-2", payload_eid="2-s2.0-2", raw_source_title="Journal A"),
            row(eid="2-s2.0-3", raw_eid="2-s2.0-3", payload_eid="2-s2.0-3", raw_source_title="Journal B"),
            row(eid="2-s2.0-4", raw_eid="2-s2.0-4", payload_eid="2-s2.0-4", raw_source_title=None),
        ]
        plan = build_plan(rows, wrong_total=4)
        assert len(plan.corrections) == 3
        assert plan.skipped == {cli.R_SOURCE_TITLE_MISSING: 1}
        assert plan.by_import() == {str(IMPORT_ID): 3}
        assert dict(plan.new_value_counts()) == {"Journal A": 2, "Journal B": 1}
        assert all(c.old == "Scopus" for c in plan.corrections)

    def test_fingerprint_is_order_independent_and_changes_with_content(self) -> None:
        a = row(eid="2-s2.0-1", raw_eid="2-s2.0-1", payload_eid="2-s2.0-1", raw_source_title="J1")
        b = row(eid="2-s2.0-2", raw_eid="2-s2.0-2", payload_eid="2-s2.0-2", raw_source_title="J2")
        assert build_plan([a, b], 2).fingerprint == build_plan([b, a], 2).fingerprint
        changed = row(
            publication_id=b.publication_id, eid="2-s2.0-2", raw_eid="2-s2.0-2", payload_eid="2-s2.0-2",
            raw_source_title="J3",
        )
        assert build_plan([a, b], 2).fingerprint != build_plan([a, changed], 2).fingerprint

    def test_publication_with_two_raw_rows_is_skipped_once(self) -> None:
        pid = uuid.uuid4()
        rows = [row(publication_id=pid), row(publication_id=pid)]
        plan = build_plan(rows, wrong_total=1)
        assert plan.corrections == ()
        assert plan.skipped == {cli.R_PROVENANCE_NOT_1TO1: 1}

    def test_wrong_value_rows_without_any_raw_source_are_reported(self) -> None:
        plan = build_plan([row()], wrong_total=3)
        assert len(plan.corrections) == 1
        assert plan.skipped == {cli.R_NO_RAW_SOURCE: 2}

    def test_rerun_after_correction_selects_nothing(self) -> None:
        corrected = [row(current_source_title="Journal A", raw_source_title="Journal A")]
        # After the update the query (source_title = 'Scopus') returns no rows at all.
        assert build_plan([], wrong_total=0).corrections == ()
        assert build_plan(corrected, wrong_total=1).corrections == ()


class TestAuditShape:
    """Audit rows must satisfy the audit_events CHECK constraints (format + SYSTEM actor)."""

    def test_identity_values_satisfy_check_constraints(self) -> None:
        assert re.fullmatch(r"[A-Z][A-Z0-9_]*", AUDIT_ACTION) and len(AUDIT_ACTION) <= 64
        assert re.fullmatch(r"[a-z][a-z0-9_]*", AUDIT_ENTITY_TYPE)
        assert AUDIT_ACTOR_SERVICE.strip()

    def test_event_is_a_system_event_without_payload_or_secrets(self) -> None:
        plan = build_plan([row()], wrong_total=1)
        event = cli._audit_event(str(IMPORT_ID), 1, plan, 1)
        assert event.actor_type == "SYSTEM"
        assert event.actor_user_id is None
        assert event.actor_service == AUDIT_ACTOR_SERVICE
        assert event.entity_id == IMPORT_ID
        assert isinstance(event.before_state, dict) and isinstance(event.after_state, dict)
        flat = repr((event.before_state, event.after_state, event.event_metadata, event.reason)).lower()
        for forbidden in ("raw_payload", "password", "token", "secret", "abstract"):
            assert forbidden not in flat
        assert event.event_metadata["publications_updated"] == 1
        assert event.event_metadata["plan_sha256"] == plan.fingerprint
