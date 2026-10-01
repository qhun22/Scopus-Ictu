"""Seed demo user accounts — M2.2 idempotent script.

Creates the 2 required demo accounts:
1. admin@gmail.com (ADMIN, display_name="Quản trị viên")
2. user@gmail.com  (LECTURER, display_name="Người dùng")

Passwords are read securely from environment variables:
- DEMO_ADMIN_PASSWORD
- DEMO_USER_PASSWORD

Usage:
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
from app.models.governance import User
from app.models.master_lecturer import Lecturer


def seed_demo_users(session: Session) -> None:
    """Idempotently seed the required demo users."""
    admin_password = os.environ.get("DEMO_ADMIN_PASSWORD")
    user_password = os.environ.get("DEMO_USER_PASSWORD")

    if not admin_password or not user_password:
        print(
            "ERROR: Missing environment variables for demo passwords.\n"
            "Please set DEMO_ADMIN_PASSWORD and DEMO_USER_PASSWORD.\n"
            "Example: DEMO_ADMIN_PASSWORD=Secret123 DEMO_USER_PASSWORD=Secret123 python -m scripts.seed_demo_users",
            file=sys.stderr,
        )
        sys.exit(1)

    # 1. Admin Account (ADMIN)
    admin_email = "admin@gmail.com"
    existing_admin = (
        session.query(User)
        .filter(func.lower(User.email) == admin_email.lower())
        .first()
    )
    if existing_admin:
        print(f"[EXISTS]  Admin user '{admin_email}' already exists (ID: {existing_admin.id}).")
    else:
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
        print(f"[CREATED] Admin user '{admin_email}' successfully created (ID: {admin_user.id}).")

    # 2. Lecturer Account (LECTURER)
    lecturer_email = "user@gmail.com"
    existing_user = (
        session.query(User)
        .filter(func.lower(User.email) == lecturer_email.lower())
        .first()
    )
    if existing_user:
        print(f"[EXISTS]  Lecturer user '{lecturer_email}' already exists (ID: {existing_user.id}).")
    else:
        # Ensure a canonical Lecturer profile exists to satisfy FK constraint
        lecturer_profile = (
            session.query(Lecturer)
            .filter(func.lower(Lecturer.email) == lecturer_email.lower())
            .first()
        )
        if not lecturer_profile:
            lecturer_profile = Lecturer(
                id=uuid.uuid4(),
                full_name="Người dùng",
                full_name_normalized="NGUOI DUNG",
                email=lecturer_email,
                department="Khoa CNTT",
                faculty="Công nghệ Thông tin",
            )
            session.add(lecturer_profile)
            session.flush()
            print(f"[CREATED] Linked Lecturer master record '{lecturer_email}' (ID: {lecturer_profile.id}).")

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
        print(f"[CREATED] Lecturer user '{lecturer_email}' successfully created (ID: {lecturer_user.id}).")

    session.commit()
    print("Demo user seeding completed successfully.")


def main() -> None:
    factory = get_session_factory()
    with factory() as session:
        seed_demo_users(session)


if __name__ == "__main__":
    main()
