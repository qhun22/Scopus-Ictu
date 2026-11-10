"""Synthetic export regression checks on in-memory SQLite, never the application DB."""

import json
from datetime import UTC, datetime
from unittest import TestCase
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.identity import LecturerScopusIdentity
from app.models.lecturer_primary_scopus import LecturerPrimaryScopusEvent
from app.models.master_lecturer import Lecturer, LecturerSourceSnapshot
from app.models.publication import ScopusAuthor
from app.services.lecturer_dataset.exporter import ICTU_SOURCE_SYSTEM, build_lecturer_export
from app.services.lecturer_dataset.parser import parse_and_validate
from tests.source_staging_fixtures import make_sqlite_engine

NOW = datetime(2026, 11, 10, tzinfo=UTC)


class LecturerScopusExportTests(TestCase):
    def setUp(self):
        self.engine = make_sqlite_engine()
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.lecturer = self.make_lecturer()
        self.seq = 0

    def make_lecturer(self, *, sourced=True):
        lid = uuid4()
        url = f"https://repository.example.invalid/giang-vien/{lid}/"
        lecturer = Lecturer(
            id=lid, full_name="Synthetic Lecturer", full_name_normalized="synthetic lecturer",
            email=f"lecturer-{lid}@example.invalid", repository_profile_url=url,
            is_active=True, created_at=NOW, updated_at=NOW,
        )
        self.db.add(lecturer)
        if sourced:
            self.db.add(LecturerSourceSnapshot(
                id=uuid4(), lecturer_id=lid, source_system=ICTU_SOURCE_SYSTEM,
                source_url=url, snapshot_hash="0" * 64, parser_version="test/1.0",
                validation_status="VALID", fetched_at=NOW, created_at=NOW,
                raw_payload={
                    "source_id": url,
                    # Stale source declarations must never replace current saved IDs.
                    "scopus_ids": ["57000000999"], "primary_scopus_id": "57000000999",
                    "provenance": {"source_urls": [url], "source_record_id": url},
                },
            ))
        self.db.flush()
        return lecturer

    def identity(self, number, *, status="APPROVED", lecturer=None):
        author = ScopusAuthor(
            id=uuid4(), scopus_id=str(57000000000 + number),
            preferred_name=str(57000000000 + number), created_at=NOW, updated_at=NOW,
        )
        identity = LecturerScopusIdentity(
            id=uuid4(), lecturer_id=(lecturer or self.lecturer).id,
            scopus_author_id=author.id, status=status, created_at=NOW, updated_at=NOW,
        )
        self.db.add_all([author, identity])
        self.db.flush()
        return identity, author.scopus_id

    def choose(self, identity=None, *, lecturer=None):
        self.seq += 1
        self.db.add(LecturerPrimaryScopusEvent(
            seq=self.seq, lecturer_id=(lecturer or self.lecturer).id,
            identity_id=identity.id if identity else None,
            action="SET" if identity else "CLEAR", reason="Synthetic human selection",
            acted_by_user_id=uuid4(), created_at=NOW,
        ))
        self.db.flush()

    def export(self):
        self.db.flush()
        return build_lecturer_export(self.db, now=NOW).payload

    def test_all_saved_ids_without_publications_and_current_primary_are_exported(self):
        expected = []
        for number in [5, 1, 4, 2, 3]:
            identity, scopus_id = self.identity(number)
            expected.append(scopus_id)
            if number == 4:
                self.choose(identity)
        for number, status in [(6, "CANDIDATE"), (7, "REJECTED"), (8, "REVOKED")]:
            self.identity(number, status=status)
        statements = []
        event.listen(self.engine, "before_cursor_execute",
                     lambda _c, _cur, statement, _p, _ctx, _many: statements.append(statement))

        payload = self.export()
        record = payload["lecturers"][0]
        self.assertEqual(record["scopus_ids"], sorted(expected))
        self.assertEqual(record["primary_scopus_id"], "57000000004")
        self.assertEqual(record["known_publications"], [])
        self.assertEqual(payload["dataset"]["export"]["scopus_identity_count"], 5)
        self.assertEqual(payload["dataset"]["export"]["primary_scopus_id_count"], 1)
        self.assertTrue(all(s.lstrip().upper().startswith("SELECT") for s in statements))
        self.assertFalse(self.db.new or self.db.dirty or self.db.deleted)
        # The additive fields keep the existing import envelope compatible.
        parsed = parse_and_validate(json.dumps(payload).encode())
        self.assertEqual(len(parsed["lecturers"]), 1)

    def test_latest_selection_wins(self):
        first, first_id = self.identity(1)
        second, second_id = self.identity(2)
        self.choose(first)
        self.choose(second)
        record = self.export()["lecturers"][0]
        self.assertEqual(record["scopus_ids"], [first_id, second_id])
        self.assertEqual(record["primary_scopus_id"], second_id)

    def test_clear_does_not_revive_an_older_primary(self):
        identity, scopus_id = self.identity(1)
        self.choose(identity)
        self.choose()
        record = self.export()["lecturers"][0]
        self.assertEqual(record["scopus_ids"], [scopus_id])
        self.assertIsNone(record["primary_scopus_id"])

    def test_revoked_primary_does_not_fall_back_to_previous_selection(self):
        first, first_id = self.identity(1)
        revoked, _ = self.identity(2, status="REVOKED")
        self.choose(first)
        self.choose(revoked)
        record = self.export()["lecturers"][0]
        self.assertEqual(record["scopus_ids"], [first_id])
        self.assertIsNone(record["primary_scopus_id"])

    def test_primary_from_another_lecturer_is_not_exported(self):
        other = self.make_lecturer()
        foreign, _ = self.identity(1, lecturer=other)
        _, own_id = self.identity(2)
        self.choose(foreign)
        records = self.export()["lecturers"]
        own_record = next(r for r in records if r["institutional_email"] == self.lecturer.email)
        self.assertEqual(own_record["scopus_ids"], [own_id])
        self.assertIsNone(own_record["primary_scopus_id"])

    def test_single_saved_id_does_not_become_primary_automatically(self):
        _, scopus_id = self.identity(1)
        record = self.export()["lecturers"][0]
        self.assertEqual(record["scopus_ids"], [scopus_id])
        self.assertIsNone(record["primary_scopus_id"])

    def test_empty_list_and_source_export_boundary(self):
        manual = self.make_lecturer(sourced=False)
        identity, _ = self.identity(1, lecturer=manual)
        self.choose(identity, lecturer=manual)
        payload = self.export()
        self.assertEqual(len(payload["lecturers"]), 1)
        self.assertEqual(payload["lecturers"][0]["scopus_ids"], [])
        self.assertIsNone(payload["lecturers"][0]["primary_scopus_id"])
        self.assertEqual(payload["dataset"]["export"]["scopus_identity_count"], 0)
        self.assertEqual(payload["dataset"]["export"]["primary_scopus_id_count"], 0)
