"""Periodic on-disk backups of every workspace.

Enabled only when `JARVIS_BACKUP_DIR` is set. Runs as an asyncio background
task started from the FastAPI lifespan hook. Each cycle writes one JSON file
per workspace, timestamped, into the configured directory.

Deliberately best-effort: exceptions are logged and swallowed so a broken
backup never crashes the API.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import engine
from app.models import Workspace
from app.services.workspace_io import export_workspace


logger = logging.getLogger("jarvis.backup")


async def run_backup_scheduler(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    if not settings.jarvis_backup_dir:
        return
    dest = Path(settings.jarvis_backup_dir)
    dest.mkdir(parents=True, exist_ok=True)
    interval = max(1, int(settings.backup_interval_minutes)) * 60
    logger.info("backup_scheduler started dir=%s interval_s=%d", dest, interval)
    while not stop_event.is_set():
        try:
            _snapshot_all_workspaces(dest)
        except Exception:
            logger.exception("backup_cycle_failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


def _snapshot_all_workspaces(dest: Path) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with Session(engine) as session:
        workspaces = session.exec(select(Workspace).where(Workspace.deleted_at.is_(None))).all()
        for ws in workspaces:
            envelope = export_workspace(session, ws.id)
            path = dest / f"{ws.slug}-{stamp}.json"
            path.write_text(json.dumps(envelope, default=str), encoding="utf-8")
            logger.info("backup_written workspace=%s file=%s", ws.slug, path.name)
