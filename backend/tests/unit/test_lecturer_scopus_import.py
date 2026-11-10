"""JSON import references and review plans, using only synthetic in-memory SQLite."""

import copy
import json
from unittest import TestCase
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.governance import User
from app.models.identity import LecturerScopusIdentity
from app.models.lecturer_primary_scopus import LecturerPrimaryScopusEvent
from app.models.master_lecturer import Lecturer, LecturerSourceSnapshot
from app.models.publication import ScopusAuthor
from app.services.lecturer_dataset.importer import LecturerImportService, LecturerPreviewService
from app.services.lecturer_dataset.parser import DatasetValidationError, parse_and_validate
from app.services.lecturer_dataset.scopus_references import pending_scopus_imports
from tests.source_staging_fixtures import make_sqlite_engine


def dataset():
    url = "https://repository.example.invalid/giang-vien/synthetic/"
    return {
        "dataset": {"schema_version": "1.1", "record_count": 1, "name": "Synthetic"},
        "lecturers": [{
            "source_id": url, "profile_url": url, "full_name": "Synthetic Lecturer",
            "institutional_email": "lecturer@example.invalid", "academic_degree": "TS",
            "is_active": True, "scopus_ids": ["57000000001", "57000000002"],
            "primary_scopus_id": "57000000002",
            "provenance": {"source_system": "ictu_dspace_archive", "source_urls": [url]},
        }],
    }


class LecturerScopusImportTests(TestCase):
    def setUp(self):
        self.engine = make_sqlite_engine()
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.actor = User(
            id=uuid4(), email="admin@example.invalid", password_hash="synthetic",
            display_name="Synthetic Admin", role="ADMIN", is_active=True,
        )
        self.db.add(self.actor)
        self.db.commit()

    def preview(self, payload):
        return LecturerPreviewService().preview(
            self.db, filename="synthetic.json", content=json.dumps(payload).encode(),
        )

    def import_dataset(self, payload):
        return LecturerImportService().import_dataset(
            self.db, filename="synthetic.json", content=json.dumps(payload).encode(),
            actor=self.actor,
        )

    def assert_no_identity_approval(self):
        for model in (LecturerScopusIdentity, LecturerPrimaryScopusEvent):
            self.assertEqual(self.db.scalar(select(func.count()).select_from(model)), 0)

    def test_parser_preserves_ids_as_strings_and_primary(self):
        payload = dataset()
        payload["lecturers"][0]["scopus_ids"][0] = " 57000000001 "
        result = parse_and_validate(json.dumps(payload).encode())["lecturers"][0]
        self.assertEqual(result["scopus_ids"], ["57000000001", "57000000002"])
        self.assertEqual(result["primary_scopus_id"], "57000000002")

    def test_invalid_ids_are_rejected_instead_of_silently_dropped(self):
        bad_values = [None, "57000000001", [57000000001], ["abc"], [""]]
        for ids in bad_values:
            with self.subTest(ids=ids):
                payload = dataset()
                payload["lecturers"][0]["scopus_ids"] = ids
                with self.assertRaises(DatasetValidationError):
                    parse_and_validate(json.dumps(payload).encode())

    def test_duplicate_ids_and_unlisted_primary_are_rejected(self):
        for overrides in [
            {"scopus_ids": ["57000000001", "57000000001"]},
            {"primary_scopus_id": "57000000003"},
            {"primary_scopus_id": 57000000002},
        ]:
            with self.subTest(overrides=overrides):
                payload = dataset()
                payload["lecturers"][0].update(overrides)
                with self.assertRaises(DatasetValidationError):
                    parse_and_validate(json.dumps(payload).encode())

    def test_preview_lists_every_pair_without_creating_any_records(self):
        result = self.preview(dataset())
        self.assertEqual(result.create, 1)
        self.assertEqual(len(result.scopus_review_items), 1)
        item = result.scopus_review_items[0]
        self.assertIsNone(item["lecturer_id"])
        self.assertEqual(item["scopus_ids"], ["57000000001", "57000000002"])
        self.assertEqual(item["primary_scopus_id"], "57000000002")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Lecturer)), 0)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(LecturerSourceSnapshot)), 0,
        )
        self.assert_no_identity_approval()

    def test_import_keeps_references_and_resolves_real_uuid_for_explicit_review(self):
        result = self.import_dataset(dataset())
        lecturer = self.db.scalar(select(Lecturer))
        snapshot = self.db.scalar(select(LecturerSourceSnapshot))
        self.assertEqual(UUID(result.scopus_review_items[0]["lecturer_id"]), lecturer.id)
        self.assertEqual(snapshot.raw_payload["scopus_ids"], ["57000000001", "57000000002"])
        self.assertEqual(snapshot.raw_payload["primary_scopus_id"], "57000000002")
        self.assert_no_identity_approval()

    def test_reimport_plan_uses_existing_lecturer_not_a_new_uuid(self):
        first = self.import_dataset(dataset())
        second = self.import_dataset(copy.deepcopy(dataset()))
        self.assertEqual(first.scopus_review_items, second.scopus_review_items)
        self.assertEqual(second.created, 0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Lecturer)), 1)
        self.assert_no_identity_approval()

    def test_legacy_json_without_scopus_fields_still_imports(self):
        payload = dataset()
        del payload["lecturers"][0]["scopus_ids"]
        del payload["lecturers"][0]["primary_scopus_id"]
        self.assertEqual(self.preview(payload).scopus_review_items, [])
        self.assertEqual(self.import_dataset(payload).scopus_review_items, [])
        self.assert_no_identity_approval()

    def test_retained_ids_are_available_after_import_without_reupload(self):
        result = self.import_dataset(dataset())
        items = pending_scopus_imports(self.db)
        self.assertEqual(items, result.scopus_review_items)
        lid = UUID(items[0]["lecturer_id"])
        self.assertEqual(pending_scopus_imports(self.db, lid), items)
        self.assertEqual(pending_scopus_imports(self.db, uuid4()), [])
        self.assert_no_identity_approval()

    def test_latest_empty_reference_list_does_not_revive_an_older_import(self):
        self.import_dataset(dataset())
        payload = dataset()
        payload["lecturers"][0].update(scopus_ids=[], primary_scopus_id=None)
        self.import_dataset(payload)
        self.assertEqual(pending_scopus_imports(self.db), [])

    def test_reviewed_ids_disappear_from_pending_only_after_primary_is_confirmed(self):
        self.import_dataset(dataset())
        lecturer = self.db.scalar(select(Lecturer))
        primary_identity = None
        for sid in ["57000000001", "57000000002"]:
            author = ScopusAuthor(id=uuid4(), scopus_id=sid, preferred_name=sid)
            identity = LecturerScopusIdentity(
                id=uuid4(), lecturer_id=lecturer.id, scopus_author_id=author.id,
                status="APPROVED",
            )
            self.db.add_all([author, identity])
            primary_identity = identity
        self.db.flush()
        self.assertEqual(len(pending_scopus_imports(self.db)), 1)
        self.db.add(LecturerPrimaryScopusEvent(
            seq=1, lecturer_id=lecturer.id, identity_id=primary_identity.id,
            action="SET", reason="Synthetic reviewer confirmation", acted_by_user_id=self.actor.id,
        ))
        self.db.flush()
        self.assertEqual(pending_scopus_imports(self.db), [])
