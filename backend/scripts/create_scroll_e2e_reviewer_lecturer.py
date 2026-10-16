"""One-off: create REVIEWER and LECTURER test accounts for the Home
placeholder E2E verification, on the test DB only
(scopus_ictu_test_withjson_r2_20261011).

Idempotent: does nothing for an account that already exists. Never touches
any other user. Not wired into any app startup path; run manually and
delete when the E2E session is done if desired.
"""

from __future__ import annotations

import os
import uuid

from sqlalchemy import func

from app.core.database import get_session_factory
from app.core.security import password_hasher
from app.models.governance import AuditEvent, User

ACCOUNTS = [
    ("scroll.e2e.reviewer@ictu.edu.vn", "REVIEWER", "Scroll E2E Reviewer"),
    ("scroll.e2e.lecturer@ictu.edu.vn", "LECTURER", "Scroll E2E Lecturer"),
]
PASSWORD = os.environ["SCROLL_E2E_PASSWORD"]


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        for email, role, display_name in ACCOUNTS:
            existing = (
                session.query(User)
                .filter(func.lower(User.email) == email.lower())
                .first()
            )
            if existing is not None:
                print(f"[OK] Account '{email}' already exists (ID: {existing.id}). Nothing to do.")
                continue

            user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=password_hasher.hash(PASSWORD),
                display_name=display_name,
                role=role,
                lecturer_id=None,
                is_active=True,
            )
            session.add(user)
            session.flush()
            session.add(AuditEvent(
                entity_type="users",
                entity_id=user.id,
                action="DEMO_ACCOUNT_SEEDED",
                actor_type="SYSTEM",
                actor_user_id=None,
                actor_service="create_scroll_e2e_reviewer_lecturer",
                after_state={"email": email, "role": role},
                reason="Temporary account for Home placeholder E2E verification",
            ))
            session.commit()
            print(f"[CREATED] {role} user '{email}' (ID: {user.id}).")


if __name__ == "__main__":
    main()
