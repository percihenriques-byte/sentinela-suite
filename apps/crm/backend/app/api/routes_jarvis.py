"""Jarvis assistant endpoints.

Design constraint (durable): Jarvis is **local-only, no external APIs**.
The local engine (`LocalJarvis`) is the sole path — no cloud LLM, no OAuth.
"""
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.jarvis.context import build_workspace_context
from app.jarvis.local_engine import LocalJarvis
from app.models import JarvisConversation, JarvisMessage
from app.schemas.common import Page
from app.schemas.jarvis import (
    JarvisChatRequest,
    JarvisChatResponse,
    JarvisContextSnapshot,
    JarvisConversationRead,
    JarvisMessageRead,
)
from app.services import crud, jarvis_service

router = APIRouter(prefix="/jarvis", tags=["jarvis"])
_local = LocalJarvis()


def _sanitize_history(messages: list[dict]) -> list[dict]:
    """Enforce strict user/assistant alternation ending with an assistant turn.

    Anthropic's messages API rejects payloads where two consecutive turns
    share the same role, and requires the first turn to be `user`. When we
    filter out fallback assistant messages (which never went through the
    LLM), the messages we keep can leave a user turn dangling with no
    matching assistant — or two user turns in a row. This drops each
    orphaned turn so the runner can append the fresh user message cleanly.
    """
    cleaned: list[dict] = []
    expected = "user"
    for msg in messages:
        role = msg.get("role")
        if role != expected:
            continue
        cleaned.append(msg)
        expected = "assistant" if expected == "user" else "user"
    # If the last entry is a user turn (no assistant paired to it), drop it —
    # the runner will append the current user message and we can't have two
    # user turns adjacent.
    if cleaned and cleaned[-1]["role"] == "user":
        cleaned.pop()
    return cleaned


@router.post("/auto-import-contacts")
def auto_import_contacts_endpoint(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
    confirm: Annotated[bool, Query()] = False,
) -> dict:
    from app.jarvis.tools import default_registry, ToolContext
    ctx = ToolContext(session=session, workspace_id=ws.id, user_id=user.id)
    return default_registry().call("auto_import_contacts", ctx, {"confirm": confirm})


@router.get("/read-file")
def read_local_file_endpoint(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
    filename: Annotated[str, Query(min_length=1, max_length=500)],
) -> dict:
    """HTTP entry to read_local_file — powers the frontend file viewer."""
    from app.jarvis.tools import default_registry, ToolContext
    ctx = ToolContext(session=session, workspace_id=ws.id, user_id=user.id)
    return default_registry().call("read_local_file", ctx, {"filename": filename})


@router.get("/scan-work-dir")
def scan_work_dir_endpoint(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> dict:
    from app.jarvis.tools import default_registry, ToolContext
    ctx = ToolContext(session=session, workspace_id=ws.id, user_id=user.id)
    return default_registry().call("scan_work_dir", ctx, {})


@router.get("/monthly-forecast")
def monthly_forecast(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
    months: Annotated[int, Query(ge=1, le=12)] = 6,
) -> dict:
    """Weighted pipeline per month for the next N months, grouped by expected_close_date."""
    from datetime import datetime, timezone
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    now = datetime.now(timezone.utc)
    opps = list(session.exec(select(Opportunity).where(
        Opportunity.workspace_id == ws.id,
        Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
        Opportunity.expected_close_date.is_not(None),
    )).all())
    buckets = {}
    for i in range(months):
        year = now.year + (now.month - 1 + i) // 12
        month = (now.month - 1 + i) % 12 + 1
        key = f"{year:04d}-{month:02d}"
        buckets[key] = {"month": key, "count": 0, "weighted": 0.0, "total": 0.0}
    end_year = now.year + (now.month - 1 + months - 1) // 12
    end_month = (now.month - 1 + months - 1) % 12 + 1
    for o in opps:
        d = o.expected_close_date
        if not d:
            continue
        if d.year < now.year or (d.year == now.year and d.month < now.month):
            continue
        if d.year > end_year or (d.year == end_year and d.month > end_month):
            continue
        key = f"{d.year:04d}-{d.month:02d}"
        b = buckets.get(key)
        if not b:
            continue
        b["count"] += 1
        b["total"] += o.amount or 0
        b["weighted"] += (o.amount or 0) * (o.probability or 0) / 100.0
    return {"months": months, "buckets": list(buckets.values())}


@router.get("/wins-losses-trend")
def wins_losses_trend(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
    days: Annotated[int, Query(ge=7, le=180)] = 30,
) -> dict:
    """Daily counts of won vs lost opportunities over the last N days."""
    from datetime import datetime, timedelta, timezone
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    rows = list(session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ws.id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status.in_([OpportunityStatus.won, OpportunityStatus.lost]),
            Opportunity.closed_at.is_not(None),
        )
    ).all())
    by_day: dict[str, dict[str, float]] = {}
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).date().isoformat()
        by_day[d] = {"won": 0, "lost": 0, "won_amt": 0.0, "lost_amt": 0.0}
    for o in rows:
        if not o.closed_at:
            continue
        closed = o.closed_at if o.closed_at.tzinfo else o.closed_at.replace(tzinfo=timezone.utc)
        if closed < since:
            continue
        key = closed.date().isoformat()
        if key not in by_day:
            continue
        if o.status == OpportunityStatus.won:
            by_day[key]["won"] += 1
            by_day[key]["won_amt"] += o.amount or 0
        else:
            by_day[key]["lost"] += 1
            by_day[key]["lost_amt"] += o.amount or 0
    series = [{"date": d, **counts} for d, counts in by_day.items()]
    totals = {
        "won": sum(x["won"] for x in series),
        "lost": sum(x["lost"] for x in series),
        "won_amt": sum(x["won_amt"] for x in series),
        "lost_amt": sum(x["lost_amt"] for x in series),
    }
    return {"days": days, "series": series, "totals": totals}


@router.get("/workspace-summary.md")
def workspace_summary_markdown(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
):
    """Human-readable Markdown snapshot of the workspace — good for email/print."""
    from fastapi.responses import PlainTextResponse
    from datetime import datetime
    from app.jarvis.context import build_workspace_context
    snap = build_workspace_context(session, ws.id, user.id)
    lines = [
        f"# {ws.workspace.name} — Snapshot",
        f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "## Contadores",
        f"- Contatos: **{snap.counts.get('contacts', 0)}**",
        f"- Empresas: **{snap.counts.get('companies', 0)}**",
        f"- Leads: **{snap.counts.get('leads', 0)}**",
        f"- Oportunidades: **{snap.counts.get('opportunities', 0)}**",
        f"- Tarefas abertas: **{snap.counts.get('tasks_open', 0)}**",
        "",
    ]
    if snap.overdue_tasks:
        lines.append("## ⏰ Tarefas atrasadas")
        for t in snap.overdue_tasks[:10]:
            due = (t.get("due_at") or "")[:16] if isinstance(t, dict) else ""
            title = t.get("title") if isinstance(t, dict) else getattr(t, "title", "?")
            lines.append(f"- **{title}**{' — ' + due if due else ''}")
        lines.append("")
    if snap.upcoming_meetings:
        lines.append("## 📅 Próximas reuniões")
        for m in snap.upcoming_meetings[:10]:
            starts = (m.get("starts_at") or "")[:16] if isinstance(m, dict) else ""
            title = m.get("title") if isinstance(m, dict) else getattr(m, "title", "?")
            lines.append(f"- **{title}** — {starts}")
        lines.append("")
    if snap.open_opportunities:
        lines.append("## 💰 Oportunidades abertas")
        for o in snap.open_opportunities[:15]:
            if isinstance(o, dict):
                name = o.get("name", "?")
                amt = f"{o.get('currency', 'USD')} {o.get('amount', 0):,.0f}"
            else:
                name = getattr(o, "name", "?")
                amt = f"{o.currency} {o.amount:,.0f}"
            lines.append(f"- **{name}** — {amt}")
        lines.append("")
    body = "\n".join(lines)
    return PlainTextResponse(
        body, media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=visiquost-summary-{ws.workspace.slug}.md"},
    )


@router.get("/local-footprint")
def local_footprint(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> dict:
    """Physical size of the local DB + total row counts across main entities.
    Powers the 'on-device footprint' widget — the app's signature reminder
    that this CRM lives on your machine, not the cloud."""
    from pathlib import Path
    from sqlmodel import select, func
    from app.models import Contact, Company, Opportunity, Lead, Task, Note, Meeting
    from app.jarvis.device_tools import _get_work_dir
    # DB file size — derive from settings.database_url, fall back to common names.
    from app.core.config import get_settings
    settings = get_settings()
    db_bytes = 0
    candidates = []
    if settings.database_url and settings.database_url.startswith("sqlite"):
        # e.g. "sqlite:///./jarvis_crm.db" → "./jarvis_crm.db"
        candidates.append(settings.database_url.split("sqlite:///", 1)[-1])
    candidates.extend(["jarvis_crm.db", "db.sqlite", "backend/jarvis_crm.db"])
    for candidate in candidates:
        p = Path(candidate)
        if p.exists():
            db_bytes = p.stat().st_size
            break
    # Total records across main entities (workspace-scoped, non-deleted)
    row_counts = {}
    for model, key in [
        (Contact, "contacts"), (Company, "companies"), (Opportunity, "opportunities"),
        (Lead, "leads"), (Task, "tasks"), (Note, "notes"), (Meeting, "meetings"),
    ]:
        row_counts[key] = session.exec(
            select(func.count()).select_from(model).where(
                model.workspace_id == ws.id, model.deleted_at.is_(None),
            )
        ).one()
    total_rows = sum(row_counts.values())
    # Work dir file count (imports, exports the user dropped)
    wd = _get_work_dir()
    workdir_files = 0
    if wd and wd.exists():
        try:
            workdir_files = sum(1 for _ in wd.iterdir())
        except OSError:
            pass
    return {
        "db_bytes": db_bytes,
        "total_rows": total_rows,
        "row_counts": row_counts,
        "workdir_files": workdir_files,
        "workdir": str(wd) if wd else None,
    }


@router.get("/device-status")
def device_status(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> dict:
    """What device-level (local) capabilities Jarvis has right now."""
    from app.jarvis.device_tools import _get_work_dir
    workdir = _get_work_dir()
    workdir_str = str(workdir) if workdir else None
    ics_count = len(list(workdir.glob("*.ics"))) if workdir else 0
    csv_count = len(list(workdir.glob("*.csv"))) + len(list(workdir.glob("*.vcf"))) if workdir else 0
    return {
        "tools": [
            {"name": "read_calendar", "label": "Ler agenda (arquivos .ics locais)",
             "status": "ready" if ics_count > 0 else "no_files",
             "note": f"{ics_count} arquivo(s) .ics em {workdir_str}" if ics_count > 0
                     else f"Salve .ics em {workdir_str or '~/Documents/VisiQuost'}"},
            {"name": "auto_import_contacts", "label": "Importar contatos de arquivos locais",
             "status": "ready" if csv_count > 0 else "no_files",
             "note": f"{csv_count} arquivo(s) .csv/.vcf em {workdir_str}" if csv_count > 0
                     else f"Salve .csv ou .vcf em {workdir_str or '~/Documents/VisiQuost'}"},
            {"name": "list_files", "label": "Ler arquivos locais",
             "status": "ready" if workdir_str else "not_configured",
             "note": f"Diretório: {workdir_str}" if workdir_str else "Auto: ~/Documents/VisiQuost"},
            {"name": "generate_marketing_copy", "label": "Gerar copy de marketing (offline, template)",
             "status": "ready", "note": "Sem API — templates locais"},
        ],
        "workdir": workdir_str,
        "local_ics_count": ics_count,
        "local_contact_files": csv_count,
    }


@router.get("/search-everywhere")
def jarvis_search_everywhere(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=25)] = 6,
) -> dict:
    """Direct HTTP entry to the search_everywhere tool — powers cmd-K palette.

    Avoids the intent classifier round-trip for pure lookups.
    """
    from app.jarvis.tools import _search_everywhere, ToolContext
    ctx = ToolContext(session=session, workspace_id=ws.id, user_id=user.id)
    result = _search_everywhere(ctx, {"query": q, "limit_per_kind": limit})
    grouped = result.get("results", {})
    return {
        "contacts": [{"id": c["id"], "first_name": c["name"].split(" ", 1)[0], "last_name": (c["name"].split(" ", 1)[1] if " " in c["name"] else ""), "email": c.get("email")} for c in grouped.get("contacts", [])],
        "companies": [{"id": c["id"], "name": c["name"], "domain": c.get("domain")} for c in grouped.get("companies", [])],
        "opportunities": [{"id": o["id"], "name": o["name"], "amount": o.get("amount"), "currency": o.get("currency", "USD")} for o in grouped.get("opportunities", [])],
        "leads": [{"id": l["id"], "first_name": l["name"].split(" ", 1)[0], "last_name": (l["name"].split(" ", 1)[1] if " " in l["name"] else ""), "company_name": l.get("company_name")} for l in grouped.get("leads", [])],
        "total": result.get("total", 0),
    }


@router.get("/context", response_model=JarvisContextSnapshot)
def jarvis_context(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> JarvisContextSnapshot:
    snap = build_workspace_context(session, ws.id, user.id)
    return JarvisContextSnapshot(
        counts=snap.counts,
        overdue_task_count=len(snap.overdue_tasks),
        upcoming_meeting_count=len(snap.upcoming_meetings),
        open_opportunity_count=len(snap.open_opportunities),
        # Expose the open-opps list so the frontend can compute the hero KPI
        # (pipeline value) client-side without a second round trip.
        open_opportunities=snap.open_opportunities,
        preferences=snap.preferences,
        generated_at=snap.generated_at.isoformat(),
        nudges=snap.nudges,
    )


@router.post("/chat", response_model=JarvisChatResponse)
def jarvis_chat(
    req: JarvisChatRequest,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> JarvisChatResponse:
    conv = jarvis_service.get_or_create_conversation(
        session, ws.id, user.id, req.conversation_id, title_seed=req.message
    )
    jarvis_service.append_message(session, ws.id, conv, role="user", content=req.message)

    # 0) Agent planner — if the message decomposes into multiple steps
    # (connectors like "e depois", "and then", numbered list), run each
    # step through the local engine and return a Manus-style checklist.
    from app.jarvis.planner import AgentPlanner, is_multi_step
    if is_multi_step(req.message):
        planner = AgentPlanner(_local)
        plan = planner.run(session=session, workspace_id=ws.id, user_id=user.id, text=req.message)
        tool_calls = []
        for step in plan.steps:
            for tc in step.tool_calls:
                tool_calls.append({**tc, "step_index": step.index, "step_intent": step.intent})
        jarvis_service.append_message(
            session, ws.id, conv,
            role="assistant", content=plan.combined_reply,
            intent="agent_plan", tool_calls=tool_calls,
        )
        return JarvisChatResponse(
            reply=plan.combined_reply,
            conversation_id=conv.id,
            intent="agent_plan",
            tool_calls=tool_calls,
        )

    # 1) Local-first — no network calls, deterministic, always available.
    # Build a lightweight conversational context from the last few turns so
    # the engine can resume ambiguity picks ("1", "the second one", etc.).
    conv_ctx = None
    try:
        import json as _json
        # Robust: directly query the most recent assistant message with
        # tool_calls_json — impervious to created_at ties in fast tests.
        last_tools_msg = jarvis_service.get_last_assistant_with_tool_calls(
            session, ws.id, conv.id,
        )
        last_assistant_tools = None
        if last_tools_msg and last_tools_msg.tool_calls_json:
            try:
                last_assistant_tools = _json.loads(last_tools_msg.tool_calls_json)
            except Exception:
                last_assistant_tools = None
        last_intent = jarvis_service.get_last_assistant_intent(
            session, ws.id, conv.id,
        )
        conv_ctx = {
            "last_tool_calls": last_assistant_tools or [],
            "last_intent": last_intent,
        }
    except Exception:
        conv_ctx = None

    local = _local.handle(
        session=session,
        workspace_id=ws.id,
        user_id=user.id,
        message=req.message,
        conversation_context=conv_ctx,
    )
    # Local always answers — no cloud/API escalation.
    jarvis_service.append_message(
        session, ws.id, conv,
        role="assistant", content=local.reply,
        intent=local.intent or "unknown", tool_calls=local.tool_calls,
        fallback=not local.handled,
    )
    return JarvisChatResponse(
        reply=local.reply,
        conversation_id=conv.id,
        intent=local.intent,
        tool_calls=local.tool_calls,
        fallback=not local.handled,
    )


@router.get("/conversations", response_model=Page[JarvisConversationRead])
def list_conversations(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[JarvisConversationRead]:
    base = crud.scoped_query(JarvisConversation, ws.id).where(JarvisConversation.user_id == user.id)
    total = crud.count_from(session, base)
    rows = session.exec(
        base.order_by(JarvisConversation.last_message_at.desc().nulls_last(), JarvisConversation.created_at.desc())
        .limit(limit).offset(offset)
    ).all()
    return Page[JarvisConversationRead].build(
        [JarvisConversationRead.model_validate(r) for r in rows], total, limit, offset
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[JarvisMessageRead])
def list_conversation_messages(
    conversation_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> list[JarvisMessageRead]:
    conv = crud.get_or_404(session, JarvisConversation, ws.id, conversation_id)
    if conv.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your conversation")
    messages = jarvis_service.get_history(session, ws.id, conv.id, limit=200)
    return [JarvisMessageRead.model_validate(m) for m in messages]


@router.get("/conversations/{conversation_id}/export.md")
def export_conversation_markdown(
    conversation_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
):
    """Export a single conversation as human-readable markdown."""
    from fastapi.responses import PlainTextResponse
    conv = crud.get_or_404(session, JarvisConversation, ws.id, conversation_id)
    if conv.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your conversation")
    messages = jarvis_service.get_history(session, ws.id, conv.id, limit=1000)
    lines = [
        f"# {conv.title or 'Sem título'}",
        f"_Exportado em {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
    ]
    for m in messages:
        role_label = {"user": "🧑 Você", "assistant": "✨ Jarvis"}.get(m.role, m.role)
        lines.append(f"## {role_label}")
        lines.append(m.content or "")
        lines.append("")
    body = "\n".join(lines)
    return PlainTextResponse(
        body, media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=jarvis-{conv.id}.md"},
    )


@router.get("/messages/search")
def search_messages(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict:
    """Full-text search across the user's own conversation messages."""
    from sqlmodel import select
    from app.services.crud import like_escape
    like = f"%{like_escape(q)}%"
    stmt = (
        select(JarvisMessage, JarvisConversation)
        .join(JarvisConversation, JarvisConversation.id == JarvisMessage.conversation_id)
        .where(
            JarvisConversation.workspace_id == ws.id,
            JarvisConversation.user_id == user.id,
            JarvisConversation.deleted_at.is_(None),
            JarvisMessage.content.ilike(like, escape="\\"),
        )
        .order_by(JarvisMessage.created_at.desc())
        .limit(limit)
    )
    hits = []
    for m, conv in session.exec(stmt).all():
        # Highlight snippet
        idx = m.content.lower().find(q.lower())
        snippet_start = max(0, idx - 40)
        snippet_end = min(len(m.content), idx + len(q) + 60)
        snippet = ("…" if snippet_start > 0 else "") + m.content[snippet_start:snippet_end] + ("…" if snippet_end < len(m.content) else "")
        hits.append({
            "conversation_id": str(conv.id),
            "conversation_title": conv.title or "Sem título",
            "role": m.role,
            "snippet": snippet,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return {"query": q, "count": len(hits), "hits": hits}


class ConversationRenameRequest(__import__("pydantic").BaseModel):
    title: str = __import__("pydantic").Field(min_length=1, max_length=200)


@router.patch("/conversations/{conversation_id}", response_model=JarvisConversationRead)
def rename_conversation(
    conversation_id: UUID,
    payload: ConversationRenameRequest,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> JarvisConversationRead:
    conv = crud.get_or_404(session, JarvisConversation, ws.id, conversation_id)
    if conv.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your conversation")
    conv.title = payload.title.strip()
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return JarvisConversationRead.model_validate(conv)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
) -> None:
    conv = crud.get_or_404(session, JarvisConversation, ws.id, conversation_id)
    if conv.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your conversation")
    crud.soft_delete(session, conv)
