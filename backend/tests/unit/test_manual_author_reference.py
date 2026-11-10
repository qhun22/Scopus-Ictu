"""Pure unit checks with mock sessions; no database engine or connection is used."""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.lecturer_scopus import AssignScopusIdentityRequest
from app.models.governance import AuditEvent
from app.models.identity import LecturerScopusIdentity
from app.models.master_lecturer import Lecturer
from app.models.publication import PublicationAuthor, ScopusAuthor
from app.services.matching import manual_candidate as manual
from app.services.normalization.scopus_author_normalizer import AuthorNormalizer


class ManualAuthorReferenceTests(TestCase):
    def setUp(self):
        self.db = MagicMock(spec=Session)
        self.reviewer = SimpleNamespace(
            id=uuid4(), email="reviewer@example.invalid", role="ADMIN", is_active=True
        )
        self.lecturer = Lecturer(id=uuid4(), full_name="Example Lecturer")
        self.scopus_id = "12345678901"
        self.reason = "Reviewed against https://example.invalid/author-list"
        self.db.get.return_value = self.lecturer

    def register(self, **overrides):
        arguments = dict(scopus_id=self.scopus_id, reviewer=self.reviewer, reason=self.reason)
        arguments.update(overrides)
        return manual._register_author_reference(self.db, **arguments)

    def assign(self, **overrides):
        arguments = dict(
            lecturer_id=self.lecturer.id,
            scopus_id=self.scopus_id,
            reviewer=self.reviewer,
            reason=self.reason,
        )
        arguments.update(overrides)
        return manual.assign_scopus_identity(self.db, **arguments)

    def test_registration_records_id_and_audit_without_name_or_publications(self):
        author = self.register()
        added = [call.args[0] for call in self.db.add.call_args_list]
        self.assertEqual(author.preferred_name, self.scopus_id)
        self.assertEqual(author.scopus_id, self.scopus_id)
        audit = next(row for row in added if isinstance(row, AuditEvent))
        self.assertEqual(audit.action, "SCOPUS_AUTHOR_REFERENCE_CREATED")
        self.assertEqual(audit.actor_user_id, self.reviewer.id)
        self.assertEqual(audit.reason, self.reason)
        self.assertFalse(audit.event_metadata["name_available"])
        self.assertFalse(
            any(isinstance(row, (LecturerScopusIdentity, PublicationAuthor)) for row in added)
        )
        self.db.commit.assert_not_called()

    def test_unimported_author_still_requires_explicit_opt_in(self):
        self.db.scalar.return_value = None
        with self.assertRaises(manual.ManualCandidateError) as error:
            self.assign()
        self.assertEqual(error.exception.code, "SCOPUS_AUTHOR_NOT_FOUND")
        self.db.add.assert_not_called()
        self.db.begin_nested.assert_not_called()

    def test_new_author_assignment_still_uses_candidate_review(self):
        candidate = SimpleNamespace(id=uuid4(), version=1)
        observation = SimpleNamespace(id=uuid4())
        result_identity = uuid4()
        self.db.scalar.side_effect = [None, None, None]
        self.db.get.side_effect = lambda model, *_args, **_kwargs: (
            self.lecturer if model is Lecturer else candidate
        )
        with ExitStack() as stack:
            create = stack.enter_context(
                patch.object(
                    manual,
                    "create_manual_candidate",
                    return_value=SimpleNamespace(candidate_id=candidate.id),
                )
            )
            stack.enter_context(
                patch.object(manual, "current_reviewable_observation", return_value=observation)
            )
            review = stack.enter_context(patch.object(manual, "CandidateReviewService"))
            review.return_value.accept_candidate.return_value = SimpleNamespace(
                resulting_identity_id=result_identity
            )
            result = self.assign(create_author_if_missing=True)
        self.assertEqual(result.identity_id, result_identity)
        self.assertFalse(result.already_approved)
        create.assert_called_once()
        command = review.return_value.accept_candidate.call_args.args[0]
        self.assertEqual(command.reviewer_user_id, self.reviewer.id)
        self.assertEqual(command.reason, self.reason)
        self.assertEqual(command.observation_id, observation.id)
        self.assertFalse(
            any(
                isinstance(call.args[0], LecturerScopusIdentity)
                for call in self.db.add.call_args_list
            )
        )

    def test_existing_approved_pair_is_reused_without_registering_an_author(self):
        author = ScopusAuthor(id=uuid4(), scopus_id=self.scopus_id, preferred_name="Example Author")
        identity = SimpleNamespace(id=uuid4(), status="APPROVED")
        self.db.scalar.side_effect = [author, identity]
        result = self.assign(create_author_if_missing=True)
        self.assertTrue(result.already_approved)
        self.assertEqual(result.identity_id, identity.id)
        self.db.add.assert_not_called()

    def test_invalid_reason_never_registers_an_author(self):
        for reason in ("", " ", "x" * 4001, "bad\x00reason"):
            with self.subTest(reason_length=len(reason)):
                with self.assertRaises(manual.ManualCandidateError):
                    self.register(reason=reason.strip())
        self.db.add.assert_not_called()

    def test_registration_rejects_non_numeric_ids(self):
        for scopus_id in ("", "not-an-id", "https://example.invalid/author", "１２３", "1" * 51):
            with self.subTest(scopus_id=scopus_id):
                with self.assertRaises(manual.ManualCandidateError):
                    self.register(scopus_id=scopus_id)
        self.db.add.assert_not_called()

    def test_inactive_and_lecturer_accounts_cannot_register_authors(self):
        for role, active in (("LECTURER", True), ("ADMIN", False), ("REVIEWER", False)):
            reviewer = SimpleNamespace(id=uuid4(), role=role, is_active=active)
            with self.subTest(role=role, active=active):
                with self.assertRaises(manual.ManualCandidateError):
                    self.register(reviewer=reviewer)
        self.db.add.assert_not_called()

    def test_concurrent_registration_reuses_unique_winner_without_outer_rollback(self):
        winner = ScopusAuthor(
            id=uuid4(), scopus_id=self.scopus_id, preferred_name="Imported Author"
        )
        original = SimpleNamespace(
            pgcode="23505", diag=SimpleNamespace(constraint_name="uq_scopus_authors_scopus_id")
        )
        self.db.flush.side_effect = IntegrityError("insert", {}, original)
        self.db.scalar.return_value = winner
        self.assertIs(self.register(), winner)
        self.db.rollback.assert_not_called()
        self.assertFalse(
            any(isinstance(call.args[0], AuditEvent) for call in self.db.add.call_args_list)
        )

    def test_unrelated_integrity_error_is_not_treated_as_an_author_race(self):
        original = SimpleNamespace(
            pgcode="23514", diag=SimpleNamespace(constraint_name="some_check")
        )
        self.db.flush.side_effect = IntegrityError("insert", {}, original)
        with self.assertRaises(IntegrityError):
            self.register()
        self.db.scalar.assert_not_called()

    def test_api_registration_flag_defaults_to_false(self):
        request = AssignScopusIdentityRequest(scopus_id=self.scopus_id, reason=self.reason)
        self.assertFalse(request.create_author_if_missing)
        opted_in = AssignScopusIdentityRequest(
            scopus_id=self.scopus_id, reason=self.reason, create_author_if_missing=True
        )
        self.assertTrue(opted_in.create_author_if_missing)

    def test_import_fills_reference_name_without_replacing_author_identity(self):
        author = ScopusAuthor(id=uuid4(), scopus_id=self.scopus_id, preferred_name=self.scopus_id)
        self.db.query.return_value.filter.return_value.first.return_value = author
        occurrence = SimpleNamespace(
            scopus_id=self.scopus_id, full_name="Example, Author", display_name="Author E."
        )
        normalizer = AuthorNormalizer()
        self.assertIs(normalizer._upsert_author(self.db, occurrence), author)
        self.assertEqual(author.preferred_name, "Example, Author")
        self.assertEqual(normalizer.counters.authors_existing, 1)
        self.db.add.assert_not_called()

    def test_import_does_not_overwrite_an_existing_real_author_name(self):
        author = ScopusAuthor(
            id=uuid4(), scopus_id=self.scopus_id, preferred_name="Existing Author"
        )
        self.db.query.return_value.filter.return_value.first.return_value = author
        occurrence = SimpleNamespace(
            scopus_id=self.scopus_id, full_name="Different spelling", display_name="Author E."
        )
        AuthorNormalizer()._upsert_author(self.db, occurrence)
        self.assertEqual(author.preferred_name, "Existing Author")

    def test_import_fills_name_when_a_manual_reference_wins_the_insert_race(self):
        author = ScopusAuthor(id=uuid4(), scopus_id=self.scopus_id, preferred_name=self.scopus_id)
        self.db.query.return_value.filter.return_value.first.side_effect = [None, author]
        occurrence = SimpleNamespace(
            scopus_id=self.scopus_id, full_name="Example, Author", display_name="Author E."
        )
        conflict = IntegrityError("insert", {}, Exception("synthetic duplicate"))
        with patch(
            "app.services.normalization.scopus_author_normalizer._insert_in_savepoint",
            return_value=conflict,
        ):
            result = AuthorNormalizer()._upsert_author(self.db, occurrence)
        self.assertIs(result, author)
        self.assertEqual(author.preferred_name, "Example, Author")
