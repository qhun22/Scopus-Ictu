"""Seed demo user accounts — M2.2 idempotent script (safe version).

Creates demo accounts only when they do not exist:
1. admin@gmail.com (ADMIN, display_name="Quản trị viên")
2. user@gmail.com  (LECTURER, display_name="Người dùng")

Passwords are read securely from environment variables:
- DEMO_ADMIN_PASSWORD  — required ONLY if admin account needs creation
- DEMO_USER_PASSWORD   — required ONLY if lecturer account needs creation

An existing account is NEVER silently re-passworded.

Usage:
    # Seed only missing accounts (safe — never overwrites existing passwords):
    DEMO_USER_PASSWORD=your_user_pwd python -m scripts.seed_demo_users
    # If admin needs creating too:
    DEMO_ADMIN_PASSWORD=your_admin_pwd DEMO_USER_PASSWORD=your_user_pwd python -m scripts.seed_demo_users
"""

from __future__ import annotations

import os
import sys
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.core.security import password_hasher
from app.models.governance import AuditEvent, User
from app.models.master_lecturer import Lecturer


def _prompt_password(prompt: str) -> str:
    """Non-echoing password input. Falls back to echo if terminal does not support."""
    try:
        import getpass
        return getpass.getpass(prompt)
    except Exception:
        return input(prompt)


def _require_password(env_var: str, account_label: str) -> str:
    """Read password from env var; fail with clear message if missing."""
    pwd = os.environ.get(env_var)
    if not pwd:
        print(
            f"ERROR: {env_var} is required to create the missing {account_label} account.\n"
            f"HINT:  Set it before running this script, e.g.:\n"
            f"       {env_var}=your_password python -m scripts.seed_demo_users",
            file=sys.stderr,
        )
        sys.exit(1)
    return pwd


def seed_demo_users(session: Session) -> None:
    """Idempotently seed the required demo accounts.

    Only creates accounts that are absent.
    Only requires password env vars for accounts that will actually be created.
    Never modifies existing accounts or their passwords.
    """

    # ── Pass 1: discover what needs to be created ─────────────────────────────
    admin_email = "admin@gmail.com"
    lecturer_email = "user@gmail.com"

    existing_admin = (
        session.query(User)
        .filter(func.lower(User.email) == admin_email.lower())
        .first()
    )
    existing_user = (
        session.query(User)
        .filter(func.lower(User.email) == lecturer_email.lower())
        .first()
    )

    admin_missing = existing_admin is None
    user_missing = existing_user is None

    if not admin_missing and not user_missing:
        print(f"[OK]     Both demo accounts already exist. Nothing to do.")
        return

    # ── Pass 2: collect only the passwords we actually need ────────────────────
    admin_password: str | None = None
    user_password: str | None = None

    if admin_missing:
        admin_password = _require_password("DEMO_ADMIN_PASSWORD", "admin")
        print(f"[INFO]   Admin account missing — will create.")

    if user_missing:
        user_password = _require_password("DEMO_USER_PASSWORD", "lecturer")
        print(f"[INFO]   Lecturer account missing — will create.")

    # ── Pass 3: create accounts atomically ───────────────────────────────────
    now_factory = lambda: uuid.uuid4()

    if admin_missing:
        admin_user = User(
            id=uuid.uuid4(),
            email=admin_email,
            password_hash=password_hasher.hash(admin_password),
            display_name="Quản trị viên",
            role="ADMIN",
            lecturer_id=None,
            is_active=True,
        )
        session.add(admin_user)
        session.flush()
        session.add(AuditEvent(
            entity_type="users",
            entity_id=admin_user.id,
            action="DEMO_ACCOUNT_SEEDED",
            actor_type="SYSTEM",
            actor_user_id=None,
            actor_service="seed_demo_users",
            after_state={
                "email": admin_email,
                "role": "ADMIN",
                "display_name": "Quản trị viên",
            },
            reason="Demo account bootstrap via seed_demo_users script",
        ))
        print(f"[CREATED] Admin user '{admin_email}' (ID: {admin_user.id}).")

    if user_missing:
        # Link to an existing ICTU Lecturer record that matches user@gmail.com,
        # or create a synthetic demo Lecturer if no match exists.
        lecturer_profile = (
            session.query(Lecturer)
            .filter(func.lower(Lecturer.email) == lecturer_email.lower())
            .first()
        )
        if not lecturer_profile:
            lecturer_profile = Lecturer(
                id=uuid.uuid4(),
                full_name="Người dùng",
                full_name_normalized="nguoi dung",
                email=lecturer_email,
                department="Khoa CNTT",
                faculty="Công nghệ Thông tin",
            )
            session.add(lecturer_profile)
            session.flush()
            session.add(AuditEvent(
                entity_type="lecturer",
                entity_id=lecturer_profile.id,
                action="DEMO_LECTURER_SEEDED",
                actor_type="SYSTEM",
                actor_user_id=None,
                actor_service="seed_demo_users",
                after_state={
                    "email": lecturer_email,
                    "display_name": "Người dùng",
                },
                reason="Synthetic demo lecturer for user@gmail.com account",
            ))
            print(f"[CREATED] Demo Lecturer '{lecturer_email}' (ID: {lecturer_profile.id}).")
        else:
            print(f"[INFO]    Lecturer profile '{lecturer_email}' already exists (ID: {lecturer_profile.id}).")

        lecturer_user = User(
            id=uuid.uuid4(),
            email=lecturer_email,
            password_hash=password_hasher.hash(user_password),
            display_name="Người dùng",
            role="LECTURER",
            lecturer_id=lecturer_profile.id,
            is_active=True,
        )
        session.add(lecturer_user)
        session.flush()
        session.add(AuditEvent(
            entity_type="users",
            entity_id=lecturer_user.id,
            action="DEMO_ACCOUNT_SEEDED",
            actor_type="SYSTEM",
            actor_user_id=None,
            actor_service="seed_demo_users",
            after_state={
                "email": lecturer_email,
                "role": "LECTURER",
                "lecturer_id": str(lecturer_profile.id),
                "display_name": "Người dùng",
            },
            reason="Demo account bootstrap via seed_demo_users script",
        ))
        print(f"[CREATED] Lecturer user '{lecturer_email}' (ID: {lecturer_user.id}).")

    session.commit()
    print("Demo user seeding completed successfully.")


def main() -> None:
    factory = get_session_factory()
    with factory() as session:
        seed_demo_users(session)


if __name__ == "__main__":
    main()
