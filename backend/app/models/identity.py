"""Identity / evidence models — M0 scaffolds.

Tables (from Architecture v1.1):
  11. lecturer_scopus_identities
  12. identity_evidence
  13. mapping_reviews

See master_lecturer.py for the rationale behind M0's inert base.
"""

from __future__ import annotations

_SENTINEL_BASE = object


class LecturerScopusIdentity(_SENTINEL_BASE):
    """Approved lecturer ↔ Scopus author mapping — M0 skeleton.

    This is the system's ground truth per ADR-004.
    TODO(M1): lecturer_id FK, scopus_author_id FK, status, approved_by,
    approved_at, source_kind, version, etc.
    """

    __tablename__ = "lecturer_scopus_identities"


class IdentityEvidence(_SENTINEL_BASE):
    """Evidence supporting an identity decision — M0 skeleton.

    Identity and evidence are separate (see ADR-004).
    TODO(M1): identity_id FK, evidence_kind, payload, captured_at, etc.
    """

    __tablename__ = "identity_evidence"


class MappingReview(_SENTINEL_BASE):
    """Review workflow record for a mapping — M0 skeleton.

    TODO(M1): identity_id FK, reviewer_id, decision, reason, reviewed_at, etc.
    """

    __tablename__ = "mapping_reviews"