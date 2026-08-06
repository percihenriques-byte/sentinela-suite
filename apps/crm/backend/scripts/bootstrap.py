"""Idempotent bootstrap: create demo user + workspace + seed data.

Safe to re-run — creates only what is missing.
Prints the demo credentials on success.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models import User, Workspace, WorkspaceMember, WorkspaceRole
from app.core.security import hash_password
from app.services import demo_seed


DEMO_EMAIL = "demo@visiquost.app"
DEMO_PASSWORD = "demo1234"
DEMO_FULLNAME = "Demo User"
DEMO_WORKSPACE = "Demo Workspace"


def main() -> int:
    init_db()
    with Session(engine) as s:
        user = s.exec(select(User).where(User.email == DEMO_EMAIL)).first()
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                full_name=DEMO_FULLNAME,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            s.add(user)
            s.flush()
            print(f"[bootstrap] created user {DEMO_EMAIL}")
        else:
            print(f"[bootstrap] user {DEMO_EMAIL} exists")

        ws = s.exec(select(Workspace).where(Workspace.owner_id == user.id)).first()
        if ws is None:
            ws = Workspace(name=DEMO_WORKSPACE, slug="demo", owner_id=user.id)
            s.add(ws)
            s.flush()
            s.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.owner))
            s.commit()
            s.refresh(ws)
            print(f"[bootstrap] created workspace {ws.slug}")
        else:
            print(f"[bootstrap] workspace {ws.slug} exists")

        result = demo_seed.seed_workspace(s, ws.id, user.id)
        print(f"[bootstrap] seed: {result.get('status')}")

    print()
    print("=" * 50)
    print(" LOGIN")
    print("=" * 50)
    print(f" Email:    {DEMO_EMAIL}")
    print(f" Password: {DEMO_PASSWORD}")
    print(f" URL:      http://127.0.0.1:8000/")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
