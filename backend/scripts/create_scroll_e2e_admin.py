"""One-off: create a dedicated ADMIN test account for the scroll-position
regression E2E session, on the test DB only (scopus_ictu_test_withjson_r2_20261011).

Idempotent: does nothing if the account already exists. Never touches any
other user. Not wired into any app startup path; run manually and delete
when the E2E session is done if desired.
"""

from __future__ import annotations

import os
import uuid

from sqlalchemy import func

from app.core.database import get_session_factory
from app.core.security import password_hasher
from app.models.governance import AuditEvent, User

EMAIL = "scroll.e2e.admin@ictu.edu.vn"
PASSWORD = os.environ["SCROLL_E2E_ADMIN_PASSWORD"]


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        existing = (
            session.query(User)
            .filter(func.lower(User.email) == EMAIL.lower())
            .first()
        )
        if existing is not None:
            print(f"[OK] Account '{EMAIL}' already exists (ID: {existing.id}). Nothing to do.")
            return

        user = User(
            id=uuid.uuid4(),
            email=EMAIL,
            password_hash=password_hasher.hash(PASSWORD),
            display_name="Scroll E2E Admin",
            role="ADMIN",
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
            actor_service="create_scroll_e2e_admin",
            after_state={"email": EMAIL, "role": "ADMIN"},
            reason="Temporary account for route scroll-position regression E2E",
        ))
        session.commit()
        print(f"[CREATED] Admin user '{EMAIL}' (ID: {user.id}).")


if __name__ == "__main__":
    main()
