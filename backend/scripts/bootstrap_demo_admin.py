"""Bootstrap ONE ADMIN account for an isolated LOCAL DEMO database (Task 14).

* Email / password come from environment variables that live in a config file
  OUTSIDE Git (``DEMO_BOOTSTRAP_ADMIN_EMAIL`` / ``DEMO_BOOTSTRAP_ADMIN_PASSWORD``).
  Nothing is hard-coded and the password is never printed or stored in plaintext
  (Argon2id hash only).
* The account is created directly as ``ADMIN`` and active - there is no approval
  step in the data model, so it can sign in immediately.  Normal login, JWT,
  session and role checks are untouched.
* Idempotent: an existing account with the same e-mail is NEVER modified.  If it
  exists but is not a usable ADMIN, the script reports it and exits non-zero.
* A password shorter than the 8-character system policy is accepted ONLY here,
  only with ``--allow-weak-demo-password``, and only when ALL guards hold:
  ``ENVIRONMENT=local``, loopback host, port != 5432, database name contains a
  ``demo``/``test`` segment, ``--expected-database`` equals the configured one,
  and the live server reports the same database/port.  The API's own password
  rules for creating/resetting users are NOT relaxed.

Usage (from ``backend/``; DB_* variables as for the app)::

    python -m scripts.bootstrap_demo_admin --dry-run --expected-database <db> --expected-port <port>
    python -m scripts.bootstrap_demo_admin --apply   --expected-database <db> --expected-port <port> \\
        [--allow-weak-demo-password]

Exit codes: 0 ok, 2 refused by a guard / unsuitable existing account, 5 failure.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.core.display_names import ADMIN_LABEL
from app.core.security import password_hasher
from app.models.governance import AuditEvent, User
from scripts.generate_matching_candidates import (
    EXIT_OK,
    EXIT_PERSIST_FAILED,
    CliRefused,
    make_read_only_engine,
    validate_target_url,
    verify_server_identity,
)

EMAIL_ENV = "DEMO_BOOTSTRAP_ADMIN_EMAIL"
PASSWORD_ENV = "DEMO_BOOTSTRAP_ADMIN_PASSWORD"
SYSTEM_MIN_PASSWORD = 8
_DEMO_DB = re.compile(r"(^|_)(demo|test)(_|$)")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class Plan:
    action: str  # CREATE | EXISTS_OK | UNSUITABLE
    detail: str
    credential_matches: bool | None = None


def validate_guards(
    *,
    environment: str,
    url: URL,
    expected_database: str,
    expected_port: int | None,
    email: str | None,
    password: str | None,
    allow_weak: bool,
) -> None:
    if (environment or "").strip().lower() != "local":
        raise CliRefused("demo bootstrap is allowed only with ENVIRONMENT=local")
    validate_target_url(url, expected_database, expected_port)
    if not _DEMO_DB.search(url.database or ""):
        raise CliRefused("database name must contain a 'demo' or 'test' segment")
    if not email or not _EMAIL.match(email.strip()):
        raise CliRefused(f"{EMAIL_ENV} is missing or not an e-mail address (read it from a config file outside Git)")
    if not password:
        raise CliRefused(f"{PASSWORD_ENV} is missing (read it from a config file outside Git)")
    if len(password) < SYSTEM_MIN_PASSWORD and not allow_weak:
        raise CliRefused(
            f"password is shorter than the {SYSTEM_MIN_PASSWORD}-character system policy; "
            "pass --allow-weak-demo-password to accept it for this isolated demo database only"
        )


ROLES = ("ADMIN", "REVIEWER", "LECTURER")
_DISPLAY = {"ADMIN": ADMIN_LABEL, "REVIEWER": "Người rà soát", "LECTURER": "Giảng viên (tra cứu)"}


def plan_for(session: Session, email: str, password: str, role: str = "ADMIN") -> Plan:
    existing = session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if existing is None:
        return Plan("CREATE", f"no account with this e-mail; will create {role} '{email.strip()}'")
    matches = password_hasher.verify(password, existing.password_hash)
    if existing.role.upper() != role or not existing.is_active or existing.lecturer_id is not None:
        return Plan(
            "UNSUITABLE",
            f"account exists with role={existing.role} active={existing.is_active} "
            f"linked_to_lecturer={existing.lecturer_id is not None}; left untouched, resolve manually",
            matches,
        )
    note = "configured password matches" if matches else "configured password does NOT match the stored credential (not overwritten)"
    return Plan("EXISTS_OK", f"active {role} already exists; {note}", matches)


def create_admin(session: Session, email: str, password: str, role: str = "ADMIN") -> User:
    """Create ONE account (ADMIN by default; REVIEWER / an unlinked read-only LECTURER on request)."""

    user = User(
        id=uuid.uuid4(),
        email=email.strip(),
        password_hash=password_hasher.hash(password),
        display_name=_DISPLAY[role],
        role=role,
        lecturer_id=None,
        is_active=True,
    )
    session.add(user)
    session.flush()
    session.add(
        AuditEvent(
            entity_type="users",
            entity_id=user.id,
            action="DEMO_ADMIN_BOOTSTRAPPED",
            actor_type="SYSTEM",
            actor_user_id=None,
            actor_service="bootstrap_demo_admin",
            after_state={"email": user.email, "role": role, "display_name": _DISPLAY[role]},
            reason=f"Isolated demo {role} created by bootstrap_demo_admin (no approval step; credential from external config)",
        )
    )
    session.commit()
    return user


def other_accounts(session: Session, email: str) -> list[tuple[str, str, bool]]:
    rows = session.execute(
        select(User.email, User.role, User.is_active).where(func.lower(User.email) != email.strip().lower()).order_by(User.email)
    ).all()
    return [(e, r, a) for e, r, a in rows]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.bootstrap_demo_admin")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--expected-database", required=True)
    p.add_argument("--expected-port", type=int, default=None)
    p.add_argument("--allow-weak-demo-password", action="store_true")
    p.add_argument("--role", choices=ROLES, default="ADMIN")
    p.add_argument("--email-env", default=EMAIL_ENV, help="name of the variable holding the e-mail")
    p.add_argument("--password-env", default=PASSWORD_ENV, help="name of the variable holding the password")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from app.core.config import settings

        url = URL.create("postgresql+psycopg2", username=settings.db_user, password=settings.db_password,
                         host=settings.db_host, port=settings.db_port, database=settings.db_name)
        email, password = os.environ.get(args.email_env), os.environ.get(args.password_env)
        validate_guards(
            environment=settings.environment, url=url, expected_database=args.expected_database,
            expected_port=args.expected_port, email=email, password=password, allow_weak=args.allow_weak_demo_password,
        )
        reader = make_read_only_engine(url)
        ident = verify_server_identity(reader, args.expected_database, args.expected_port)
        print(f"target: database={ident['database']} port={ident['port']} addr={ident['address']}")
        with Session(reader) as session:
            plan = plan_for(session, email, password, args.role)
            others = other_accounts(session, email)
            session.rollback()
        report: dict[str, Any] = {"mode": "dry-run" if args.dry_run else "apply", "email": email.strip(), "role": args.role, "plan": plan.action,
                                  "detail": plan.detail, "other_accounts_untouched": [f"{e} ({r})" for e, r, _ in others]}
        if plan.action == "UNSUITABLE":
            print(report)
            print("REFUSED: existing account is not a usable ADMIN; nothing was changed", file=sys.stderr)
            return 2
        if args.apply and plan.action == "CREATE":
            from sqlalchemy import create_engine

            writer = create_engine(url, pool_pre_ping=True)
            try:
                verify_server_identity(writer, args.expected_database, args.expected_port)
                with Session(writer) as session:  # fresh session, no prior statements
                    user = create_admin(session, email, password, args.role)
                    report["created_user_id"] = str(user.id)
            finally:
                writer.dispose()
        print(report)
        return EXIT_OK
    except CliRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}", file=sys.stderr)
        return EXIT_PERSIST_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
