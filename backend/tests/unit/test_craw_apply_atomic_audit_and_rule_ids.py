"""G15: Craw apply writes data and its success audit in ONE commit. G16: run rule ids."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.lecturer_dataset import craw_ingestion_workflow as workflow
from app.services.matching.candidate_generator import RULE_ORDER
from app.services.matching.candidate_persistence import CANDIDATE_RULE_IDS


class _Result:
    snapshots_created = snapshots_reused = known_publications_created = 0
    known_publications_reused = source_duplicates_collapsed = source_urls_collapsed = 0
    invalid_records = 0
    unmapped_lecturers = ()


class _Db:
    def __init__(self, fail_first_commit: bool = False) -> None:
        self.events: list[str] = []
        self.fail_first_commit = fail_first_commit

    def execute(self, *_a, **_k):
        return SimpleNamespace(scalar_one=lambda: True)

    def add(self, row):
        self.events.append(f"add:{row.action}")

    def commit(self):
        self.events.append("commit")
        if self.fail_first_commit and self.events.count("commit") == 1:
            raise RuntimeError("audit insert failed")

    def rollback(self):
        self.events.append("rollback")


@pytest.fixture
def patched(monkeypatch):
    calls = {}
    monkeypatch.setattr(workflow, "compute_preview", lambda db, d: SimpleNamespace(
        can_apply=True, fingerprint="f", blocked_reason=None))
    monkeypatch.setattr(workflow, "_load_source", lambda d: (SimpleNamespace(sources=[]), None))

    class _Service:
        def apply(self, db, sources, *, commit=True):
            calls["commit"] = commit
            db.events.append("apply")
            return _Result()

    monkeypatch.setattr(workflow, "KnownPublicationIngestionService", _Service)
    return calls


def test_data_and_success_audit_commit_together_once(patched, tmp_path):
    db = _Db()
    out = workflow.apply_ingestion(db, fingerprint="f", actor_user_id=__import__("uuid").uuid4(),
                                   directory=tmp_path)
    assert out["result"]["snapshots_created"] == 0
    assert patched["commit"] is False                      # apply must not commit by itself
    assert db.events == ["apply", f"add:{workflow.APPLIED_ACTION}", "commit"]


def test_audit_failure_rolls_back_the_data_and_records_a_failure(patched, tmp_path):
    db = _Db(fail_first_commit=True)
    with pytest.raises(workflow.CrawIngestionWorkflowError) as exc:
        workflow.apply_ingestion(db, fingerprint="f", actor_user_id=__import__("uuid").uuid4(),
                                 directory=tmp_path)
    assert exc.value.code == "CRAW_APPLY_FAILED"
    assert db.events == ["apply", f"add:{workflow.APPLIED_ACTION}", "commit", "rollback",
                         f"add:{workflow.FAILED_ACTION}", "commit"]


def test_run_metadata_lists_every_rule_the_generator_executes():
    assert tuple(CANDIDATE_RULE_IDS) == tuple(RULE_ORDER) and len(CANDIDATE_RULE_IDS) == 7
