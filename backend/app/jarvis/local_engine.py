"""Local Jarvis engine — deterministic, offline, zero external APIs.

This is the primary path for `/jarvis/chat`. It:

  * classifies the user's intent by keyword + regex patterns,
  * routes to a handler that reads from the workspace snapshot or invokes
    an existing CRM tool,
  * returns a natural-language reply built from real data.

When no intent matches, the engine returns a fallback reply with suggestions.
There is no cloud LLM escalation — Jarvis runs entirely on the user's machine.

Design principles:
  * Every capability has a local path. No external HTTP calls allowed.
  * Handlers must be workspace-scoped through ToolContext — no leakage.
  * Reply text is short, actionable, and mirrors the language of the request
    (pt-BR / en). Language detection is heuristic.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

from sqlmodel import Session

from app.jarvis.context import WorkspaceSnapshot, build_workspace_context
from app.jarvis.date_parser import parse_when
from app.jarvis.tools import ToolContext, ToolRegistry, default_registry


def _normalize(text: str) -> str:
    """Cheap accent stripper + lowercase to make patterns tolerant of typos and
    Portuguese diacritics. Keeps it fast — no external nlp deps."""
    if not text:
        return ""
    lowered = text.lower()
    replacements = {
        "á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "í": "i", "ì": "i", "î": "i", "ï": "i",
        "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ö": "o",
        "ú": "u", "ù": "u", "û": "u", "ü": "u",
        "ç": "c", "ñ": "n",
    }
    return "".join(replacements.get(ch, ch) for ch in lowered)


def _fuzzy_contains(text: str, needles: list[str], cutoff: float = 0.82) -> bool:
    """Return True if any token in `text` is close to any `needle`.

    Used to tolerate small typos like "opportunites" or "reunioe" without giving
    up the deterministic feel of pattern matching.
    """
    tokens = re.findall(r"[a-z0-9]+", _normalize(text))
    for needle in needles:
        n = _normalize(needle)
        if n in _normalize(text):
            return True
        matches = difflib.get_close_matches(n, tokens, n=1, cutoff=cutoff)
        if matches:
            return True
    return False


PT_HINTS = {
    "quantos", "quantas", "abrir", "criar", "crie", "listar", "mostrar", "resumo",
    "pipeline", "oportunidade", "oportunidades", "contato", "contatos",
    "empresa", "empresas", "tarefa", "tarefas", "reunião", "reunioes",
    "reuniões", "vencidas", "atrasadas", "próximas", "proximas", "ajuda",
    "olá", "ola", "bom dia", "boa tarde", "boa noite",
    "minha", "meu", "meus", "minhas", "semana", "planeje", "hoje", "amanhã", "amanha",
    "feche", "marque", "apague", "delete", "enriqueça",
    "obrigado", "obrigada", "tchau", "leads", "lead",
    "agende", "poste", "escreva", "gere",
    "arquivos", "arquivo", "pasta", "onde", "quais", "que",
    # New: personal pronouns + copular verbs that appear in common PT queries
    "você", "voce", "vc", "quem", "sou", "estou", "está", "esta", "estão", "estao",
    "seu", "sua", "seus", "suas", "nome", "chama", "chamas",
    "pra", "para", "pro", "ligar", "ligue", "devo", "faço", "faz",
    "eu", "nós", "nos", "isso", "isto", "essa", "esse", "esta",
    "sim", "não", "nao", "com", "sem", "muito", "pouco",
}

EN_HINTS = {
    "how", "many", "list", "show", "create", "summarize", "summary",
    "pipeline", "opportunity", "opportunities", "contact", "contacts",
    "company", "companies", "task", "tasks", "meeting", "meetings",
    "overdue", "upcoming", "help", "hello", "hi",
}


def _detect_lang(text: str) -> str:
    tokens = set(re.findall(r"[\wÀ-ÿ]+", text.lower()))
    pt = len(tokens & PT_HINTS)
    en = len(tokens & EN_HINTS)
    if pt > en:
        return "pt"
    if en > 0:
        return "en"
    return "en"


@dataclass
class IntentResult:
    reply: str = ""
    handled: bool = False
    needs_llm: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    intent: str = "unknown"

    @classmethod
    def ok(cls, reply: str, *, intent: str, tool_calls: list[dict[str, Any]] | None = None, confidence: float = 0.9) -> "IntentResult":
        return cls(reply=reply, handled=True, intent=intent, tool_calls=tool_calls or [], confidence=confidence)

    @classmethod
    def escalate(cls, hint: str) -> "IntentResult":
        return cls(reply=hint, handled=False, needs_llm=True, intent="unknown")


IntentHandler = Callable[["Intent", str, WorkspaceSnapshot, ToolContext], IntentResult]


@dataclass
class Intent:
    name: str
    patterns: list[re.Pattern]
    handler: IntentHandler
    description: str = ""
    fuzzy_keywords: list[str] = field(default_factory=list)

    def matches(self, text: str) -> re.Match | None:
        for p in self.patterns:
            m = p.search(text)
            if m:
                return m
        # Fuzzy fallback: only fire if EVERY fuzzy keyword group has a match.
        # A keyword group is a "|"-separated string of alternatives.
        if self.fuzzy_keywords:
            for group in self.fuzzy_keywords:
                needles = group.split("|")
                if not _fuzzy_contains(text, needles):
                    return None
            # Return a synthetic match so the handler can proceed.
            return re.match(r".*", text, re.DOTALL)
        return None


# ---- Handlers -------------------------------------------------------------

def _fmt_money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _handle_greeting(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """JARVIS-style greeting: crisp, situationally aware, quietly ready.

    Respects the user's ``tone`` preference (formal/casual/concise/technical/etc.)
    if one has been set via `set_tone`. Falls back to default formal-crisp.
    """
    lang = _detect_lang(text)
    c = snap.counts.get("contacts", 0)
    o = snap.counts.get("opportunities", 0)
    t = snap.counts.get("tasks_open", 0)
    name = (snap.preferences or {}).get("preferred_name")
    salut_pt = f", {name}" if name else ""
    salut_en = f", {name}" if name else ""
    tone = (snap.preferences or {}).get("tone", "formal")

    if tone == "casual":
        if lang == "pt":
            parts = [
                f"Opa{salut_pt}! Tô online 🙂 tudo local por aqui.",
                f"Você tem {c} contatos, {o} oportunidades e {t} tarefas em aberto.",
                "É só pedir. \"briefing\" pra resumo, \"o que devo fazer\" pra prioridades.",
            ]
        else:
            parts = [
                f"Hey{salut_en} 🙂 online and local.",
                f"You've got {c} contacts, {o} opportunities and {t} open tasks.",
                "Ask away. \"briefing\" for a summary, \"what should I do\" for priorities.",
            ]
    elif tone == "concise":
        if lang == "pt":
            parts = [
                f"Jarvis online{salut_pt}.",
                f"{c} contatos · {o} opp · {t} tarefas.",
            ]
        else:
            parts = [
                f"Jarvis online{salut_en}.",
                f"{c} contacts · {o} opps · {t} tasks.",
            ]
    elif tone == "technical":
        if lang == "pt":
            parts = [
                f"Sistema operacional{salut_pt}. Runtime local, sem dependências externas.",
                f"Snapshot: contacts={c} opportunities={o} tasks_open={t}",
                "Comandos: `briefing`, `pipeline health`, `data quality`, `sugestões`.",
            ]
        else:
            parts = [
                f"System operational{salut_en}. Local runtime, no external deps.",
                f"Snapshot: contacts={c} opportunities={o} tasks_open={t}",
                "Commands: `briefing`, `pipeline health`, `data quality`, `suggestions`.",
            ]
    else:  # formal (default) or neutral
        if lang == "pt":
            parts = [
                f"Bom dia{salut_pt}. Jarvis online, sistemas 100% locais.",
                f"Estado atual: {c} contatos, {o} oportunidades, {t} tarefas abertas.",
                "Ao seu dispor. Diga \"briefing\" para o resumo do dia ou \"o que devo fazer\" para prioridades.",
            ]
        else:
            parts = [
                f"Good day{salut_en}. Jarvis online, all systems local.",
                f"Current state: {c} contacts, {o} opportunities, {t} open tasks.",
                "At your service. Say \"briefing\" for the day's summary, or \"what should I do\" for priorities.",
            ]
    return IntentResult.ok("\n".join(parts), intent="greeting", confidence=0.95)


def _handle_help(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    lang = _detect_lang(text)
    lines_en = [
        "I run entirely on your machine — no cloud calls required. Things I can do right now:",
        "  • Today: \"what's on today\", \"today's schedule\"",
        "  • Counts: \"how many contacts / companies / leads / opportunities / tasks?\"",
        "  • Pipeline: \"summarize pipeline\", \"open opportunities\"",
        "  • Tasks: \"overdue tasks\", \"create task: <title>\", \"mark task <name> done\"",
        "  • Meetings: \"upcoming meetings\"",
        "  • Notes: \"create note: <body>\" or \"note: <body>\"",
        "  • Search: \"find contact <name>\", \"find company <name>\"",
        "  • Sales: \"move opportunity <name> to Negotiation\"",
        "  • Timeline: \"recent activity\"",
    ]
    lines_pt = [
        "Rodo inteiramente na sua máquina — sem chamadas à nuvem. O que posso fazer agora:",
        "  • Hoje: \"o que tem hoje\", \"agenda de hoje\"",
        "  • Contagens: \"quantos contatos / empresas / leads / oportunidades / tarefas?\"",
        "  • Pipeline: \"resumir pipeline\", \"oportunidades abertas\"",
        "  • Tarefas: \"tarefas vencidas\", \"criar tarefa: <título>\", \"concluir tarefa <nome>\"",
        "  • Reuniões: \"próximas reuniões\"",
        "  • Notas: \"criar nota: <texto>\" ou \"nota: <texto>\"",
        "  • Busca: \"buscar contato <nome>\", \"buscar empresa <nome>\"",
        "  • Vendas: \"mover oportunidade <nome> para Negociação\"",
        "  • Histórico: \"atividade recente\"",
    ]
    return IntentResult.ok("\n".join(lines_pt if lang == "pt" else lines_en), intent="help", confidence=1.0)


def _handle_count(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    lang = _detect_lang(text)
    # Map keyword → snapshot key
    keyword_map_en = {
        "contact": "contacts", "contacts": "contacts",
        "compan": "companies",
        "lead": "leads", "leads": "leads",
        "opportunit": "opportunities",
        "deal": "opportunities", "deals": "opportunities",
        "task": "tasks_open",
    }
    keyword_map_pt = {
        "contato": "contacts",
        "empresa": "companies",
        "lead": "leads",
        "oportunidad": "opportunities",
        "negócio": "opportunities",
        "negocio": "opportunities",
        "tarefa": "tasks_open",
    }
    lower = text.lower()
    picked: str | None = None
    for kw, key in (keyword_map_pt | keyword_map_en).items():
        if kw in lower:
            picked = key
            break
    if picked is None:
        return IntentResult(handled=False)
    n = snap.counts.get(picked, 0)
    label_en = {"contacts": "contacts", "companies": "companies", "leads": "leads",
                "opportunities": "opportunities", "tasks_open": "open tasks"}[picked]
    label_pt = {"contacts": "contatos", "companies": "empresas", "leads": "leads",
                "opportunities": "oportunidades", "tasks_open": "tarefas abertas"}[picked]
    reply = f"Você tem {n} {label_pt} neste workspace." if lang == "pt" else f"You have {n} {label_en} in this workspace."
    return IntentResult.ok(reply, intent=f"count_{picked}", confidence=0.9)


def _handle_summarize_pipeline(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    reg = default_registry()
    result = reg.call("summarize_pipeline", ctx, {})
    lang = _detect_lang(text)
    if "error" in result:
        return IntentResult.ok(f"Couldn't summarize pipeline: {result['error']}", intent="summarize_pipeline", confidence=0.4)
    by_curr = ", ".join(f"{cur} {amt:,.2f}" for cur, amt in result.get("by_currency", {}).items()) or "—"
    if lang == "pt":
        reply = (
            f"Pipeline: {result['open_count']} oportunidades abertas.\n"
            f"Valor total: {by_curr}.\n"
            f"Valor ponderado (probabilidade × valor): {result['weighted_amount']:,.2f}."
        )
    else:
        reply = (
            f"Pipeline: {result['open_count']} open opportunities.\n"
            f"Total value: {by_curr}.\n"
            f"Weighted (probability × amount): {result['weighted_amount']:,.2f}."
        )
    return IntentResult.ok(reply, intent="summarize_pipeline", tool_calls=[{"name": "summarize_pipeline", "input": {}, "result": result}], confidence=0.95)


def _handle_overdue_tasks(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    lang = _detect_lang(text)
    if not snap.overdue_tasks:
        return IntentResult.ok(
            "Nenhuma tarefa vencida. 🎉" if lang == "pt" else "No overdue tasks. 🎉",
            intent="overdue_tasks",
        )
    header = "Tarefas vencidas:" if lang == "pt" else "Overdue tasks:"
    lines = [header]
    for t in snap.overdue_tasks[:10]:
        lines.append(f"  • {t['title']} (venceu {t['due_at']})" if lang == "pt" else f"  • {t['title']} (was due {t['due_at']})")
    return IntentResult.ok("\n".join(lines), intent="overdue_tasks", confidence=0.95)


def _handle_upcoming_meetings(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    lang = _detect_lang(text)
    if not snap.upcoming_meetings:
        return IntentResult.ok(
            "Nenhuma reunião nas próximas 48h." if lang == "pt" else "No meetings scheduled in the next 48h.",
            intent="upcoming_meetings",
        )
    header = "Próximas reuniões (48h):" if lang == "pt" else "Upcoming meetings (48h):"
    lines = [header]
    for m in snap.upcoming_meetings[:10]:
        lines.append(f"  • {m['title']} @ {m['starts_at']}")
    return IntentResult.ok("\n".join(lines), intent="upcoming_meetings", confidence=0.95)


def _handle_open_opportunities(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    lang = _detect_lang(text)
    reg = default_registry()
    result = reg.call("list_open_opportunities", ctx, {"limit": 10})
    rows = result.get("results", [])
    if not rows:
        return IntentResult.ok(
            "Nenhuma oportunidade aberta no momento." if lang == "pt" else "No open opportunities right now.",
            intent="open_opportunities",
        )
    header = "Oportunidades abertas (top por valor):" if lang == "pt" else "Open opportunities (top by amount):"
    lines = [header]
    for o in rows:
        lines.append(f"  • {o['name']} — {_fmt_money(o['amount'], o['currency'])}")
    return IntentResult.ok(
        "\n".join(lines),
        intent="open_opportunities",
        tool_calls=[{"name": "list_open_opportunities", "input": {"limit": 10}, "result": result}],
        confidence=0.95,
    )


def _handle_opportunities_by_status(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Won/lost opportunities."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    lower = _normalize(text)
    if "won" in lower or "ganh" in lower or "vencid" in lower or "ganad" in lower:
        status = OpportunityStatus.won
        label_pt, label_en = "ganhas", "won"
    elif "lost" in lower or "perdid" in lower:
        status = OpportunityStatus.lost
        label_pt, label_en = "perdidas", "lost"
    else:
        return IntentResult(handled=False)
    opps = list(ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == status,
        ).order_by(Opportunity.closed_at.desc().nulls_last(), Opportunity.updated_at.desc()).limit(15)
    ).all())
    if not opps:
        empty = f"Nenhuma oportunidade {label_pt}." if lang == "pt" else f"No {label_en} opportunities."
        return IntentResult.ok(empty, intent="opportunities_by_status", confidence=0.9)
    header = (f"Oportunidades {label_pt}:" if lang == "pt" else f"{label_en.capitalize()} opportunities:")
    lines = [header]
    for o in opps:
        lines.append(f"  • {o.name} — {_fmt_money(o.amount, o.currency)}")
    return IntentResult.ok(
        "\n".join(lines), intent="opportunities_by_status", confidence=0.92,
        tool_calls=[{
            "name": "recent_list", "kind": "opportunity",
            "items": [{"id": str(o.id), "name": o.name} for o in opps],
        }],
    )


def _handle_win_rate(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Won / (Won + Lost) — the classic sales KPI."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    opps = list(ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status.in_([OpportunityStatus.won, OpportunityStatus.lost]),
        )
    ).all())
    won = [o for o in opps if o.status == OpportunityStatus.won]
    lost = [o for o in opps if o.status == OpportunityStatus.lost]
    total = len(won) + len(lost)
    if total == 0:
        return IntentResult.ok(
            "Ainda não há oportunidades ganhas ou perdidas." if lang == "pt"
            else "No won or lost opportunities yet.",
            intent="win_rate", confidence=0.9,
        )
    rate = 100.0 * len(won) / total
    won_amt = sum(o.amount or 0 for o in won)
    lost_amt = sum(o.amount or 0 for o in lost)
    currency = (won or lost)[0].currency
    if lang == "pt":
        body = (f"🎯 Win rate: **{rate:.0f}%** ({len(won)} ganhas / {len(lost)} perdidas)\n"
                f"  Ganho: {_fmt_money(won_amt, currency)}\n"
                f"  Perdido: {_fmt_money(lost_amt, currency)}")
    else:
        body = (f"🎯 Win rate: **{rate:.0f}%** ({len(won)} won / {len(lost)} lost)\n"
                f"  Won: {_fmt_money(won_amt, currency)}\n"
                f"  Lost: {_fmt_money(lost_amt, currency)}")
    return IntentResult.ok(body, intent="win_rate", confidence=0.94)


def _handle_amount_this_period(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """'ganhei quanto este mes/semana' / 'won this month'."""
    from datetime import datetime, timedelta, timezone
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    lower = _normalize(text)
    is_lost = "perdi" in lower or "lost" in lower or "perd" in lower
    # Time window
    now = datetime.now(timezone.utc)
    if "semana" in lower or "week" in lower:
        # Start of week (Monday)
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        label_pt, label_en = "esta semana", "this week"
    elif "ano" in lower or "year" in lower:
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        label_pt, label_en = "este ano", "this year"
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label_pt, label_en = "este mês", "this month"
    status = OpportunityStatus.lost if is_lost else OpportunityStatus.won
    action_pt, action_en = ("Perdido", "Lost") if is_lost else ("Ganho", "Won")
    opps = list(ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == status,
            Opportunity.closed_at.is_not(None),
        )
    ).all())
    # Filter by closed_at within window
    filtered = []
    for o in opps:
        closed = o.closed_at if o.closed_at.tzinfo else o.closed_at.replace(tzinfo=timezone.utc)
        if closed >= start:
            filtered.append(o)
    total = sum(o.amount or 0 for o in filtered)
    currency = filtered[0].currency if filtered else "USD"
    if lang == "pt":
        body = f"💰 {action_pt} {label_pt}: **{_fmt_money(total, currency)}** ({len(filtered)} oportunidade{'s' if len(filtered) != 1 else ''})"
    else:
        body = f"💰 {action_en} {label_en}: **{_fmt_money(total, currency)}** ({len(filtered)} deal{'s' if len(filtered) != 1 else ''})"
    return IntentResult.ok(body, intent="amount_this_period", confidence=0.92)


def _handle_tasks_today(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """'tarefas de hoje', 'my tasks', 'minhas tarefas' — open tasks due today or unscheduled."""
    from datetime import datetime, timedelta, timezone
    from sqlmodel import select
    from app.models import Task, TaskStatus
    lang = _detect_lang(text)
    lower = _normalize(text)
    now = datetime.now(timezone.utc)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    # 'my tasks' → all open; 'today' → due today or overdue
    only_today = "hoje" in lower or "today" in lower
    stmt = select(Task).where(
        Task.workspace_id == ctx.workspace_id,
        Task.deleted_at.is_(None),
        Task.status.in_([TaskStatus.todo, TaskStatus.in_progress, TaskStatus.blocked]),
    )
    tasks = list(ctx.session.exec(stmt).all())
    if only_today:
        tasks = [t for t in tasks if not t.due_at or (
            (t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)) <= today_end
        )]
    tasks.sort(key=lambda t: (t.due_at or now))
    if not tasks:
        empty = ("Nenhuma tarefa aberta." if lang == "pt" else "No open tasks.")
        return IntentResult.ok(empty, intent="tasks_today", confidence=0.9)
    header = (f"✓ {len(tasks)} tarefa{'s' if len(tasks) != 1 else ''} " +
              ("para hoje:" if only_today else "abertas:") if lang == "pt"
              else f"✓ {len(tasks)} open task{'s' if len(tasks) != 1 else ''}:")
    lines = [header]
    for t in tasks[:15]:
        due = ""
        if t.due_at:
            d = t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)
            due = f" · {d.strftime('%d/%m %H:%M')}" if d.date() != now.date() else f" · hoje {d.strftime('%H:%M')}"
        lines.append(f"  • {t.title}{due}")
    if len(tasks) > 15:
        lines.append(f"  … +{len(tasks) - 15}")
    return IntentResult.ok("\n".join(lines), intent="tasks_today", confidence=0.94)


_CREATE_TASK_RE = re.compile(
    r"(?:criar|crie|create|adicionar|adicione|add)\s+(?:uma\s+|a\s+|new\s+)?(?:tarefa|task)\s*[:\-]?\s*(?P<title>.+)",
    re.IGNORECASE,
)
_REMINDER_RE = re.compile(
    r"^(?:lembre[-\s]me\s+(?:de|a|para)\s+|me\s+lembr[ae]\s+(?:de|a|para)\s+|lembrete\s*[:\-]\s*|remind\s+me\s+to\s+)(?P<title>.+)",
    re.IGNORECASE,
)
# Form B: "me lembra amanhã 15h de ligar pra Alice" — when first, then title.
_REMINDER_WHEN_FIRST_RE = re.compile(
    r"^(?:me\s+lembr[ae]|lembre[-\s]me|remind\s+me)\s+"
    r"(?P<when>(?:hoje|amanh[ãa]|amanha|tomorrow|tonight|today|next\s+\S+|pr[óo]xim[oa]\s+\S+|"
    r"seg(?:unda)?|ter(?:[cç]a)?|qua(?:rta)?|qui(?:nta)?|sex(?:ta)?|s[áa]b(?:ado)?|dom(?:ingo)?|"
    r"mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"\d{1,2}[:h/-]\d{0,2}\S*|\d{1,2}\s*(?:am|pm|h))"
    r"(?:\s+(?:(?:as|às|at)\s+)?\d{1,2}[:h]?\d{0,2}\S*(?:\s*(?:am|pm|h))?)?)\s+"
    r"(?:de|a|para|to|of)\s+"
    r"(?P<title>.+)",
    re.IGNORECASE,
)


_TASK_PRIORITY_MAP = {
    "urgent": "urgent", "urgente": "urgent", "asap": "urgent", "critical": "urgent",
    "high": "high", "alta": "high", "importante": "high",
    "low": "low", "baixa": "low",
    "normal": "normal", "média": "normal", "media": "normal",
}
_TASK_PRIORITY_RE = re.compile(
    r"\b(urgent|urgente|asap|critical|high|alta|importante|low|baixa|normal|m[eé]dia)\b\s*$",
    re.IGNORECASE,
)
_TASK_DUE_HINTS = re.compile(
    r"\b(hoje|amanh[ãa]|today|tomorrow|next\s+week|semana\s+que\s+vem|"
    r"seg(?:unda)?|ter(?:ça|ca)?|qua(?:rta)?|qui(?:nta)?|sex(?:ta)?|s[áa]bado|domingo|"
    r"mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?|"
    r"\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm|h))\b.*$",
    re.IGNORECASE,
)
_TASK_WITH_CONTACT_RE = re.compile(
    r"\b(?:com|with)\s+(?P<name>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']+(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']+)?)\b",
    re.IGNORECASE,
)


def _handle_create_task(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    from app.jarvis.date_parser import parse_when
    from datetime import datetime, timezone
    from sqlmodel import select
    from app.models import Contact, Task, TaskPriority
    from app.services.crud import like_escape

    # Form B ("me lembra amanhã de X") — WHEN first, TITLE last
    mb = _REMINDER_WHEN_FIRST_RE.match(text.strip())
    if mb:
        when_str = mb.group("when").strip()
        title = mb.group("title").strip().rstrip(".")
        # Reconstruct as "title when" so downstream date-extraction picks it up
        text = f"lembrete: {title} {when_str}"
    m = _CREATE_TASK_RE.search(text) or _REMINDER_RE.search(text)
    if not m:
        return IntentResult(handled=False)
    raw = m.group("title").strip().rstrip(".").strip().strip(":-")
    raw = re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ]+$", "", raw).strip()
    lang = _detect_lang(text)
    if not raw or not re.search(r"\w", raw):
        return IntentResult.ok(
            "Diga o título: \"crie tarefa: revisar contrato\"." if lang == "pt"
            else "Give a title: \"create task: review contract\".",
            intent="create_task", confidence=0.6,
        )

    working = raw
    # Extract priority (trailing word)
    prio = None
    pm = _TASK_PRIORITY_RE.search(working)
    if pm:
        prio = _TASK_PRIORITY_MAP.get(pm.group(1).lower(), "normal")
        working = working[:pm.start()].rstrip()

    # Extract due (last date-ish tail)
    due_dt = None
    dm = _TASK_DUE_HINTS.search(working)
    if dm:
        tail = dm.group(0).strip()
        parsed = parse_when(tail)
        if parsed is not None:
            due_dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            working = working[:dm.start()].rstrip(" ,.").rstrip()

    # Contact linkage via "with X" / "com X"
    contact = None
    cm = _TASK_WITH_CONTACT_RE.search(working)
    if cm:
        name_query = cm.group("name").strip()
        like = f"%{like_escape(name_query)}%"
        contact = ctx.session.exec(
            select(Contact).where(
                Contact.workspace_id == ctx.workspace_id,
                Contact.deleted_at.is_(None),
                (Contact.first_name.ilike(like, escape="\\")) | (Contact.last_name.ilike(like, escape="\\"))
            ).limit(1)
        ).first()

    title = working.strip() or raw
    task = Task(
        workspace_id=ctx.workspace_id,
        title=title,
        due_at=due_dt,
        assignee_user_id=ctx.user_id,
        related_contact_id=contact.id if contact else None,
        priority=TaskPriority(prio) if prio else TaskPriority.normal,
    )
    ctx.session.add(task)
    ctx.session.commit()
    ctx.session.refresh(task)

    parts = [f"\"{task.title}\""]
    if due_dt:
        parts.append(f"— {due_dt.strftime('%Y-%m-%d %H:%M')}")
    if prio and prio != "normal":
        parts.append(f"[{prio}]")
    if contact:
        parts.append(f"→ {contact.first_name} {contact.last_name or ''}".strip())
    header = "✅ Tarefa criada: " if lang == "pt" else "✅ Task created: "
    reply = header + " ".join(parts)
    tone = (snap.preferences or {}).get("tone", "formal")
    if tone in ("casual", "formal") and not due_dt:
        nudge = ("\n💡 Sem prazo? Adicione: `me lembra amanhã 15h de X`" if lang == "pt"
                 else "\n💡 No deadline? Add: `remind me tomorrow 3pm to X`")
        reply += nudge
    return IntentResult.ok(
        reply,
        intent="create_task",
        tool_calls=[{"name": "create_task", "input": {"title": title, "priority": prio, "due_at": due_dt.isoformat() if due_dt else None, "contact_id": str(contact.id) if contact else None}, "result": {"id": str(task.id)}}],
        confidence=0.95,
    )


_FIND_CONTACT_RE = re.compile(
    r"(?:buscar|busque|busca|find|search|encontr(?:e|ar)|localiz(?:e|ar)|procur(?:e|ar|a)|ache)\s+(?:o\s+|a\s+)?(?:contato|contact)\s+(?P<q>.+)",
    re.IGNORECASE,
)
_FIND_COMPANY_RE = re.compile(
    r"(?:buscar|busque|busca|find|search|encontr(?:e|ar)|localiz(?:e|ar)|procur(?:e|ar|a)|ache)\s+(?:a\s+|the\s+)?(?:empresa|company)\s+(?P<q>.+)",
    re.IGNORECASE,
)


def _handle_find_contact(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _FIND_CONTACT_RE.search(text)
    if not m:
        return IntentResult(handled=False)
    query = m.group("q").strip().rstrip("?.").strip()
    reg = default_registry()
    result = reg.call("search_contacts", ctx, {"query": query, "limit": 5})
    rows = result.get("results", [])
    lang = _detect_lang(text)
    if not rows:
        return IntentResult.ok(
            f"Nenhum contato encontrado para '{query}'." if lang == "pt" else f"No contacts found for '{query}'.",
            intent="find_contact",
        )
    header = f"Contatos que combinam com '{query}':" if lang == "pt" else f"Contacts matching '{query}':"
    lines = [header]
    for c in rows:
        detail = " · ".join(v for v in [c.get("email"), c.get("phone"), c.get("job_title")] if v)
        lines.append(f"  • {c['name']}{(' — ' + detail) if detail else ''}")
    return IntentResult.ok(
        "\n".join(lines),
        intent="find_contact",
        tool_calls=[{"name": "search_contacts", "input": {"query": query, "limit": 5}, "result": result}],
        confidence=0.9,
    )


_CREATE_NOTE_RE = re.compile(
    r"(?:criar|crie|create|adicionar|adicione|add|nova|nova?)\s+(?:uma\s+)?(?:nota|note)\s*[:\-]?\s*(?P<body>.+)",
    re.IGNORECASE,
)
_SHORT_NOTE_RE = re.compile(r"^\s*(?:nota|note)\s*[:\-]\s*(?P<body>.+)", re.IGNORECASE)


def _handle_create_note(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _CREATE_NOTE_RE.search(text) or _SHORT_NOTE_RE.search(text)
    if not m:
        return IntentResult(handled=False)
    body = m.group("body").strip().rstrip(".").strip().strip(":-")
    body = re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ]+$", "", body).strip()
    lang = _detect_lang(text)
    if not body or not re.search(r"\w", body):
        return IntentResult.ok(
            "Diga o conteúdo: \"nota: fechar contrato X\"." if lang == "pt"
            else "Give a body: \"note: close X contract\".",
            intent="create_note", confidence=0.6,
        )
    reg = default_registry()
    result = reg.call("create_note", ctx, {"body": body})
    if "error" in result:
        return IntentResult.ok(
            f"Não consegui criar a nota: {result['error']}" if lang == "pt" else f"Couldn't create note: {result['error']}",
            intent="create_note",
            confidence=0.5,
        )
    reply = f"Nota criada (id {result['id']})." if lang == "pt" else f"Note created (id {result['id']})."
    return IntentResult.ok(
        reply,
        intent="create_note",
        tool_calls=[{"name": "create_note", "input": {"body": body}, "result": result}],
        confidence=0.9,
    )


# ---- Direct entity creation from chat ----------------------------------------
_CREATE_CONTACT_RE = re.compile(
    r"^\s*(?:novo|new|adicione?|adiciona|adicionar|add|crie?|cria|criar|create)\s+(?:o\s+|a\s+|um\s+|uma\s+|the\s+)?(?:contato|contact)\s*[:\-]?\s*(?P<name>.+?)\s*$",
    re.IGNORECASE,
)
_CREATE_COMPANY_RE = re.compile(
    r"^\s*(?:nova|new|adicione?|adiciona|adicionar|add|crie?|cria|criar|create)\s+(?:a\s+|uma\s+|the\s+)?(?:empresa|company)\s*[:\-]?\s*(?P<name>.+?)\s*$",
    re.IGNORECASE,
)
_CREATE_OPPORTUNITY_RE = re.compile(
    r"^\s*(?:nova|new|adicione?|adiciona|adicionar|add|crie?|cria|criar|create)\s+(?:a\s+|uma\s+|the\s+)?"
    r"(?:oportunidade|opportunity|deal|neg[óo]cio|opp)\s*[:\-]?\s*(?P<name>.+?)\s*$",
    re.IGNORECASE,
)
# amount hint: "50k", "50 mil", "R$ 50000", "$50000", "50000"
_AMOUNT_HINT_RE = re.compile(
    r"(?:r\$\s*|us?\$\s*|\$\s*)?(?P<num>\d[\d.,]*)\s*(?P<suffix>k|mil|m|milh(?:[ãa]o|[oõ]es))?\s*$",
    re.IGNORECASE,
)


def _parse_amount_hint(raw: str) -> tuple[float | None, str]:
    """Extract a trailing amount from a free-form name. Returns (amount, cleaned_name)."""
    raw = raw.strip()
    m = _AMOUNT_HINT_RE.search(raw)
    if not m:
        return None, raw
    num_str = m.group("num").replace(".", "").replace(",", ".")
    # Ambiguous: "50.000" — if 3 zeros after dot, treat as thousands separator
    try:
        val = float(num_str)
    except ValueError:
        return None, raw
    suffix = (m.group("suffix") or "").lower()
    if suffix in ("k", "mil"):
        val *= 1000
    elif suffix in ("m", "milhão", "milhao", "milhões", "milhoes"):
        val *= 1_000_000
    # Only accept if the amount is substantial enough to not be a stray year
    if val < 100:
        return None, raw
    # Strip the matched amount from name
    cleaned = raw[:m.start()].strip().rstrip(",").rstrip("-").rstrip("|").strip()
    return val, cleaned or raw


# --- Update entity field ------------------------------------------------------
# Natural-language field editor. Supports:
#   "email do Alice é foo@bar.com"
#   "muda o telefone do Bob para 999999"
#   "atualize o cargo da Alice: CTO"
#   "update Alice email = foo@bar.com"
#   "amount da oportunidade Big Deal = 50000"
_FIELD_ALTS = (
    r"email|e-mail|telefone|phone|cargo|title|job[_\s]?title|nome|name|"
    r"amount|valor|probabilidade|probability|website|site|dom[íi]nio|domain|"
    r"ind[úu]stria|industry|score"
)
# Form A (PT natural): "email do Alice é X" / "muda o telefone do Bob para X"
_UPDATE_FIELD_RE_A = re.compile(
    r"^\s*(?:atualize?|atualizar|muda|mude|mudar|edit|update|set|troca|troque|trocar)?\s*"
    r"(?:o\s+|a\s+|the\s+)?"
    rf"(?P<field>{_FIELD_ALTS})\s+"
    r"(?:do|da|de|of|from|for)\s+"
    r"(?:contato|contact|empresa|company|oportunidade|opportunity|lead|deal|neg[óo]cio)?\s*"
    # Subject: any chars up to the separator token (é|=|:|para|to)
    r"(?P<subject>.+?)\s*"
    r"(?:é|=|:|\s+para|\s+to)\s+"
    r"(?P<value>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)
# Form B (EN imperative): "update Alice email = X" / "set Alice email to X"
_UPDATE_FIELD_RE_B = re.compile(
    r"^\s*(?:update|set|edit|muda|mude|atualize?|troca|troque)\s+"
    r"(?:contato|contact|empresa|company|oportunidade|opportunity|lead)?\s*"
    r"(?P<subject>.+?)\s+"
    rf"(?P<field>{_FIELD_ALTS})\s+"
    r"(?:=|to|para|é|:)\s+"
    r"(?P<value>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)

# clear_field: "apaga o email do Alice" / "remove o telefone do Bob" / "clear Alice email"
_CLEAR_FIELD_RE_A = re.compile(
    r"^\s*(?:apaga|apagar|apague|remove|remover|remova|limpa|limpar|limpe|clear|delete)\s+"
    r"(?:o\s+|a\s+|the\s+)?"
    rf"(?P<field>{_FIELD_ALTS})\s+"
    r"(?:do|da|de|of|from|for)\s+"
    r"(?:contato|contact|empresa|company|oportunidade|opportunity|lead|deal|neg[óo]cio)?\s*"
    r"(?P<subject>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)
_CLEAR_FIELD_RE_B = re.compile(
    r"^\s*(?:clear|remove|delete|apaga|apagar|apague|remova|limpa|limpar|limpe)\s+"
    r"(?:contato|contact|empresa|company|oportunidade|opportunity|lead)?\s*"
    r"(?P<subject>.+?)\s+"
    rf"(?P<field>{_FIELD_ALTS})\s*[?!.]?\s*$",
    re.IGNORECASE,
)

_UPDATE_FIELD_MAP = {
    "email": "email", "e-mail": "email",
    "telefone": "phone", "phone": "phone",
    "cargo": "job_title", "title": "job_title", "job_title": "job_title", "job title": "job_title",
    "nome": "name", "name": "name",
    "amount": "amount", "valor": "amount",
    "probabilidade": "probability", "probability": "probability",
    "website": "domain", "site": "domain",
    "dominio": "domain", "domínio": "domain", "domain": "domain",
    "industria": "industry", "indústria": "industry", "industry": "industry",
    "score": "score",
}


def _handle_update_field(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Update a single field on a contact/company/opportunity/lead by name."""
    from sqlmodel import select, or_
    from app.models import Contact, Company, Opportunity, Lead
    from app.services.crud import like_escape
    m = _UPDATE_FIELD_RE_A.match(text.strip()) or _UPDATE_FIELD_RE_B.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    lang = _detect_lang(text)
    field_raw = m.group("field").lower()
    subject = m.group("subject").strip().strip("\"'").rstrip(",.")
    value = m.group("value").strip().strip("\"'").rstrip(",.")
    field = _UPDATE_FIELD_MAP.get(field_raw)
    if not field or not subject or not value:
        return IntentResult(handled=False)
    # Coerce amount/probability/score to numbers
    if field in ("amount", "probability", "score"):
        try:
            value_num = float(value.replace(",", ".").replace("$", "").replace("R", "").strip())
            value = value_num
        except ValueError:
            return IntentResult.ok(
                f"Valor \"{m.group('value')}\" não é numérico." if lang == "pt"
                else f"Value \"{m.group('value')}\" is not numeric.",
                intent="update_field", confidence=0.7,
            )
    # Search across entity kinds — first match wins
    like = f"%{like_escape(subject)}%"
    tokens = subject.split()
    tries = []
    # Contact
    contact_conds = [Contact.first_name.ilike(like, escape="\\"),
                     Contact.last_name.ilike(like, escape="\\"),
                     Contact.email.ilike(like, escape="\\")]
    if len(tokens) >= 2:
        from sqlmodel import and_
        contact_conds.append(and_(
            Contact.first_name.ilike(f"%{like_escape(tokens[0])}%", escape="\\"),
            Contact.last_name.ilike(f"%{like_escape(tokens[-1])}%", escape="\\"),
        ))
    obj = ctx.session.exec(
        select(Contact).where(
            Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
            or_(*contact_conds),
        ).limit(1)
    ).first()
    kind = "contact" if obj else None
    if not obj:
        obj = ctx.session.exec(
            select(Company).where(
                Company.workspace_id == ctx.workspace_id, Company.deleted_at.is_(None),
                or_(Company.name.ilike(like, escape="\\"), Company.domain.ilike(like, escape="\\")),
            ).limit(1)
        ).first()
        kind = "company" if obj else None
    if not obj:
        obj = ctx.session.exec(
            select(Opportunity).where(
                Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
                Opportunity.name.ilike(like, escape="\\"),
            ).limit(1)
        ).first()
        kind = "opportunity" if obj else None
    if not obj:
        obj = ctx.session.exec(
            select(Lead).where(
                Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
                or_(Lead.first_name.ilike(like, escape="\\"),
                    Lead.last_name.ilike(like, escape="\\"),
                    Lead.email.ilike(like, escape="\\")),
            ).limit(1)
        ).first()
        kind = "lead" if obj else None
    if not obj:
        return IntentResult.ok(
            f"Não encontrei \"{subject}\"." if lang == "pt" else f"Nothing matches \"{subject}\".",
            intent="update_field", confidence=0.7,
        )
    # Verify field applies to this kind
    if not hasattr(obj, field):
        return IntentResult.ok(
            f"Campo \"{field_raw}\" não existe em {kind}." if lang == "pt"
            else f"Field \"{field_raw}\" doesn't exist on {kind}.",
            intent="update_field", confidence=0.7,
        )
    old_value = getattr(obj, field)
    setattr(obj, field, value)
    ctx.session.add(obj)
    ctx.session.commit()
    ctx.session.refresh(obj)
    display_name = getattr(obj, "name", None) or f"{getattr(obj, 'first_name', '') or ''} {getattr(obj, 'last_name', '') or ''}".strip() or "?"
    return IntentResult.ok(
        (f"✅ {kind.capitalize()} \"{display_name}\" atualizado: {field} = {value} (antes: {old_value})"
         if lang == "pt"
         else f"✅ {kind.capitalize()} \"{display_name}\" updated: {field} = {value} (was: {old_value})"),
        intent="update_field", confidence=0.94,
        tool_calls=[{"name": f"update_{kind}",
                     "input": {"id": str(obj.id), "field": field, "value": value},
                     "result": {"old": str(old_value)}}],
    )


def _handle_explain_last(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Explain the last mutation in plain language.

    Reads ``conversation_context.last_tool_calls`` and describes what was done,
    to which entity, and how the user can reverse it.
    """
    lang = _detect_lang(text)
    tool_calls = (ctx.conversation_context or {}).get("last_tool_calls") or []
    # Latest actionable tool_call (skip diagnostic/list-only)
    target = None
    for tc in reversed(tool_calls):
        name = (tc.get("name") or "").lower()
        if name in ("ambiguity", "recent_list"):
            continue
        target = tc
        break
    if not target:
        return IntentResult.ok(
            "Nada pra explicar ainda — faça uma ação primeiro." if lang == "pt"
            else "Nothing to explain yet — make an action first.",
            intent="explain_last", confidence=0.85,
        )
    name = target.get("name") or "?"
    inp = target.get("input") or {}
    res = target.get("result") or {}
    lines: list[str] = []
    if name.startswith("update_") and "old" in res and inp.get("field"):
        kind = name.replace("update_", "")
        old = res.get("old")
        new = inp.get("value")
        if new is None:
            action = (f"Apaguei o campo `{inp.get('field')}` de um {kind} (era `{old}`)."
                      if lang == "pt"
                      else f"I cleared field `{inp.get('field')}` on a {kind} (was `{old}`).")
        else:
            action = (f"Atualizei o campo `{inp.get('field')}` de um {kind} para `{new}` (antes: `{old}`)."
                      if lang == "pt"
                      else f"I updated field `{inp.get('field')}` on a {kind} to `{new}` (was: `{old}`).")
        lines.append(action)
        lines.append("Pra reverter, digite: `desfaz`" if lang == "pt" else "To revert, type: `undo`")
    elif name.startswith("delete_"):
        kind = name.replace("delete_", "")
        lines.append(f"Apaguei um {kind}." if lang == "pt" else f"I deleted a {kind}.")
        lines.append("Ficou no histórico (soft-delete) — restaura via API se precisar."
                     if lang == "pt"
                     else "It's soft-deleted — restore via API if needed.")
    elif name == "bulk_delete_tasks":
        count = res.get("count", "?")
        filt = inp.get("filter") or "all"
        lines.append((f"Apaguei {count} tarefas ({filt})." if lang == "pt"
                      else f"I deleted {count} tasks ({filt})."))
    elif name.startswith("create_"):
        kind = name.replace("create_", "")
        obj_name = res.get("name") or "?"
        lines.append((f"Criei o {kind} \"{obj_name}\"." if lang == "pt"
                      else f"I created {kind} \"{obj_name}\"."))
    elif name == "move_opportunity_stage":
        stage = res.get("stage") or inp.get("stage") or "?"
        obj_name = res.get("name") or "?"
        lines.append((f"Movi \"{obj_name}\" para o estágio {stage}." if lang == "pt"
                      else f"I moved \"{obj_name}\" to stage {stage}."))
    else:
        lines.append((f"Última ação: {name} (input: {inp})." if lang == "pt"
                      else f"Last action: {name} (input: {inp})."))
    return IntentResult.ok(
        "\n".join(lines),
        intent="explain_last", confidence=0.9,
    )


def _find_entity_by_subject(ctx: ToolContext, subject: str):
    """Search contact → company → opportunity → lead by fuzzy subject. Returns (obj, kind)."""
    from sqlmodel import select, or_, and_
    from app.models import Contact, Company, Opportunity, Lead
    from app.services.crud import like_escape
    like = f"%{like_escape(subject)}%"
    tokens = subject.split()
    contact_conds = [
        Contact.first_name.ilike(like, escape="\\"),
        Contact.last_name.ilike(like, escape="\\"),
        Contact.email.ilike(like, escape="\\"),
    ]
    if len(tokens) >= 2:
        contact_conds.append(and_(
            Contact.first_name.ilike(f"%{like_escape(tokens[0])}%", escape="\\"),
            Contact.last_name.ilike(f"%{like_escape(tokens[-1])}%", escape="\\"),
        ))
    obj = ctx.session.exec(
        select(Contact).where(
            Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
            or_(*contact_conds),
        ).limit(1)
    ).first()
    if obj:
        return obj, "contact"
    obj = ctx.session.exec(
        select(Company).where(
            Company.workspace_id == ctx.workspace_id, Company.deleted_at.is_(None),
            or_(Company.name.ilike(like, escape="\\"), Company.domain.ilike(like, escape="\\")),
        ).limit(1)
    ).first()
    if obj:
        return obj, "company"
    obj = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
            Opportunity.name.ilike(like, escape="\\"),
        ).limit(1)
    ).first()
    if obj:
        return obj, "opportunity"
    obj = ctx.session.exec(
        select(Lead).where(
            Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
            or_(Lead.first_name.ilike(like, escape="\\"),
                Lead.last_name.ilike(like, escape="\\"),
                Lead.email.ilike(like, escape="\\")),
        ).limit(1)
    ).first()
    if obj:
        return obj, "lead"
    return None, None


def _handle_clear_field(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Clear (set to None) a single field on an entity found by name."""
    m = _CLEAR_FIELD_RE_A.match(text.strip()) or _CLEAR_FIELD_RE_B.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    lang = _detect_lang(text)
    field_raw = m.group("field").lower()
    subject = m.group("subject").strip().strip("\"'").rstrip(",.")
    field = _UPDATE_FIELD_MAP.get(field_raw)
    if not field or not subject:
        return IntentResult(handled=False)
    obj, kind = _find_entity_by_subject(ctx, subject)
    if not obj:
        return IntentResult.ok(
            f"Não encontrei \"{subject}\"." if lang == "pt" else f"Nothing matches \"{subject}\".",
            intent="clear_field", confidence=0.7,
        )
    if not hasattr(obj, field):
        return IntentResult.ok(
            f"Campo \"{field_raw}\" não existe em {kind}." if lang == "pt"
            else f"Field \"{field_raw}\" doesn't exist on {kind}.",
            intent="clear_field", confidence=0.7,
        )
    old_value = getattr(obj, field)
    if old_value is None or old_value == "":
        return IntentResult.ok(
            f"O campo \"{field}\" já está vazio." if lang == "pt"
            else f"Field \"{field}\" is already empty.",
            intent="clear_field", confidence=0.85,
        )
    setattr(obj, field, None)
    ctx.session.add(obj)
    ctx.session.commit()
    ctx.session.refresh(obj)
    display_name = getattr(obj, "name", None) or f"{getattr(obj, 'first_name', '') or ''} {getattr(obj, 'last_name', '') or ''}".strip() or "?"
    return IntentResult.ok(
        (f"🧹 {kind.capitalize()} \"{display_name}\": {field} apagado (era {old_value})"
         if lang == "pt"
         else f"🧹 {kind.capitalize()} \"{display_name}\": {field} cleared (was {old_value})"),
        intent="clear_field", confidence=0.94,
        tool_calls=[{"name": f"update_{kind}",
                     "input": {"id": str(obj.id), "field": field, "value": None},
                     "result": {"old": str(old_value)}}],
    )


def _handle_undo_last(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Reverse the most recent reversible mutation from conversation history.

    Reads conversation_context.last_tool_calls for an entry with a
    ``result.old`` (currently produced by update_field) and rolls it back.
    """
    from sqlmodel import select
    from app.models import Contact, Company, Opportunity, Lead
    lang = _detect_lang(text)
    tool_calls = (ctx.conversation_context or {}).get("last_tool_calls") or []
    # Find latest reversible mutation
    target = None
    for tc in reversed(tool_calls):
        name = (tc.get("name") or "").lower()
        result = tc.get("result") or {}
        input_ = tc.get("input") or {}
        if result.get("reason") == "undo":
            # Undo tags its own tool_calls so we don't ping-pong reverses.
            continue
        if name.startswith("update_") and "old" in result and input_.get("id") and input_.get("field"):
            target = tc
            break
    if not target:
        return IntentResult.ok(
            "Nada para desfazer na conversa recente." if lang == "pt"
            else "Nothing to undo in recent conversation.",
            intent="undo_last", confidence=0.85,
        )
    kind = (target.get("name") or "").replace("update_", "")
    model_map = {"contact": Contact, "company": Company, "opportunity": Opportunity, "lead": Lead}
    Model = model_map.get(kind)
    if not Model:
        return IntentResult.ok(
            "Não sei desfazer esse tipo de mudança." if lang == "pt"
            else "I don't know how to undo that kind of change.",
            intent="undo_last", confidence=0.7,
        )
    from uuid import UUID as _UUID
    try:
        obj_id = _UUID(target["input"]["id"])
    except Exception:
        return IntentResult.ok(
            "Referência interna inválida." if lang == "pt" else "Bad internal reference.",
            intent="undo_last", confidence=0.5,
        )
    obj = ctx.session.exec(
        select(Model).where(Model.workspace_id == ctx.workspace_id, Model.id == obj_id)
    ).first()
    if not obj:
        return IntentResult.ok(
            "O registro não existe mais." if lang == "pt" else "That record no longer exists.",
            intent="undo_last", confidence=0.7,
        )
    field = target["input"]["field"]
    current_value = getattr(obj, field, None)
    old_value_str = target["result"]["old"]
    # Coerce back to correct type
    old_value: object = old_value_str
    if old_value_str in ("None", "null", ""):
        old_value = None
    elif field in ("amount", "probability", "score"):
        try:
            old_value = float(old_value_str)
        except (ValueError, TypeError):
            old_value = None
    setattr(obj, field, old_value)
    ctx.session.add(obj)
    ctx.session.commit()
    ctx.session.refresh(obj)
    display_name = getattr(obj, "name", None) or f"{getattr(obj, 'first_name', '') or ''} {getattr(obj, 'last_name', '') or ''}".strip() or "?"
    return IntentResult.ok(
        (f"↩️ Desfeito: {kind} \"{display_name}\" — {field} voltou para {old_value} (era {current_value})"
         if lang == "pt"
         else f"↩️ Undone: {kind} \"{display_name}\" — {field} reverted to {old_value} (was {current_value})"),
        intent="undo_last", confidence=0.95,
        tool_calls=[{"name": f"update_{kind}",
                     "input": {"id": str(obj.id), "field": field, "value": old_value},
                     "result": {"old": str(current_value), "reason": "undo"}}],
    )


def _handle_create_contact(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    from app.models import Contact
    from app.services import crud
    m = _CREATE_CONTACT_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    raw_name = m.group("name").strip().strip("\"'").rstrip(".!?").strip(":-")
    # Strip leading/trailing punctuation that regex captured; must have real chars
    raw_name = re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ]+$", "", raw_name).strip()
    lang = _detect_lang(text)
    if not raw_name or not re.search(r"\w", raw_name):
        return IntentResult.ok(
            "Preciso do nome do contato. Ex.: \"novo contato: Alice Silva\"." if lang == "pt"
            else "I need a name. Ex.: \"new contact: Alice Smith\".",
            intent="create_contact", confidence=0.6,
        )
    parts = raw_name.split(None, 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else None
    obj = Contact(workspace_id=ctx.workspace_id, first_name=first, last_name=last)
    obj = crud.create_scoped(ctx.session, obj)
    full = f"{first} {last or ''}".strip()
    tone = (snap.preferences or {}).get("tone", "formal")
    if tone in ("casual", "formal"):
        # Proactive nudge — JARVIS anticipates the follow-up
        nudge = (f"\n💡 Adicione email/telefone com: `email do {first} é foo@bar.com`" if lang == "pt"
                 else f"\n💡 Add email/phone with: `email of {first} is foo@bar.com`")
    else:
        nudge = ""
    reply = (f"✅ Contato criado: {full}{nudge}" if lang == "pt"
             else f"✅ Contact created: {full}{nudge}")
    return IntentResult.ok(
        reply, intent="create_contact", confidence=0.94,
        tool_calls=[{"name": "create_contact", "input": {"first_name": first, "last_name": last},
                     "result": {"id": str(obj.id), "name": full}}],
    )


def _handle_create_company(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    from app.models import Company
    from app.services import crud
    m = _CREATE_COMPANY_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().strip("\"'").rstrip(".!?").strip(":-")
    name = re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ]+$", "", name).strip()
    lang = _detect_lang(text)
    if not name or not re.search(r"\w", name):
        return IntentResult.ok(
            "Preciso do nome da empresa. Ex.: \"nova empresa: Acme Corp\"." if lang == "pt"
            else "I need a name. Ex.: \"new company: Acme Corp\".",
            intent="create_company", confidence=0.6,
        )
    obj = Company(workspace_id=ctx.workspace_id, name=name)
    obj = crud.create_scoped(ctx.session, obj)
    reply = (f"✅ Empresa criada: {name}" if lang == "pt"
             else f"✅ Company created: {name}")
    return IntentResult.ok(
        reply, intent="create_company", confidence=0.94,
        tool_calls=[{"name": "create_company", "input": {"name": name}, "result": {"id": str(obj.id)}}],
    )


def _handle_create_opportunity(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    from sqlmodel import select
    from app.models import Opportunity, Pipeline, PipelineStage
    from app.services import crud
    m = _CREATE_OPPORTUNITY_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    raw = m.group("name").strip().strip("\"'").rstrip(".!?").strip(":-")
    raw = re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ]+$", "", raw).strip()
    lang = _detect_lang(text)
    if not raw or not re.search(r"\w", raw):
        return IntentResult.ok(
            "Preciso do nome da oportunidade. Ex.: \"nova oportunidade: Big Deal 50k\"." if lang == "pt"
            else "I need an opportunity name. Ex.: \"new opportunity: Big Deal 50k\".",
            intent="create_opportunity", confidence=0.6,
        )
    # Default pipeline + first stage are required by schema (auto-creates if missing)
    from app.services import pipeline_service
    pipeline = pipeline_service.get_default_pipeline(ctx.session, ctx.workspace_id)
    first_stage = ctx.session.exec(
        select(PipelineStage).where(
            PipelineStage.pipeline_id == pipeline.id,
            PipelineStage.deleted_at.is_(None),
        ).order_by(PipelineStage.order_index)
    ).first()
    amount, name = _parse_amount_hint(raw)
    obj = Opportunity(
        workspace_id=ctx.workspace_id, name=name, amount=amount or 0.0,
        pipeline_id=pipeline.id,
        stage_id=first_stage.id if first_stage else None,
    )
    obj = crud.create_scoped(ctx.session, obj)
    amt_str = f" — {_fmt_money(amount, obj.currency)}" if amount else ""
    tone = (snap.preferences or {}).get("tone", "formal")
    if tone in ("casual", "formal") and not amount:
        nudge = (f"\n💡 Defina valor com: `amount da opp {name} = 50000`" if lang == "pt"
                 else f"\n💡 Set amount with: `amount of opp {name} = 50000`")
    elif tone in ("casual", "formal") and (obj.probability or 0) == 0:
        nudge = (f"\n💡 Ajuste probabilidade com: `probabilidade de {name} para 60`" if lang == "pt"
                 else f"\n💡 Set probability with: `probability of {name} to 60`")
    else:
        nudge = ""
    reply = (f"✅ Oportunidade criada: {name}{amt_str}{nudge}" if lang == "pt"
             else f"✅ Opportunity created: {name}{amt_str}{nudge}")
    return IntentResult.ok(
        reply, intent="create_opportunity", confidence=0.94,
        tool_calls=[{"name": "create_opportunity",
                     "input": {"name": name, "amount": amount},
                     "result": {"id": str(obj.id)}}],
    )


def _handle_current_date_time(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Answer 'what day is today', 'what time is it', 'que dia é hoje/amanhã'."""
    from datetime import datetime, timedelta
    lang = _detect_lang(text)
    lower = _normalize(text)
    now = datetime.now()
    target = now
    if "amanha" in lower or "tomorrow" in lower:
        target = now + timedelta(days=1)
        label = "amanhã" if lang == "pt" else "tomorrow"
    elif "ontem" in lower or "yesterday" in lower:
        target = now - timedelta(days=1)
        label = "ontem" if lang == "pt" else "yesterday"
    else:
        label = "hoje" if lang == "pt" else "today"
    if "hora" in lower or "time" in lower:
        # time query
        if lang == "pt":
            body = f"🕒 São {target.strftime('%H:%M')} de {target.strftime('%A, %d/%m/%Y')}"
        else:
            body = f"🕒 It's {target.strftime('%H:%M')} on {target.strftime('%A, %B %d, %Y')}"
    else:
        # date query
        weekdays_pt = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                       "sexta-feira", "sábado", "domingo"]
        if lang == "pt":
            body = f"📅 {label.capitalize()} é {weekdays_pt[target.weekday()]}, {target.strftime('%d/%m/%Y')}"
        else:
            body = f"📅 {label.capitalize()} is {target.strftime('%A, %B %d, %Y')}"
    return IntentResult.ok(body, intent="current_date_time", confidence=0.95)


_MARK_DONE_RE = re.compile(
    r"(?:mark|complete|finish|conclu(?:ir|a|iu|i|ida?)|marcar|marque|encerrar)\s+"
    r"(?:the\s+|a\s+|o\s+|como\s+feito\s+|as\s+done\s+)?"
    r"(?:task|tarefa)?\s*[:\-]?\s*"
    r"(?P<query>.+?)"
    r"(?:\s+(?:as\s+)?done|\s+como\s+(?:conclu[íi]da|feita|feito))?\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_mark_task_done(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _MARK_DONE_RE.search(text)
    if not m:
        return IntentResult(handled=False)
    query = (m.group("query") or "").strip().rstrip("?.").strip()
    if not query:
        return IntentResult(handled=False)
    reg = default_registry()
    result = reg.call("mark_task_done", ctx, {"query": query})
    lang = _detect_lang(text)
    if result.get("error") == "task_not_found":
        return IntentResult.ok(
            f"Não encontrei tarefa com '{query}'." if lang == "pt" else f"No matching open task found for '{query}'.",
            intent="mark_task_done",
            confidence=0.7,
        )
    if "error" in result:
        return IntentResult.ok(
            f"Erro ao concluir: {result['error']}" if lang == "pt" else f"Couldn't complete: {result['error']}",
            intent="mark_task_done",
            confidence=0.5,
        )
    reply = (
        f"Tarefa concluída: \"{result['title']}\"."
        if lang == "pt"
        else f"Task marked done: \"{result['title']}\"."
    )
    return IntentResult.ok(
        reply,
        intent="mark_task_done",
        tool_calls=[{"name": "mark_task_done", "input": {"query": query}, "result": result}],
        confidence=0.9,
    )


_FIND_COMPANY_INTENT_RE = re.compile(
    r"(?:buscar|busque|busca|find|search|encontr(?:e|ar)|localiz(?:e|ar)|procur(?:e|ar|a)|ache)\s+(?:a\s+|the\s+)?(?:empresa|company)\s+(?P<q>.+)",
    re.IGNORECASE,
)


def _handle_find_company(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _FIND_COMPANY_INTENT_RE.search(text)
    if not m:
        return IntentResult(handled=False)
    query = m.group("q").strip().rstrip("?.").strip()
    reg = default_registry()
    result = reg.call("search_companies", ctx, {"query": query, "limit": 5})
    rows = result.get("results", [])
    lang = _detect_lang(text)
    if not rows:
        return IntentResult.ok(
            f"Nenhuma empresa encontrada para '{query}'." if lang == "pt" else f"No companies found for '{query}'.",
            intent="find_company",
        )
    header = f"Empresas que combinam com '{query}':" if lang == "pt" else f"Companies matching '{query}':"
    lines = [header]
    for c in rows:
        details = " · ".join(v for v in [c.get("domain"), c.get("industry")] if v)
        lines.append(f"  • {c['name']}{(' — ' + details) if details else ''}")
    return IntentResult.ok(
        "\n".join(lines),
        intent="find_company",
        tool_calls=[{"name": "search_companies", "input": {"query": query, "limit": 5}, "result": result}],
        confidence=0.9,
    )


_MOVE_STAGE_RE = re.compile(
    r"(?:move|mover|advance|avan(?:ç|c)ar|change|mudar|mark)\s+(?:the\s+|a\s+)?(?:opportunity|oportunidade|deal|neg[óo]cio)\s+(?P<opp>.+?)\s+(?:to|para|as|como)\s+(?P<stage>.+)",
    re.IGNORECASE,
)


def _handle_move_stage(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _MOVE_STAGE_RE.search(text)
    if not m:
        return IntentResult(handled=False)
    opp_q = m.group("opp").strip().strip("\"'")
    stage = m.group("stage").strip().rstrip(".?!").strip("\"'")
    reg = default_registry()
    result = reg.call("move_opportunity_stage", ctx, {"opportunity_query": opp_q, "stage": stage})
    lang = _detect_lang(text)
    if result.get("error") == "opportunity_not_found":
        return IntentResult.ok(
            f"Não encontrei oportunidade com '{opp_q}'." if lang == "pt" else f"No opportunity found matching '{opp_q}'.",
            intent="move_opportunity_stage",
            confidence=0.7,
        )
    if result.get("error") == "stage_not_found":
        available = ", ".join(result.get("available", []))
        return IntentResult.ok(
            f"Estágio '{stage}' não existe. Disponíveis: {available}."
            if lang == "pt"
            else f"Stage '{stage}' doesn't exist. Available: {available}.",
            intent="move_opportunity_stage",
            confidence=0.7,
        )
    if "error" in result:
        return IntentResult.ok(
            f"Erro: {result['error']}" if lang == "pt" else f"Error: {result['error']}",
            intent="move_opportunity_stage",
            confidence=0.5,
        )
    reply = (
        f"Movido: \"{result['name']}\" → {result['stage']} (status: {result['status']})."
        if lang == "pt"
        else f"Moved: \"{result['name']}\" → {result['stage']} (status: {result['status']})."
    )
    return IntentResult.ok(
        reply,
        intent="move_opportunity_stage",
        tool_calls=[{"name": "move_opportunity_stage", "input": {"opportunity_query": opp_q, "stage": stage}, "result": result}],
        confidence=0.95,
    )


def _handle_activity_timeline(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    reg = default_registry()
    result = reg.call("list_recent_activity", ctx, {"limit": 10})
    rows = result.get("results", [])
    lang = _detect_lang(text)
    if not rows:
        return IntentResult.ok(
            "Nenhuma atividade recente registrada." if lang == "pt" else "No recent activity recorded yet.",
            intent="activity_timeline",
        )
    header = "Atividade recente:" if lang == "pt" else "Recent activity:"
    lines = [header]
    for a in rows:
        lines.append(f"  • [{a['occurred_at']}] {a['kind']} · {a['subject_type']} — {a.get('summary') or a['subject_id']}")
    return IntentResult.ok(
        "\n".join(lines),
        intent="activity_timeline",
        tool_calls=[{"name": "list_recent_activity", "input": {"limit": 10}, "result": result}],
        confidence=0.9,
    )


def _handle_today(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    reg = default_registry()
    result = reg.call("today_summary", ctx, {})
    lang = _detect_lang(text)
    empty = (
        not result.get("tasks_due_today")
        and not result.get("meetings_today")
        and result.get("overdue_task_count", 0) == 0
    )
    if empty:
        return IntentResult.ok(
            "Nada agendado para hoje e nenhuma tarefa vencida. 👌"
            if lang == "pt"
            else "Nothing scheduled today and no overdue tasks. 👌",
            intent="today_summary",
        )
    header = "Hoje:" if lang == "pt" else "Today:"
    lines = [header]
    if result.get("meetings_today"):
        sub = "Reuniões:" if lang == "pt" else "Meetings:"
        lines.append(f"  {sub}")
        for m in result["meetings_today"]:
            lines.append(f"    • {m['title']} @ {m['starts_at']}")
    if result.get("tasks_due_today"):
        sub = "Tarefas para hoje:" if lang == "pt" else "Tasks due today:"
        lines.append(f"  {sub}")
        for t in result["tasks_due_today"]:
            lines.append(f"    • {t['title']}")
    if result.get("overdue_task_count", 0) > 0:
        sub = f"Vencidas: {result['overdue_task_count']}" if lang == "pt" else f"Overdue: {result['overdue_task_count']}"
        lines.append(f"  {sub}")
        for t in result.get("overdue_tasks", [])[:5]:
            lines.append(f"    • {t['title']} (venceu {t['due_at']})" if lang == "pt" else f"    • {t['title']} (was due {t['due_at']})")
    return IntentResult.ok(
        "\n".join(lines),
        intent="today_summary",
        tool_calls=[{"name": "today_summary", "input": {}, "result": result}],
        confidence=0.95,
    )


# ---- Memory / preferences --------------------------------------------------

_REMEMBER_RE = re.compile(
    r"(?:remember|lembre(?:-se)?|guarde)\s*[:\-]?\s*(?P<fact>.+)",
    re.IGNORECASE,
)
_CALL_ME_RE = re.compile(
    r"(?:call\s+me|me\s+chame|pode\s+me\s+chamar\s+de)\s+(?P<name>[^\.\?!]+)",
    re.IGNORECASE,
)
_PREFER_LANG_RE = re.compile(
    r"\b(?:prefer(?:o|ir)?|fale?\s+comigo\s+em|responda\s+em)\s+(?P<lang>portugu[êe]s|ingl[êe]s|english|portuguese|pt(?:-?br)?|en(?:-us)?)\b",
    re.IGNORECASE,
)
_SET_TONE_RE = re.compile(
    r"\b(?:seja\s+(?:mais\s+)?|be\s+(?:more\s+)?|modo\s+|mode\s+|estilo\s+|style\s+|tom\s+|tone\s+)"
    r"(?P<tone>formal|casual|t[eé]cnic[oa]|technical|amig[áa]vel|friendly|neutro|neutral|conciso|concise|verbose|prolix[oa])"
    r"\b",
    re.IGNORECASE,
)


def _persist_pref(ctx: ToolContext, key: str, value: str, kind: str = "preference") -> dict[str, Any]:
    reg = default_registry()
    return reg.call("save_preference", ctx, {"key": key, "value": value, "kind": kind})


def _handle_remember(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    lang = _detect_lang(text)

    # Tone preference — persists per user via JarvisMemory (key='tone')
    m = _SET_TONE_RE.search(text)
    if m:
        raw = m.group("tone").lower()
        tone_map = {
            "formal": "formal", "casual": "casual", "friendly": "casual", "amigável": "casual", "amigavel": "casual",
            "técnico": "technical", "tecnico": "technical", "technical": "technical",
            "neutral": "neutral", "neutro": "neutral",
            "concise": "concise", "conciso": "concise",
            "verbose": "verbose", "prolixo": "verbose", "prolixa": "verbose",
        }
        tone = tone_map.get(raw, "formal")
        result = _persist_pref(ctx, "tone", tone, kind="style")
        labels_pt = {"formal": "formal", "casual": "casual", "technical": "técnico", "neutral": "neutro", "concise": "conciso", "verbose": "prolixo"}
        labels_en = {"formal": "formal", "casual": "casual", "technical": "technical", "neutral": "neutral", "concise": "concise", "verbose": "verbose"}
        label = labels_pt.get(tone, tone) if lang == "pt" else labels_en.get(tone, tone)
        reply = (
            f"Tom ajustado para {label}. Ao dispor."
            if lang == "pt"
            else f"Tone set to {label}. At your service."
        )
        return IntentResult.ok(
            reply,
            intent="set_tone",
            tool_calls=[{"name": "save_preference", "input": {"key": "tone", "value": tone}, "result": result}],
            confidence=0.95,
        )

    # Language preference
    m = _PREFER_LANG_RE.search(text)
    if m:
        raw = m.group("lang").lower()
        code = "pt" if raw.startswith(("port", "pt")) else "en"
        result = _persist_pref(ctx, "language", code)
        reply = (
            f"Combinado — vou responder em português a partir de agora."
            if code == "pt"
            else f"Got it — I'll reply in English from now on."
        )
        return IntentResult.ok(
            reply,
            intent="remember_language",
            tool_calls=[{"name": "save_preference", "input": {"key": "language", "value": code}, "result": result}],
            confidence=0.95,
        )

    # "Call me by <name>"
    m = _CALL_ME_RE.search(text)
    if m:
        name = m.group("name").strip().rstrip(",.")
        result = _persist_pref(ctx, "preferred_name", name)
        reply = (
            f"Perfeito, {name}. Vou te chamar assim daqui em diante."
            if lang == "pt"
            else f"Nice to meet you, {name}. I'll call you that from now on."
        )
        return IntentResult.ok(
            reply,
            intent="remember_name",
            tool_calls=[{"name": "save_preference", "input": {"key": "preferred_name", "value": name}, "result": result}],
            confidence=0.95,
        )

    # Generic "remember: <fact>"
    m = _REMEMBER_RE.search(text)
    if m:
        fact = m.group("fact").strip().rstrip(".")
        if not fact:
            return IntentResult(handled=False)
        # Split "key = value" or "key: value" if present, otherwise store under freeform note.
        key_val = re.match(r"^\s*(?P<k>[\w\s]{1,40}?)\s*[:=]\s*(?P<v>.+)$", fact)
        if key_val:
            key = key_val.group("k").strip().lower().replace(" ", "_")
            value = key_val.group("v").strip()
        else:
            key = f"note_{int(datetime.now(timezone.utc).timestamp())}"
            value = fact
        result = _persist_pref(ctx, key, value, kind="fact")
        reply = (
            f"Guardado: {key} = {value}." if lang == "pt" else f"Remembered: {key} = {value}."
        )
        return IntentResult.ok(
            reply,
            intent="remember_fact",
            tool_calls=[{"name": "save_preference", "input": {"key": key, "value": value, "kind": "fact"}, "result": result}],
            confidence=0.9,
        )

    return IntentResult(handled=False)


def _handle_list_preferences(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    reg = default_registry()
    result = reg.call("list_preferences", ctx, {})
    rows = result.get("results", [])
    lang = _detect_lang(text)
    if not rows:
        return IntentResult.ok(
            "Nada guardado ainda. Diga \"lembre: X\" para começar." if lang == "pt" else "Nothing stored yet. Say \"remember: X\" to start.",
            intent="list_preferences",
        )
    header = "O que eu me lembro sobre você:" if lang == "pt" else "What I remember about you:"
    lines = [header]
    for r in rows:
        lines.append(f"  • {r['key']} = {r['value']} ({r['kind']})")
    return IntentResult.ok(
        "\n".join(lines),
        intent="list_preferences",
        tool_calls=[{"name": "list_preferences", "input": {}, "result": result}],
        confidence=0.95,
    )


# ---- Log call/email --------------------------------------------------------

_LOG_INTERACTION_RE = re.compile(
    r"(?:log|register|registrar|anotar)\s+(?:a\s+|uma\s+)?(?P<kind>call|ligac?[aã]o|ligacao|liga(?:ç|c)[ãa]o|email|e-mail|sms|whatsapp|zap|chat|conversa)"
    r"(?:\s+(?:with|com|para|to)\s+(?P<who>[^:]+?))?(?:\s*[:\-]\s*(?P<summary>.+))?$",
    re.IGNORECASE,
)


def _handle_log_interaction(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _LOG_INTERACTION_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    raw_kind = m.group("kind").lower()
    kind_map = {
        "call": "call", "ligacao": "call", "ligação": "call", "ligaçao": "call", "ligacão": "call",
        "email": "email", "e-mail": "email",
        "sms": "sms",
        "whatsapp": "whatsapp", "zap": "whatsapp",
        "chat": "chat", "conversa": "chat",
    }
    kind = kind_map.get(raw_kind, "call")
    who = (m.group("who") or "").strip()
    summary = (m.group("summary") or "").strip()

    args: dict[str, Any] = {"kind": kind}
    if who:
        args["contact_query"] = who
    if summary:
        args["summary"] = summary

    reg = default_registry()
    result = reg.call("log_interaction", ctx, args)
    lang = _detect_lang(text)
    if result.get("error") == "contact_not_found":
        return IntentResult.ok(
            f"Não achei um contato para '{who}'." if lang == "pt" else f"No contact found matching '{who}'.",
            intent="log_interaction",
            confidence=0.7,
        )
    if "error" in result:
        return IntentResult.ok(
            f"Erro: {result['error']}" if lang == "pt" else f"Error: {result['error']}",
            intent="log_interaction",
            confidence=0.5,
        )
    label = {"call": "ligação", "email": "e-mail", "sms": "SMS", "whatsapp": "WhatsApp", "chat": "conversa"}.get(kind, kind) if lang == "pt" else kind
    reply = (
        f"{label.capitalize()} registrada."
        if lang == "pt"
        else f"{label.capitalize()} logged."
    )
    if summary:
        reply += f" ({summary})"
    return IntentResult.ok(
        reply,
        intent="log_interaction",
        tool_calls=[{"name": "log_interaction", "input": args, "result": result}],
        confidence=0.9,
    )


# ---- Reschedule meeting ----------------------------------------------------

_RESCHEDULE_RE = re.compile(
    r"(?:reschedule|move|remarcar|reagendar|mover)\s+(?:the\s+|a\s+)?(?:meeting|reuni[ãa]o)?\s*(?P<title>.*?)\s+(?:to|para|for)\s+(?P<when>.+)$",
    re.IGNORECASE,
)


def _handle_reschedule_meeting(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _RESCHEDULE_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    title = m.group("title").strip().strip("\"'").rstrip(".:")
    when_text = m.group("when").strip().rstrip(".?!")
    if not title:
        return IntentResult(handled=False)

    new_start = parse_when(when_text)
    lang = _detect_lang(text)
    if new_start is None:
        return IntentResult.ok(
            f"Não consegui entender a data '{when_text}'." if lang == "pt" else f"Couldn't parse when: '{when_text}'.",
            intent="reschedule_meeting",
            confidence=0.6,
        )
    reg = default_registry()
    result = reg.call("reschedule_meeting", ctx, {"query": title, "starts_at": new_start.isoformat()})
    if result.get("error") == "meeting_not_found":
        return IntentResult.ok(
            f"Não encontrei reunião com '{title}'." if lang == "pt" else f"No meeting matching '{title}'.",
            intent="reschedule_meeting",
            confidence=0.7,
        )
    if "error" in result:
        return IntentResult.ok(
            f"Erro: {result['error']}" if lang == "pt" else f"Error: {result['error']}",
            intent="reschedule_meeting",
            confidence=0.5,
        )
    reply = (
        f"Reunião \"{result['title']}\" remarcada para {result['starts_at']}."
        if lang == "pt"
        else f"Meeting \"{result['title']}\" moved to {result['starts_at']}."
    )
    return IntentResult.ok(
        reply,
        intent="reschedule_meeting",
        tool_calls=[{"name": "reschedule_meeting", "input": {"query": title, "starts_at": new_start.isoformat()}, "result": result}],
        confidence=0.95,
    )


# ---- Forecast --------------------------------------------------------------

def _handle_forecast(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    reg = default_registry()
    result = reg.call("forecast", ctx, {})
    lang = _detect_lang(text)
    labels_en = {
        "overdue": "Overdue", "this_week": "This week", "this_month": "This month",
        "next_month": "Next month", "later": "Later", "no_date": "No close date",
    }
    labels_pt = {
        "overdue": "Vencidas", "this_week": "Esta semana", "this_month": "Este mês",
        "next_month": "Próximo mês", "later": "Depois", "no_date": "Sem data",
    }
    labels = labels_pt if lang == "pt" else labels_en
    header = "Previsão do pipeline aberto:" if lang == "pt" else "Open pipeline forecast:"
    lines = [header]
    for key in ("overdue", "this_week", "this_month", "next_month", "later", "no_date"):
        b = result["buckets"][key]
        if b["count"] == 0:
            continue
        lines.append(f"  • {labels[key]}: {int(b['count'])} deals · total {b['amount']:,.2f} · weighted {b['weighted']:,.2f}")
    totals = result["totals"]
    suffix = "Total ponderado:" if lang == "pt" else "Weighted total:"
    lines.append(f"{suffix} {totals['weighted']:,.2f} across {int(totals['count'])} open deals.")
    return IntentResult.ok(
        "\n".join(lines),
        intent="forecast",
        tool_calls=[{"name": "forecast", "input": {}, "result": result}],
        confidence=0.95,
    )


# ---- Week summary ----------------------------------------------------------

def _handle_week_summary(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    reg = default_registry()
    result = reg.call("week_summary", ctx, {})
    lang = _detect_lang(text)
    opps = result.get("opportunities_closing", [])
    tasks = result.get("tasks_due", [])
    meets = result.get("meetings", [])
    if not opps and not tasks and not meets:
        return IntentResult.ok(
            "Semana tranquila — nada agendado por aqui." if lang == "pt" else "Quiet week — nothing scheduled.",
            intent="week_summary",
        )
    header = "Esta semana:" if lang == "pt" else "This week:"
    lines = [header]
    if opps:
        sub = "Oportunidades fechando:" if lang == "pt" else "Opportunities closing:"
        lines.append(f"  {sub}")
        for o in opps:
            lines.append(f"    • {o['name']} — {o['currency']} {o['amount']:,.2f} (esperado {o['expected_close_date']})")
        lines.append(
            f"  {'Pipeline ponderado' if lang == 'pt' else 'Weighted pipeline'}: {result.get('weighted_pipeline', 0):,.2f}"
        )
    if tasks:
        sub = "Tarefas vencendo:" if lang == "pt" else "Tasks due:"
        lines.append(f"  {sub}")
        for t in tasks[:10]:
            lines.append(f"    • {t['title']} ({t['due_at']})")
    if meets:
        sub = "Reuniões agendadas:" if lang == "pt" else "Meetings scheduled:"
        lines.append(f"  {sub}")
        for m in meets:
            lines.append(f"    • {m['title']} @ {m['starts_at']}")
    return IntentResult.ok(
        "\n".join(lines),
        intent="week_summary",
        tool_calls=[{"name": "week_summary", "input": {}, "result": result}],
        confidence=0.95,
    )


# ---- Tag entity ------------------------------------------------------------

_TAG_ENTITY_RE = re.compile(
    r"(?:tag|marcar|marque|etiquetar)\s+(?:the\s+|o\s+|a\s+)?"
    r"(?P<kind>contact|company|lead|opportunity|contato|empresa|oportunidade)?\s*"
    r"(?P<who>.+?)\s+(?:as|como)\s+(?P<tag>.+)",
    re.IGNORECASE,
)

_KIND_MAP = {
    "contact": "contact", "contato": "contact",
    "company": "company", "empresa": "company",
    "lead": "lead",
    "opportunity": "opportunity", "oportunidade": "opportunity",
}


def _handle_tag_entity(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _TAG_ENTITY_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    who = m.group("who").strip().strip("\"'")
    tag_name = m.group("tag").strip().rstrip(".!?").strip("\"'")
    raw_kind = (m.group("kind") or "").strip().lower()
    kind = _KIND_MAP.get(raw_kind, "contact")  # default to contact — most common
    if not who or not tag_name:
        return IntentResult(handled=False)
    reg = default_registry()
    result = reg.call("tag_entity", ctx, {"tag": tag_name, "subject_type": kind, "query": who})
    lang = _detect_lang(text)
    if result.get("error") == "subject_not_found":
        return IntentResult.ok(
            f"Não encontrei {kind} com '{who}'." if lang == "pt" else f"No {kind} matching '{who}'.",
            intent="tag_entity",
            confidence=0.7,
        )
    if "error" in result:
        return IntentResult.ok(
            f"Erro: {result['error']}" if lang == "pt" else f"Error: {result['error']}",
            intent="tag_entity",
            confidence=0.5,
        )
    verb = "já estava marcado" if lang == "pt" and result.get("already_linked") else \
           "already tagged" if result.get("already_linked") else \
           "marcado" if lang == "pt" else "tagged"
    reply = (
        f"{who} {verb} como \"{tag_name}\"."
        if lang == "pt"
        else f"{who} {verb} as \"{tag_name}\"."
    )
    return IntentResult.ok(
        reply,
        intent="tag_entity",
        tool_calls=[{"name": "tag_entity", "input": {"tag": tag_name, "subject_type": kind, "query": who}, "result": result}],
        confidence=0.9,
    )


# ---- Lead scoring ----------------------------------------------------------

def _handle_recalculate_scores(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    reg = default_registry()
    result = reg.call("recalculate_lead_scores", ctx, {"reset_to_zero": True})
    lang = _detect_lang(text)
    if "error" in result:
        return IntentResult.ok(
            f"Erro: {result['error']}" if lang == "pt" else f"Error: {result['error']}",
            intent="recalculate_lead_scores",
            confidence=0.5,
        )
    if lang == "pt":
        reply = (
            f"Recalculei os leads. Regras ativas: {result['rules_active']}. "
            f"Leads verificados: {result['leads_scanned']}. "
            f"Atualizados: {result['leads_updated']}."
        )
    else:
        reply = (
            f"Recomputed lead scores. Active rules: {result['rules_active']}. "
            f"Leads scanned: {result['leads_scanned']}. Updated: {result['leads_updated']}."
        )
    return IntentResult.ok(
        reply,
        intent="recalculate_lead_scores",
        tool_calls=[{"name": "recalculate_lead_scores", "input": {"reset_to_zero": True}, "result": result}],
        confidence=0.95,
    )


# ---- Search everywhere -----------------------------------------------------

_SEARCH_EVERYWHERE_RE = re.compile(
    r"(?:search|find|look\s+up|busca(?:r|s|m)?|busque|localiz(?:e|ar)|encontr(?:e|ar)|procur(?:e|ar|a|o)|ache|acha|acho|onde\s+(?:est[áa]|fica|encontro)|"
    r"quem\s+(?:é|eh|e)|who\s+is|"
    r"(?:me\s+fale|me\s+conte|me\s+diga|diga|conte|fale|tell\s+me)\s+(?:sobre|de|da|do|about))\s+"
    r"(?:for\s+|por\s+|a\s+|o\s+)?"
    r"(?:everywhere\s+for\s+|anywhere\s+for\s+|em\s+tudo\s+por\s+|em\s+tudo\s+)?"
    r"(?P<q>.+)",
    re.IGNORECASE,
)


def _handle_search_everywhere(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _SEARCH_EVERYWHERE_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    query = m.group("q").strip().rstrip("?.").strip("\"'")
    if len(query) < 2:
        return IntentResult(handled=False)
    reg = default_registry()
    result = reg.call("search_everywhere", ctx, {"query": query})
    lang = _detect_lang(text)
    total = result.get("total", 0)
    if total == 0:
        return IntentResult.ok(
            f"Nada encontrado para '{query}'." if lang == "pt" else f"Nothing matched '{query}'.",
            intent="search_everywhere",
            confidence=0.85,
        )
    header = f"Resultados para '{query}':" if lang == "pt" else f"Results for '{query}':"
    lines = [header]
    labels_pt = {"contacts": "Contatos", "companies": "Empresas", "leads": "Leads", "opportunities": "Oportunidades", "notes": "Notas"}
    labels_en = {"contacts": "Contacts", "companies": "Companies", "leads": "Leads", "opportunities": "Opportunities", "notes": "Notes"}
    labels = labels_pt if lang == "pt" else labels_en
    for kind in ("contacts", "companies", "leads", "opportunities", "notes"):
        rows = result["results"].get(kind, [])
        if not rows:
            continue
        lines.append(f"  {labels[kind]}:")
        for r in rows:
            if kind == "contacts":
                sfx = f" — {r['job_title']}" if r.get("job_title") else ""
                lines.append(f"    • {r['name']}{sfx}")
            elif kind == "companies":
                sfx = f" · {r['domain']}" if r.get("domain") else ""
                lines.append(f"    • {r['name']}{sfx}")
            elif kind == "leads":
                sfx = f" ({r['status']})" if r.get("status") else ""
                lines.append(f"    • {r['name']}{sfx}")
            elif kind == "opportunities":
                lines.append(f"    • {r['name']} — {r['currency']} {r['amount']:,.2f} ({r['status']})")
            elif kind == "notes":
                lines.append(f"    • {r['body_preview']}")
    return IntentResult.ok(
        "\n".join(lines),
        intent="search_everywhere",
        tool_calls=[{"name": "search_everywhere", "input": {"query": query}, "result": result}],
        confidence=0.9,
    )


# ---- Contacts at a company -------------------------------------------------

_CONTACTS_AT_COMPANY_RE = re.compile(
    r"(?:who\s+(?:works?|is)\s+at|contacts?\s+at|contatos?\s+(?:d[ea]|em|na|no)|quem\s+trabalha\s+(?:em|n[ao]s?))\s+(?P<q>.+)",
    re.IGNORECASE,
)


def _handle_contacts_at_company(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    m = _CONTACTS_AT_COMPANY_RE.search(text)
    if not m:
        return IntentResult(handled=False)
    query = m.group("q").strip().rstrip("?.").strip("\"'")
    reg = default_registry()
    result = reg.call("list_contacts_by_company", ctx, {"company_query": query})
    lang = _detect_lang(text)
    if result.get("error") == "company_not_found":
        return IntentResult.ok(
            f"Não encontrei a empresa '{query}'." if lang == "pt" else f"No company matching '{query}'.",
            intent="list_contacts_by_company",
            confidence=0.7,
        )
    rows = result.get("results", [])
    if not rows:
        return IntentResult.ok(
            f"Nenhum contato registrado para '{query}'." if lang == "pt" else f"No contacts on file for '{query}'.",
            intent="list_contacts_by_company",
        )
    header = f"Contatos em {query}:" if lang == "pt" else f"Contacts at {query}:"
    lines = [header]
    for c in rows:
        det = " · ".join(v for v in [c.get("job_title"), c.get("email")] if v)
        lines.append(f"  • {c['name']}{(' — ' + det) if det else ''}")
    return IntentResult.ok(
        "\n".join(lines),
        intent="list_contacts_by_company",
        tool_calls=[
            {"name": "list_contacts_by_company", "input": {"company_query": query}, "result": result},
            {"name": "recent_list", "kind": "contact",
             "items": [{"id": str(c.get("id")), "name": c.get("name")} for c in rows]},
        ],
        confidence=0.9,
    )


# ---- Extra intents added for VisiQuost v1.0 -------------------------------

def _handle_how_are_you(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """JARVIS: crisp status, no small-talk sugar."""
    lang = _detect_lang(text)
    if lang == "pt":
        reply = "Todos os sistemas nominais. Rodando localmente na sua máquina. Aguardo instruções."
    else:
        reply = "All systems nominal. Running locally on your machine. Awaiting instructions."
    return IntentResult.ok(reply, intent="how_are_you", confidence=0.95)


def _handle_who_are_you(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """JARVIS: introduce as a proactive local assistant with dry professionalism."""
    lang = _detect_lang(text)
    if lang == "pt":
        reply = (
            "Jarvis. Assistente do VisiQuost, operando integralmente na sua máquina — "
            "nenhum dado sai daqui.\n"
            "Planejo, executo e reporto. Diga \"o que voce pode fazer\" para o inventário, "
            "ou \"briefing\" para começar."
        )
    else:
        reply = (
            "Jarvis. VisiQuost assistant, running entirely on your machine — "
            "nothing leaves this box.\n"
            "I plan, execute, and report. Say \"what can you do\" for the inventory, "
            "or \"briefing\" to begin."
        )
    return IntentResult.ok(reply, intent="who_are_you", confidence=0.98)


def _handle_capabilities(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """What can you do — richer than help."""
    lang = _detect_lang(text)
    if lang == "pt":
        reply = (
            "📋 O que eu posso fazer:\n\n"
            "**Consulta rápida**\n"
            "  • \"pipeline\" — resumo de oportunidades\n"
            "  • \"tarefas atrasadas\", \"próximas reuniões\"\n"
            "  • \"top 5 oportunidades\", \"leads parados\"\n\n"
            "**Ação**\n"
            "  • \"crie tarefa: X\", \"agende reunião com Y para amanhã 15h\"\n"
            "  • \"marque a oportunidade Z como won\"\n"
            "  • \"apague o contato W\"\n\n"
            "**Contexto do dia**\n"
            "  • \"briefing\" ou \"meu dia\"\n"
            "  • \"quem devo ligar hoje\"\n"
            "  • \"ajude a focar\" (3 ações prioritárias)\n\n"
            "**Local (arquivos)**\n"
            "  • \"meus arquivos\", \"leia arquivo X\"\n"
            "  • \"importe contatos\" (de .csv/.vcf na pasta)\n"
            "  • \"minha agenda\" (de .ics na pasta)"
        )
    else:
        reply = (
            "📋 What I can do:\n\n"
            "**Quick lookups**\n"
            "  • \"pipeline\" — open opps summary\n"
            "  • \"overdue tasks\", \"upcoming meetings\"\n"
            "  • \"top 5 opportunities\", \"stale leads\"\n\n"
            "**Actions**\n"
            "  • \"create task: X\", \"schedule meeting with Y for tomorrow 3pm\"\n"
            "  • \"mark opportunity Z as won\"\n"
            "  • \"delete contact W\"\n\n"
            "**Day context**\n"
            "  • \"briefing\" or \"what's my day\"\n"
            "  • \"who should I call today\"\n"
            "  • \"help me focus\" (3 priorities)\n\n"
            "**Local (files)**\n"
            "  • \"my files\", \"read file X\"\n"
            "  • \"import contacts\" (from .csv/.vcf in the folder)\n"
            "  • \"my calendar\" (from .ics in the folder)"
        )
    return IntentResult.ok(reply, intent="capabilities", confidence=0.95)


def _handle_thanks(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """JARVIS: acknowledge without effusion."""
    lang = _detect_lang(text)
    reply = "Ao dispor." if lang == "pt" else "At your service."
    return IntentResult.ok(reply, intent="thanks", confidence=0.95)


def _handle_goodbye(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """JARVIS: standby posture, ready when called."""
    lang = _detect_lang(text)
    reply = "Até logo. Em standby quando precisar." if lang == "pt" else "Until later. Standing by."
    return IntentResult.ok(reply, intent="goodbye", confidence=0.95)


def _handle_top_opportunities(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Top N opportunities by weighted amount (open only)."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    m = re.search(r"\btop\s+(\d+)", text, re.IGNORECASE) or re.search(r"\bmaiores?\s+(\d+)", text, re.IGNORECASE)
    n = min(int(m.group(1)) if m else 5, 25)
    stmt = select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
    )
    opps = list(ctx.session.exec(stmt).all())
    opps.sort(key=lambda o: (o.amount or 0) * ((o.probability or 0) / 100.0), reverse=True)
    picked = opps[:n]
    if not picked:
        reply = "Nenhuma oportunidade aberta ainda." if lang == "pt" else "No open opportunities yet."
        return IntentResult.ok(reply, intent="top_opportunities", confidence=0.9)
    header = f"Top {len(picked)} oportunidades (peso = valor × probabilidade):" if lang == "pt" else f"Top {len(picked)} opportunities (weight = amount × probability):"
    lines = [header]
    for i, o in enumerate(picked, 1):
        w = (o.amount or 0) * ((o.probability or 0) / 100.0)
        lines.append(f"  {i}. {o.name} — {o.currency} {o.amount:,.0f} × {o.probability:.0f}% = {o.currency} {w:,.0f}")
    return IntentResult.ok(
        "\n".join(lines), intent="top_opportunities", confidence=0.92,
        tool_calls=[{
            "name": "recent_list",
            "kind": "opportunity",
            "items": [{"id": str(o.id), "name": o.name} for o in picked],
        }],
    )


def _handle_revenue_by_stage(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Sum open opportunity amount per stage."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus, Pipeline, PipelineStage
    lang = _detect_lang(text)
    stages = list(ctx.session.exec(
        select(PipelineStage).join(Pipeline)
        .where(Pipeline.workspace_id == ctx.workspace_id, Pipeline.deleted_at.is_(None), Pipeline.is_default.is_(True))
        .order_by(PipelineStage.order_index)
    ).all())
    if not stages:
        reply = "Sem pipeline configurado." if lang == "pt" else "No pipeline configured."
        return IntentResult.ok(reply, intent="revenue_by_stage", confidence=0.9)
    stmt = select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
    )
    opps = list(ctx.session.exec(stmt).all())
    by_stage: dict[str, tuple[int, float]] = {s.name: (0, 0.0) for s in stages}
    for o in opps:
        for s in stages:
            if s.id == o.stage_id:
                cnt, amt = by_stage[s.name]
                by_stage[s.name] = (cnt + 1, amt + (o.amount or 0))
                break
    header = "Valor aberto por estágio:" if lang == "pt" else "Open value by stage:"
    lines = [header]
    for s in stages:
        cnt, amt = by_stage[s.name]
        lines.append(f"  • {s.name}: {cnt} × $ {amt:,.0f}")
    return IntentResult.ok("\n".join(lines), intent="revenue_by_stage", confidence=0.92)


def _handle_help_me_focus(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Pick exactly 3 actions for today — quality over quantity."""
    # Reuse the who_to_call_today priority logic and trim to 3
    lang = _detect_lang(text)
    who_result = _handle_who_to_call_today(intent, text, snap, ctx)
    lines_all = who_result.reply.split("\n")
    # Skip header, take first 3 bullets
    picks = [ln for ln in lines_all if ln.strip().startswith("•")][:3]
    if not picks:
        return IntentResult.ok(
            "🎉 Nada urgente. Foco: prospecção e nutrir leads existentes." if lang == "pt"
            else "🎉 Nothing urgent. Focus: prospect and nurture existing leads.",
            intent="help_me_focus", confidence=0.9,
        )
    header = "🎯 Foco de hoje — 3 ações:" if lang == "pt" else "🎯 Today's focus — 3 actions:"
    lines = [header, ""]
    for i, p in enumerate(picks, 1):
        stripped = p.replace("  •", "").strip()
        lines.append(f"  {i}. {stripped}")
    lines.append("")
    lines.append("💡 Termine essas 3 antes de olhar outras coisas." if lang == "pt"
                 else "💡 Finish these 3 before looking at anything else.")
    return IntentResult.ok("\n".join(lines), intent="help_me_focus", confidence=0.94,
        tool_calls=[{"name": "help_me_focus", "result": {"count": len(picks)}}])


def _handle_daily_briefing(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Morning briefing: today's meetings + top 3 priorities + focus for the day."""
    from sqlmodel import select
    from datetime import datetime, timezone, timedelta
    from app.models import Meeting, Task, TaskStatus, Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)
    end_today = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)

    meetings_today = list(ctx.session.exec(select(Meeting).where(
        Meeting.workspace_id == ctx.workspace_id, Meeting.deleted_at.is_(None),
        Meeting.starts_at >= now, Meeting.starts_at < end_today,
    ).order_by(Meeting.starts_at.asc())).all())

    overdue = list(ctx.session.exec(select(Task).where(
        Task.workspace_id == ctx.workspace_id, Task.deleted_at.is_(None),
        Task.status != TaskStatus.done, Task.due_at.is_not(None),
    )).all())
    overdue = [tk for tk in overdue if (tk.due_at if tk.due_at.tzinfo else tk.due_at.replace(tzinfo=timezone.utc)) < now]

    open_opps = list(ctx.session.exec(select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
    )).all())
    weighted_total = sum((o.amount or 0) * ((o.probability or 0) / 100) for o in open_opps)

    if lang == "pt":
        lines = [f"☀️ Bom dia! Aqui está seu briefing ({now.strftime('%d/%m')}):", ""]
    else:
        lines = [f"☀️ Good morning! Your briefing ({now.strftime('%b %d')}):", ""]

    if meetings_today:
        lines.append("📅 Reuniões hoje:" if lang == "pt" else "📅 Meetings today:")
        for m in meetings_today[:5]:
            when = m.starts_at.strftime("%H:%M")
            lines.append(f"  • {when} — {m.title}")
        lines.append("")
    else:
        lines.append("📅 Sem reuniões hoje" if lang == "pt" else "📅 No meetings today")
        lines.append("")

    if overdue:
        lines.append(f"⚠ {len(overdue)} tarefas atrasadas" if lang == "pt" else f"⚠ {len(overdue)} overdue tasks")
    else:
        lines.append("✅ Zero tarefas atrasadas" if lang == "pt" else "✅ Zero overdue tasks")

    lines.append(f"💰 Pipeline ponderado: $ {weighted_total:,.0f}" if lang == "pt" else f"💰 Weighted pipeline: $ {weighted_total:,.0f}")
    lines.append("")
    focus = "Foque em fechar oportunidades acima" if lang == "pt" and open_opps else \
            "Focus on closing open opportunities" if open_opps else \
            "Foque em prospecção e novos leads" if lang == "pt" else \
            "Focus on prospecting and new leads"
    lines.append(f"🎯 {focus}")
    lines.append("")
    lines.append("💡 Peça \"quem devo ligar hoje\" para lista priorizada" if lang == "pt"
                 else "💡 Say \"who should I call today\" for a prioritized list")

    return IntentResult.ok(
        "\n".join(lines), intent="daily_briefing", confidence=0.94,
        tool_calls=[{"name": "daily_briefing", "result": {"meetings": len(meetings_today), "overdue": len(overdue)}}],
    )


def _handle_who_to_call_today(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Priority queue: who should you call/message today?

    Combines: overdue tasks with contact + high-score qualified leads not
    recently contacted + open opps closing this month with no touch >7d.
    """
    from sqlmodel import select
    from datetime import datetime, timezone, timedelta
    from app.models import Task, TaskStatus, TaskPriority, Contact, Lead, LeadStatus, Opportunity, OpportunityStatus, Activity
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)

    priorities: list[tuple[int, str]] = []  # (score, description)

    # 1) Overdue tasks with related contact
    overdue = list(ctx.session.exec(select(Task).where(
        Task.workspace_id == ctx.workspace_id, Task.deleted_at.is_(None),
        Task.status != TaskStatus.done, Task.status != TaskStatus.cancelled,
        Task.due_at.is_not(None),
    )).all())
    for tk in overdue:
        due = tk.due_at if tk.due_at.tzinfo else tk.due_at.replace(tzinfo=timezone.utc)
        if due >= now:
            continue
        days_over = (now - due).days
        prio_boost = {TaskPriority.urgent: 40, TaskPriority.high: 25, TaskPriority.normal: 10, TaskPriority.low: 0}.get(tk.priority, 10)
        score = min(100, prio_boost + days_over * 3)
        who = ""
        if tk.related_contact_id:
            c = ctx.session.exec(select(Contact).where(Contact.id == tk.related_contact_id)).first()
            if c:
                who = f"{c.first_name} {c.last_name or ''}".strip()
        priorities.append((score, f"📞 {tk.title}{' — ' + who if who else ''} ({days_over}d atraso)"))

    # 2) High-score qualified leads with no recent activity
    hot_leads = list(ctx.session.exec(select(Lead).where(
        Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
        Lead.status.in_([LeadStatus.qualified, LeadStatus.contacted, LeadStatus.new]),
        Lead.score >= 50,
    )).all())
    for l in hot_leads:
        last = ctx.session.exec(select(Activity).where(
            Activity.workspace_id == ctx.workspace_id,
            Activity.subject_type == "lead", Activity.subject_id == l.id,
        ).order_by(Activity.occurred_at.desc()).limit(1)).first()
        days_cold = 999 if last is None else (now - (last.occurred_at if last.occurred_at.tzinfo else last.occurred_at.replace(tzinfo=timezone.utc))).days
        if days_cold < 3:
            continue
        score = min(100, l.score + days_cold)
        name = f"{l.first_name} {l.last_name or ''}".strip()
        priorities.append((score, f"🎯 Lead {name} (score {l.score}, sem toque {days_cold}d)"))

    # 3) Open opps closing this month, no recent touch
    this_month = now.replace(day=1)
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    open_opps = list(ctx.session.exec(select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
        Opportunity.expected_close_date.is_not(None),
    )).all())
    for o in open_opps:
        # Normalize expected_close_date to date (handles both date and datetime)
        ecd = o.expected_close_date
        if hasattr(ecd, "date"):  # datetime → date
            ecd = ecd.date()
        if not (this_month.date() <= ecd < next_month.date()):
            continue
        last = ctx.session.exec(select(Activity).where(
            Activity.workspace_id == ctx.workspace_id,
            Activity.subject_type == "opportunity", Activity.subject_id == o.id,
        ).order_by(Activity.occurred_at.desc()).limit(1)).first()
        days_cold = 999 if last is None else (now - (last.occurred_at if last.occurred_at.tzinfo else last.occurred_at.replace(tzinfo=timezone.utc))).days
        if days_cold < 7:
            continue
        weight = int((o.amount or 0) * ((o.probability or 0) / 100.0) / 1000)
        score = min(100, weight + days_cold)
        priorities.append((score, f"💼 Fechando este mês: {o.name} — $ {o.amount or 0:,.0f} ({days_cold}d sem toque)"))

    priorities.sort(key=lambda x: x[0], reverse=True)
    if not priorities:
        return IntentResult.ok(
            "Sem prioridades urgentes. Sugiro nutrir leads existentes." if lang == "pt" else "No urgent priorities. Nurture existing leads.",
            intent="who_to_call_today", confidence=0.9,
        )
    tone = (snap.preferences or {}).get("tone", "formal")
    if tone == "casual":
        header = "📞 Quem eu ligaria hoje:" if lang == "pt" else "📞 Who I'd call today:"
    elif tone == "concise":
        header = "📞 Ligar:" if lang == "pt" else "📞 Call:"
    elif tone == "technical":
        header = "call_queue[prio]:"
    else:
        header = "📞 Lista priorizada de contatos:" if lang == "pt" else "📞 Prioritized call list:"
    lines = [header]
    for score, desc in priorities[:10]:
        lines.append(f"  • {desc}")
    return IntentResult.ok(
        "\n".join(lines), intent="who_to_call_today", confidence=0.94,
        tool_calls=[{"name": "who_to_call_today", "result": {"count": len(priorities)}}],
    )


def _handle_top_companies_by_opps(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Rank companies by number and value of associated opportunities."""
    from sqlmodel import select
    from app.models import Company, Contact, Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    companies = {c.id: c for c in ctx.session.exec(select(Company).where(
        Company.workspace_id == ctx.workspace_id, Company.deleted_at.is_(None),
    )).all()}
    contact_to_co = {c.id: c.company_id for c in ctx.session.exec(select(Contact).where(
        Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
        Contact.company_id.is_not(None),
    )).all()}
    tally: dict = {}
    for o in ctx.session.exec(select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
    )).all():
        co_id = contact_to_co.get(o.contact_id)
        if not co_id or co_id not in companies:
            continue
        entry = tally.setdefault(co_id, {"count": 0, "won": 0, "value": 0.0})
        entry["count"] += 1
        entry["value"] += o.amount or 0
        if o.status == OpportunityStatus.won:
            entry["won"] += 1
    if not tally:
        return IntentResult.ok(
            "Sem oportunidades vinculadas a empresas." if lang == "pt" else "No opportunities linked to companies.",
            intent="top_companies_by_opps", confidence=0.9,
        )
    ranked = sorted(tally.items(), key=lambda x: x[1]["value"], reverse=True)
    header = "🏢 Top empresas por valor de oportunidades:" if lang == "pt" else "🏢 Top companies by opp value:"
    lines = [header]
    for co_id, stats in ranked[:10]:
        co = companies[co_id]
        lines.append(f"  • {co.name} — {stats['count']} opp(s) · ${stats['value']:,.0f} · {stats['won']} won")
    return IntentResult.ok(
        "\n".join(lines), intent="top_companies_by_opps", confidence=0.93,
        tool_calls=[{"name": "top_companies_by_opps", "result": {"count": len(ranked)}}],
    )


def _handle_orphan_contacts(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Contacts with no linked company — auto-enrichment targets."""
    from sqlmodel import select
    from app.models import Contact
    lang = _detect_lang(text)
    orphans = list(ctx.session.exec(select(Contact).where(
        Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
        Contact.company_id.is_(None),
    ).limit(30)).all())
    if not orphans:
        return IntentResult.ok(
            "🎉 Todos os contatos têm empresa vinculada." if lang == "pt" else "🎉 Every contact has a linked company.",
            intent="orphan_contacts", confidence=0.93,
        )
    header = f"👥 {len(orphans)} contato(s) sem empresa:" if lang == "pt" else f"👥 {len(orphans)} contacts without a company:"
    lines = [header]
    for c in orphans[:15]:
        name = f"{c.first_name} {c.last_name or ''}".strip()
        lines.append(f"  • {name}{' — ' + c.email if c.email else ''}")
    if len(orphans) > 15:
        lines.append(f"  … +{len(orphans) - 15}")
    return IntentResult.ok(
        "\n".join(lines), intent="orphan_contacts", confidence=0.93,
        tool_calls=[{"name": "orphan_contacts", "result": {"count": len(orphans)}}],
    )


def _handle_orphan_companies(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Companies with no linked contacts — potential clean-up targets."""
    from sqlmodel import select
    from app.models import Company, Contact
    lang = _detect_lang(text)
    companies = list(ctx.session.exec(select(Company).where(
        Company.workspace_id == ctx.workspace_id, Company.deleted_at.is_(None),
    )).all())
    contact_company_ids = {c.company_id for c in ctx.session.exec(select(Contact).where(
        Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
        Contact.company_id.is_not(None),
    )).all()}
    orphans = [c for c in companies if c.id not in contact_company_ids]
    if not orphans:
        return IntentResult.ok(
            "🎉 Todas as empresas têm contatos vinculados." if lang == "pt" else "🎉 Every company has at least one contact.",
            intent="orphan_companies", confidence=0.93,
        )
    header = f"🏢 {len(orphans)} empresa(s) sem contatos:" if lang == "pt" else f"🏢 {len(orphans)} companies with no contacts:"
    lines = [header]
    for c in orphans[:15]:
        lines.append(f"  • {c.name}{' — ' + c.domain if c.domain else ''}")
    if len(orphans) > 15:
        lines.append(f"  … +{len(orphans) - 15}")
    return IntentResult.ok(
        "\n".join(lines), intent="orphan_companies", confidence=0.93,
        tool_calls=[{"name": "orphan_companies", "result": {"count": len(orphans)}}],
    )


def _handle_top_lead_sources(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Rank sources of leads by count + average score."""
    from sqlmodel import select, func
    from app.models import Lead
    lang = _detect_lang(text)
    stmt = select(Lead.source, func.count(Lead.id), func.avg(Lead.score)).where(
        Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
        Lead.source.is_not(None),
    ).group_by(Lead.source)
    rows = list(ctx.session.exec(stmt).all())
    if not rows:
        return IntentResult.ok(
            "Sem fontes de lead cadastradas." if lang == "pt" else "No lead sources yet.",
            intent="top_lead_sources", confidence=0.9,
        )
    rows.sort(key=lambda r: r[1], reverse=True)
    header = "🎯 Top fontes de lead:" if lang == "pt" else "🎯 Top lead sources:"
    lines = [header]
    for source, count, avg_score in rows[:10]:
        lines.append(f"  • {source}: {count} leads · score médio {avg_score:.1f}")
    return IntentResult.ok(
        "\n".join(lines), intent="top_lead_sources", confidence=0.93,
        tool_calls=[{"name": "top_lead_sources", "result": {"count": len(rows)}}],
    )


def _handle_leads_by_status(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Count of leads grouped by status."""
    from sqlmodel import select, func
    from app.models import Lead
    lang = _detect_lang(text)
    stmt = select(Lead.status, func.count(Lead.id)).where(
        Lead.workspace_id == ctx.workspace_id,
        Lead.deleted_at.is_(None),
    ).group_by(Lead.status)
    rows = list(ctx.session.exec(stmt).all())
    if not rows:
        return IntentResult.ok("Sem leads ainda." if lang == "pt" else "No leads yet.", intent="leads_by_status", confidence=0.9)
    header = "Leads por status:" if lang == "pt" else "Leads by status:"
    lines = [header]
    for status_val, count in rows:
        name = status_val.value if hasattr(status_val, "value") else str(status_val)
        lines.append(f"  • {name}: {count}")
    return IntentResult.ok("\n".join(lines), intent="leads_by_status", confidence=0.92)


def _handle_closing_this_month(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Opportunities with expected_close_date in the current month."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    from datetime import datetime, timezone
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)
    stmt = select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
        Opportunity.expected_close_date.is_not(None),
    )
    opps = [
        o for o in ctx.session.exec(stmt).all()
        if o.expected_close_date and o.expected_close_date.year == now.year and o.expected_close_date.month == now.month
    ]
    opps.sort(key=lambda o: o.expected_close_date)
    if not opps:
        reply = "Nenhuma oportunidade fechando este mês." if lang == "pt" else "No opportunities closing this month."
        return IntentResult.ok(reply, intent="closing_this_month", confidence=0.9)
    total = sum(o.amount or 0 for o in opps)
    header = f"{len(opps)} oportunidades fechando este mês (total $ {total:,.0f}):" if lang == "pt" else f"{len(opps)} opportunities closing this month (total $ {total:,.0f}):"
    lines = [header]
    for o in opps[:10]:
        d = o.expected_close_date.strftime("%d/%m") if lang == "pt" else o.expected_close_date.strftime("%b %d")
        lines.append(f"  • {o.name} — {o.currency} {o.amount:,.0f} — {d} ({o.probability:.0f}%)")
    if len(opps) > 10:
        lines.append(f"  … +{len(opps) - 10}")
    return IntentResult.ok("\n".join(lines), intent="closing_this_month", confidence=0.92)


def _handle_closing_this_week(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Opportunities with expected_close_date within the next 7 days."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    from datetime import datetime, timedelta, timezone
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)
    week_end = now + timedelta(days=7)
    stmt = select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
        Opportunity.expected_close_date.is_not(None),
    )
    opps = [
        o for o in ctx.session.exec(stmt).all()
        if o.expected_close_date and now.date() <= o.expected_close_date.date() <= week_end.date()
    ]
    opps.sort(key=lambda o: o.expected_close_date)
    if not opps:
        reply = "Nenhuma oportunidade fechando nesta semana." if lang == "pt" else "No opportunities closing this week."
        return IntentResult.ok(reply, intent="closing_this_week", confidence=0.9)
    total = sum(o.amount or 0 for o in opps)
    header = f"{len(opps)} oportunidade{'s' if len(opps) != 1 else ''} fechando esta semana (total ${total:,.0f}):" if lang == "pt" else f"{len(opps)} opportunit{'ies' if len(opps) != 1 else 'y'} closing this week (total ${total:,.0f}):"
    lines = [header]
    for o in opps[:10]:
        d = o.expected_close_date.strftime("%d/%m") if lang == "pt" else o.expected_close_date.strftime("%b %d")
        lines.append(f"  • {o.name} — {o.currency} {o.amount:,.0f} — {d}")
    return IntentResult.ok("\n".join(lines), intent="closing_this_week", confidence=0.92,
        tool_calls=[{"name": "recent_list", "kind": "opportunity",
                     "items": [{"id": str(o.id), "name": o.name} for o in opps]}])


_OPPS_AT_COMPANY_RE = re.compile(
    r"(?:oportunidades?|opportunit(?:ies|y)|deals?)\s+(?:d[ea]|em|na|no|at|from|for)\s+(?P<q>.+)",
    re.IGNORECASE,
)


def _handle_opportunities_at_company(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    from sqlmodel import select, or_
    from app.models import Opportunity, Company
    from app.services.crud import like_escape
    lang = _detect_lang(text)
    m = _OPPS_AT_COMPANY_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    query = m.group("q").strip().rstrip("?.").strip("\"'")
    like = f"%{like_escape(query)}%"
    company = ctx.session.exec(
        select(Company).where(
            Company.workspace_id == ctx.workspace_id,
            Company.deleted_at.is_(None),
            or_(Company.name.ilike(like, escape="\\"), Company.domain.ilike(like, escape="\\")),
        ).limit(1)
    ).first()
    if not company:
        return IntentResult.ok(
            f"Empresa '{query}' não encontrada." if lang == "pt" else f"Company '{query}' not found.",
            intent="opportunities_at_company", confidence=0.7,
        )
    opps = list(ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.company_id == company.id,
        ).order_by(Opportunity.amount.desc().nulls_last())
    ).all())
    if not opps:
        return IntentResult.ok(
            f"Nenhuma oportunidade em {company.name}." if lang == "pt" else f"No opportunities at {company.name}.",
            intent="opportunities_at_company", confidence=0.9,
        )
    header = f"Oportunidades em {company.name} ({len(opps)}):" if lang == "pt" else f"Opportunities at {company.name} ({len(opps)}):"
    lines = [header]
    for o in opps[:10]:
        lines.append(f"  • {o.name} — {_fmt_money(o.amount, o.currency)} · {o.status.value if hasattr(o.status,'value') else o.status}")
    return IntentResult.ok(
        "\n".join(lines), intent="opportunities_at_company", confidence=0.92,
        tool_calls=[{"name": "recent_list", "kind": "opportunity",
                     "items": [{"id": str(o.id), "name": o.name} for o in opps]}],
    )


_ENTITY_DETAILS_RE = re.compile(
    r"^\s*(?:detalhes?|info(?:rma[çc][ãa]o|s)?|details|show|mostre?|open|abrir?)?\s*"
    r"(?:d[eoa]s?\s+|do\s+|da\s+|of\s+the\s+|of\s+|the\s+|o\s+|a\s+)?"
    r"(?:contato|contact|empresa|company|oportunidade|opportunity|deal|neg[óo]cio|lead)\s+"
    r"(?P<name>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)
# Bare form with no name: "detalhes do contato" → hint asking which one.
_ENTITY_DETAILS_HINT_RE = re.compile(
    r"^\s*(?:detalhes?|info(?:rma[çc][ãa]o|s)?|details|show|mostre?|open|abrir?)\s+"
    r"(?:d[eoa]s?\s+|do\s+|da\s+|of\s+the\s+|of\s+|the\s+|o\s+|a\s+)?"
    r"(?P<kind>contato|contact|empresa|company|oportunidade|opportunity|deal|neg[óo]cio|lead)\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_entity_details(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Direct lookup by name: 'detalhes do contato Alice', 'info da Big Deal'."""
    from sqlmodel import select, or_
    from app.models import Contact, Company, Opportunity, Lead
    from app.services.crud import like_escape
    lang = _detect_lang(text)
    # Bare form with no name — polite prompt asking which one
    hint = _ENTITY_DETAILS_HINT_RE.match(text.strip())
    if hint and not _ENTITY_DETAILS_RE.match(text.strip()):
        kind = hint.group("kind").lower()
        return IntentResult.ok(
            (f"Qual {kind}? Diga o nome, por exemplo: \"detalhes do {kind} Alice\"." if lang == "pt"
             else f"Which {kind}? Give a name, e.g. \"details of {kind} Alice\"."),
            intent="entity_details", confidence=0.85,
        )
    m = _ENTITY_DETAILS_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().strip("\"'")
    lang = _detect_lang(text)
    lower_text = text.lower()
    like = f"%{like_escape(name)}%"
    # Detect entity kind from the message
    if "contato" in lower_text or "contact" in lower_text:
        row = ctx.session.exec(
            select(Contact).where(
                Contact.workspace_id == ctx.workspace_id,
                Contact.deleted_at.is_(None),
                or_(Contact.first_name.ilike(like, escape="\\"),
                    Contact.last_name.ilike(like, escape="\\"),
                    Contact.email.ilike(like, escape="\\")),
            ).limit(1)
        ).first()
        if not row:
            return IntentResult.ok(
                f"Contato \"{name}\" não encontrado." if lang == "pt" else f"Contact \"{name}\" not found.",
                intent="contact_details", confidence=0.7,
            )
        reply = _contact_details_reply(ctx.session, ctx.workspace_id, str(row.id), lang)
        return IntentResult.ok(reply or "", intent="contact_details", confidence=0.94,
            tool_calls=[{"name": "contact_details", "input": {"id": str(row.id)}}])
    if "empresa" in lower_text or "company" in lower_text:
        row = ctx.session.exec(
            select(Company).where(
                Company.workspace_id == ctx.workspace_id,
                Company.deleted_at.is_(None),
                or_(Company.name.ilike(like, escape="\\"), Company.domain.ilike(like, escape="\\")),
            ).limit(1)
        ).first()
        if not row:
            return IntentResult.ok(
                f"Empresa \"{name}\" não encontrada." if lang == "pt" else f"Company \"{name}\" not found.",
                intent="company_details", confidence=0.7,
            )
        if lang == "pt":
            parts = [f"🏢 {row.name}"]
            if row.domain: parts.append(f"  Domínio: {row.domain}")
            if row.industry: parts.append(f"  Setor: {row.industry}")
        else:
            parts = [f"🏢 {row.name}"]
            if row.domain: parts.append(f"  Domain: {row.domain}")
            if row.industry: parts.append(f"  Industry: {row.industry}")
        return IntentResult.ok("\n".join(parts), intent="company_details", confidence=0.94,
            tool_calls=[{"name": "company_details", "input": {"id": str(row.id)}}])
    if "oportunidade" in lower_text or "opportunity" in lower_text or "deal" in lower_text or "negócio" in lower_text or "negocio" in lower_text:
        row = ctx.session.exec(
            select(Opportunity).where(
                Opportunity.workspace_id == ctx.workspace_id,
                Opportunity.deleted_at.is_(None),
                Opportunity.name.ilike(like, escape="\\"),
            ).limit(1)
        ).first()
        if not row:
            return IntentResult.ok(
                f"Oportunidade \"{name}\" não encontrada." if lang == "pt" else f"Opportunity \"{name}\" not found.",
                intent="opportunity_details", confidence=0.7,
            )
        reply = _opportunity_details_reply(ctx.session, ctx.workspace_id, str(row.id), lang)
        return IntentResult.ok(reply or "", intent="opportunity_details", confidence=0.94,
            tool_calls=[{"name": "opportunity_details", "input": {"id": str(row.id)}}])
    if "lead" in lower_text:
        row = ctx.session.exec(
            select(Lead).where(
                Lead.workspace_id == ctx.workspace_id,
                Lead.deleted_at.is_(None),
                or_(Lead.first_name.ilike(like, escape="\\"),
                    Lead.last_name.ilike(like, escape="\\"),
                    Lead.email.ilike(like, escape="\\")),
            ).limit(1)
        ).first()
        if not row:
            return IntentResult.ok(
                f"Lead \"{name}\" não encontrado." if lang == "pt" else f"Lead \"{name}\" not found.",
                intent="lead_details", confidence=0.7,
            )
        full = f"{row.first_name} {row.last_name or ''}".strip()
        parts = [f"🎯 {full}"]
        if row.email: parts.append(f"  Email: {row.email}")
        if row.score is not None: parts.append(f"  Score: {row.score}")
        return IntentResult.ok("\n".join(parts), intent="lead_details", confidence=0.94)
    return IntentResult(handled=False)


_NOTE_ON_ENTITY_RE = re.compile(
    r"^\s*(?:nota|note)\s+(?:no|na|on|para|for|a[oa]?)\s+"
    r"(?:(?:o|a|the)\s+)?"
    r"(?P<kind>contato|contact|empresa|company|oportunidade|opportunity|lead|deal)\s+"
    r"(?P<name>.+?)\s*[:\-]\s*(?P<body>.+?)\s*$",
    re.IGNORECASE,
)

_KIND_MAP_PT = {
    "contato": "contact", "contact": "contact",
    "empresa": "company", "company": "company",
    "oportunidade": "opportunity", "opportunity": "opportunity", "deal": "opportunity",
    "lead": "lead",
}


def _handle_note_on_entity(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Note linked to a specific contact/company/opportunity/lead by name."""
    from sqlmodel import select, or_
    from app.models import Contact, Company, Opportunity, Lead, Note
    from app.services import crud
    from app.services.crud import like_escape
    m = _NOTE_ON_ENTITY_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    kind_raw = m.group("kind").lower()
    kind = _KIND_MAP_PT.get(kind_raw)
    name = m.group("name").strip().strip("\"'")
    body = m.group("body").strip().rstrip(".")
    lang = _detect_lang(text)
    if not (kind and name and body):
        return IntentResult(handled=False)
    like = f"%{like_escape(name)}%"
    entity_id = None
    entity_label = name
    if kind == "contact":
        row = ctx.session.exec(
            select(Contact).where(
                Contact.workspace_id == ctx.workspace_id,
                Contact.deleted_at.is_(None),
                or_(Contact.first_name.ilike(like, escape="\\"),
                    Contact.last_name.ilike(like, escape="\\"),
                    Contact.email.ilike(like, escape="\\")),
            ).limit(1)
        ).first()
        if row:
            entity_id, entity_label = row.id, f"{row.first_name} {row.last_name or ''}".strip()
            note = Note(workspace_id=ctx.workspace_id, body=body, related_contact_id=entity_id, author_user_id=ctx.user_id)
    elif kind == "company":
        row = ctx.session.exec(
            select(Company).where(
                Company.workspace_id == ctx.workspace_id,
                Company.deleted_at.is_(None),
                or_(Company.name.ilike(like, escape="\\"), Company.domain.ilike(like, escape="\\")),
            ).limit(1)
        ).first()
        if row:
            entity_id, entity_label = row.id, row.name
            note = Note(workspace_id=ctx.workspace_id, body=body, related_company_id=entity_id, author_user_id=ctx.user_id)
    elif kind == "opportunity":
        row = ctx.session.exec(
            select(Opportunity).where(
                Opportunity.workspace_id == ctx.workspace_id,
                Opportunity.deleted_at.is_(None),
                Opportunity.name.ilike(like, escape="\\"),
            ).limit(1)
        ).first()
        if row:
            entity_id, entity_label = row.id, row.name
            note = Note(workspace_id=ctx.workspace_id, body=body, related_opportunity_id=entity_id, author_user_id=ctx.user_id)
    elif kind == "lead":
        row = ctx.session.exec(
            select(Lead).where(
                Lead.workspace_id == ctx.workspace_id,
                Lead.deleted_at.is_(None),
                or_(Lead.first_name.ilike(like, escape="\\"),
                    Lead.last_name.ilike(like, escape="\\"),
                    Lead.email.ilike(like, escape="\\")),
            ).limit(1)
        ).first()
        if row:
            entity_id, entity_label = row.id, f"{row.first_name} {row.last_name or ''}".strip()
            note = Note(workspace_id=ctx.workspace_id, body=body, related_lead_id=entity_id, author_user_id=ctx.user_id)
    if entity_id is None:
        return IntentResult.ok(
            f"Não encontrei {kind_raw} \"{name}\"." if lang == "pt"
            else f"No {kind} matching \"{name}\".",
            intent="note_on_entity", confidence=0.7,
        )
    note = crud.create_scoped(ctx.session, note)
    reply = (f"📝 Nota criada em {kind_raw} \"{entity_label}\"." if lang == "pt"
             else f"📝 Note added to {kind} \"{entity_label}\".")
    return IntentResult.ok(
        reply, intent="note_on_entity", confidence=0.94,
        tool_calls=[{"name": "note_on_entity",
                     "input": {"kind": kind, "entity": entity_label, "body": body},
                     "result": {"id": str(note.id)}}],
    )


def _handle_onboarding(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """First-time user guide — Manus-style checklist with concrete next actions."""
    lang = _detect_lang(text)
    counts = snap.counts or {}
    total = sum(counts.get(k, 0) for k in ("contacts", "companies", "opportunities", "leads"))
    # Detect state — early, mid, or filled
    if total == 0:
        state = "empty"
    elif total < 20:
        state = "starting"
    else:
        state = "active"

    if lang == "pt":
        header = "👋 **Bem-vindo ao VisiQuost!**"
        subtitle = "Vou te guiar em 3 passos:" if state != "active" else "Aqui está o que dá pra fazer agora:"
        if state == "empty":
            steps = [
                ("1️⃣", "Popular dados de exemplo", "Diga: `popular demo`"),
                ("2️⃣", "Ver o pipeline", "Diga: `pipeline`"),
                ("3️⃣", "Criar seu primeiro contato real", "Diga: `novo contato: Nome Sobrenome`"),
            ]
        elif state == "starting":
            steps = [
                ("1️⃣", "Ver oportunidades", "Diga: `oportunidades` ou `top 5 oportunidades`"),
                ("2️⃣", "Agendar uma reunião", "Diga: `agende reunião com <contato> amanhã 15h`"),
                ("3️⃣", "Ver o painel", "Diga: `painel` ou `pipeline`"),
            ]
        else:
            steps = [
                ("1️⃣", "Foco do dia", "Diga: `foco de hoje` ou `ajude a priorizar`"),
                ("2️⃣", "Insights", "Diga: `insights` ou `dicas`"),
                ("3️⃣", "Saúde do sistema", "Diga: `status`"),
            ]
        lines = [header, "", subtitle, ""]
        for icon, title, action in steps:
            lines.append(f"{icon} **{title}**")
            lines.append(f"   💬 {action}")
            lines.append("")
        lines.append("_Digite `ajuda` a qualquer momento pra ver a lista completa de comandos._")
    else:
        header = "👋 **Welcome to VisiQuost!**"
        subtitle = "I'll guide you in 3 steps:" if state != "active" else "Here's what you can do now:"
        if state == "empty":
            steps = [
                ("1️⃣", "Seed sample data", "Say: `seed demo`"),
                ("2️⃣", "View the pipeline", "Say: `pipeline`"),
                ("3️⃣", "Create your first real contact", "Say: `new contact: First Last`"),
            ]
        elif state == "starting":
            steps = [
                ("1️⃣", "See opportunities", "Say: `opportunities` or `top 5 opportunities`"),
                ("2️⃣", "Schedule a meeting", "Say: `schedule meeting with <name> tomorrow 3pm`"),
                ("3️⃣", "View dashboard", "Say: `dashboard`"),
            ]
        else:
            steps = [
                ("1️⃣", "Today's focus", "Say: `focus today` or `help me prioritize`"),
                ("2️⃣", "Insights", "Say: `insights` or `tips`"),
                ("3️⃣", "System health", "Say: `status`"),
            ]
        lines = [header, "", subtitle, ""]
        for icon, title, action in steps:
            lines.append(f"{icon} **{title}**")
            lines.append(f"   💬 {action}")
            lines.append("")
        lines.append("_Type `help` anytime to see the full command list._")

    return IntentResult.ok(
        "\n".join(lines).rstrip(), intent="onboarding", confidence=0.95,
        tool_calls=[{"name": "onboarding", "result": {"state": state, "total_records": total}}],
    )


def _handle_seed_demo(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Populate workspace with a realistic sample dataset."""
    from app.services.demo_seed import seed_workspace
    lang = _detect_lang(text)
    lower = _normalize(text)
    force = any(k in lower for k in ("force", "forca", "resetar", "reset"))
    try:
        result = seed_workspace(ctx.session, ctx.workspace_id, ctx.user_id, force=force)
    except Exception as e:
        return IntentResult.ok(
            f"Falha ao popular demo: {e}" if lang == "pt" else f"Failed to seed demo: {e}",
            intent="seed_demo", confidence=0.5,
        )
    if result.get("status") == "skipped":
        return IntentResult.ok(
            ("Workspace já tem dados — diga \"popular demo forçado\" pra sobrescrever."
             if lang == "pt" else
             "Workspace already has data — say \"seed demo force\" to overwrite."),
            intent="seed_demo", confidence=0.9,
        )
    created = result.get("counts", {})
    if lang == "pt":
        lines = ["🌱 Dataset demo instanciado. Estado do workspace:"]
        for kind, n in created.items():
            lines.append(f"  ✅ {n} {kind}")
        lines.append("")
        lines.append("Pronto para consulta. Sugiro: \"pipeline\", \"contatos\" ou \"briefing\".")
    else:
        lines = ["🌱 Demo dataset instanced. Workspace state:"]
        for kind, n in created.items():
            lines.append(f"  ✅ {n} {kind}")
        lines.append("")
        lines.append("Ready to query. Suggested: \"pipeline\", \"contacts\", or \"briefing\".")
    return IntentResult.ok(
        "\n".join(lines), intent="seed_demo", confidence=0.95,
        tool_calls=[{"name": "seed_demo", "input": {"force": force}, "result": result}],
    )


def _handle_system_check(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Self-diagnose: pipeline configured? work_dir accessible? demo data seeded?
    Returns a Manus-like checklist with actionable fixes."""
    from sqlmodel import select
    from app.models import Pipeline, PipelineStage, Contact, Company, Opportunity
    from app.jarvis.device_tools import _get_work_dir
    import os

    lang = _detect_lang(text)
    checks: list[tuple[bool, str, str | None]] = []  # (ok, label, hint_if_not_ok)

    # 1) Default pipeline
    pipeline = ctx.session.exec(
        select(Pipeline).where(
            Pipeline.workspace_id == ctx.workspace_id,
            Pipeline.deleted_at.is_(None),
            Pipeline.is_default.is_(True),
        )
    ).first()
    if pipeline:
        stages_n = ctx.session.exec(
            select(PipelineStage).where(
                PipelineStage.pipeline_id == pipeline.id,
                PipelineStage.deleted_at.is_(None),
            )
        ).all()
        if stages_n:
            checks.append((True,
                (f"Pipeline padrão ({len(stages_n)} estágios)" if lang == "pt"
                 else f"Default pipeline ({len(stages_n)} stages)"),
                None))
        else:
            checks.append((False,
                "Pipeline sem estágios" if lang == "pt" else "Pipeline has no stages",
                "Vá em Pipeline → Instalar template padrão" if lang == "pt"
                else "Go to Pipeline → Install default template"))
    else:
        checks.append((False,
            "Pipeline padrão ausente" if lang == "pt" else "No default pipeline",
            "Crie uma oportunidade (o pipeline padrão é auto-criado)" if lang == "pt"
            else "Create an opportunity (default pipeline is auto-created)"))

    # 2) Work directory
    workdir = _get_work_dir()
    if workdir and os.path.exists(workdir):
        try:
            file_count = len(list(workdir.iterdir()))
            checks.append((True,
                (f"Pasta de trabalho: {workdir} ({file_count} arquivo(s))" if lang == "pt"
                 else f"Work directory: {workdir} ({file_count} file(s))"),
                None))
        except OSError:
            checks.append((False,
                f"Pasta de trabalho inacessível: {workdir}" if lang == "pt"
                else f"Work directory unreadable: {workdir}",
                "Verifique permissões da pasta" if lang == "pt"
                else "Check folder permissions"))
    else:
        checks.append((False,
            "Pasta de trabalho não configurada" if lang == "pt"
            else "Work directory not set",
            "Será criada automaticamente ao usar arquivos" if lang == "pt"
            else "Will be created automatically when you use files"))

    # 3) Data seeded?
    counts = snap.counts or {}
    total_records = sum(counts.get(k, 0) for k in ("contacts", "companies", "opportunities", "leads"))
    if total_records == 0:
        checks.append((False,
            "Nenhum registro (workspace vazio)" if lang == "pt"
            else "No records yet (empty workspace)",
            "Diga \"popular demo\" pra semear dados de exemplo" if lang == "pt"
            else "Say \"seed demo data\" to add sample records"))
    else:
        checks.append((True,
            f"{total_records} registros no workspace" if lang == "pt"
            else f"{total_records} records in workspace",
            None))

    # 4) Any overdue tasks warning?
    overdue = len(snap.overdue_tasks or [])
    if overdue > 0:
        checks.append((False,
            f"{overdue} tarefa(s) atrasada(s)" if lang == "pt"
            else f"{overdue} overdue task(s)",
            "Diga \"tarefas atrasadas\" pra ver a lista" if lang == "pt"
            else "Say \"overdue tasks\" to see the list"))
    else:
        checks.append((True,
            "Sem tarefas atrasadas" if lang == "pt" else "No overdue tasks",
            None))

    # Format Manus-like checklist
    ok_count = sum(1 for ok, _, _ in checks if ok)
    total = len(checks)
    if lang == "pt":
        header = f"🩺 **Diagnóstico do sistema** — {ok_count}/{total} OK"
    else:
        header = f"🩺 **System check** — {ok_count}/{total} OK"
    lines = [header, ""]
    for ok, label, hint in checks:
        mark = "✅" if ok else "⚠️"
        lines.append(f"{mark} {label}")
        if not ok and hint:
            lines.append(f"   💡 {hint}")
    return IntentResult.ok(
        "\n".join(lines), intent="system_check", confidence=0.95,
        tool_calls=[{"name": "system_check", "result": {"ok": ok_count, "total": total}}],
    )


_FOLLOWUP_RE = re.compile(
    r"^\s*(?:agende?|schedule|marque?|book|create|crie|criar)?\s*"
    r"(?:um\s+|uma\s+|a\s+|the\s+)?"
    r"(?:follow[\s-]?up|follow[\s-]?ups?|acompanhamento|retorno|ligar|call|telefonar|liga(?:r)?)"
    r"(?:\s+(?:com|with|para|to)\s+(?P<who>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-'\.]*(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-'\.]*)*))?"
    r"(?:\s+(?P<when>.+?))?"
    r"\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_follow_up(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Follow-up shortcut → creates a Task. Extracts contact + when. Reuses create_task infra."""
    m = _FOLLOWUP_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    who = (m.group("who") or "").strip()
    when = (m.group("when") or "").strip()
    lang = _detect_lang(text)
    # Build a "crie tarefa" message so the existing task handler can parse due_at + contact linkage
    title_pt = f"Follow-up com {who}" if who else "Follow-up"
    title_en = f"Follow-up with {who}" if who else "Follow-up"
    title = title_pt if lang == "pt" else title_en
    synthesized = f"crie tarefa: {title}"
    if when:
        synthesized = f"{synthesized} {when}"
    # Reroute to create_task
    fake_intent = Intent(name="create_task", patterns=[], handler=_handle_create_task)
    return _handle_create_task(fake_intent, synthesized, snap, ctx)


def _handle_urgent_tasks(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Open tasks with priority = urgent or high."""
    from sqlmodel import select
    from app.models import Task, TaskStatus, TaskPriority
    lang = _detect_lang(text)
    lower = _normalize(text)
    # Support "urgente" (only urgent) vs "alta" (high + urgent)
    if "urgent" in lower:
        priorities = [TaskPriority.urgent]
    else:
        priorities = [TaskPriority.urgent, TaskPriority.high]
    tasks = list(ctx.session.exec(
        select(Task).where(
            Task.workspace_id == ctx.workspace_id,
            Task.deleted_at.is_(None),
            Task.status.in_([TaskStatus.todo, TaskStatus.in_progress, TaskStatus.blocked]),
            Task.priority.in_(priorities),
        ).order_by(Task.priority.desc(), Task.due_at.asc().nulls_last())
    ).all())
    if not tasks:
        return IntentResult.ok(
            "🎉 Nenhuma tarefa urgente." if lang == "pt" else "🎉 No urgent tasks.",
            intent="urgent_tasks", confidence=0.9,
        )
    header = (f"🔥 {len(tasks)} tarefa{'s' if len(tasks) != 1 else ''} de alta prioridade:" if lang == "pt"
              else f"🔥 {len(tasks)} high-priority task{'s' if len(tasks) != 1 else ''}:")
    lines = [header]
    for t in tasks[:15]:
        prio = t.priority.value if hasattr(t.priority, "value") else str(t.priority)
        due = ""
        if t.due_at:
            due = f" · {t.due_at.strftime('%d/%m')}" if lang == "pt" else f" · {t.due_at.strftime('%b %d')}"
        lines.append(f"  • [{prio}] {t.title}{due}")
    return IntentResult.ok("\n".join(lines), intent="urgent_tasks", confidence=0.94)


def _handle_top_leads(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Leads ranked by score (descending)."""
    from sqlmodel import select
    from app.models import Lead
    lang = _detect_lang(text)
    m = re.search(r"\btop\s+(\d+)|\bmelhores?\s+(\d+)|\bprimeiros?\s+(\d+)", text, re.IGNORECASE)
    n = min(int(m.group(1) or m.group(2) or m.group(3)) if m else 5, 25) if m else 5
    leads = list(ctx.session.exec(
        select(Lead).where(
            Lead.workspace_id == ctx.workspace_id,
            Lead.deleted_at.is_(None),
        ).order_by(Lead.score.desc().nulls_last()).limit(n)
    ).all())
    if not leads:
        return IntentResult.ok(
            "Nenhum lead cadastrado ainda." if lang == "pt" else "No leads yet.",
            intent="top_leads", confidence=0.9,
        )
    header = f"🎯 Top {len(leads)} leads por score:" if lang == "pt" else f"🎯 Top {len(leads)} leads by score:"
    lines = [header]
    for lead in leads:
        name = f"{lead.first_name} {lead.last_name or ''}".strip()
        score = lead.score if lead.score is not None else "?"
        lines.append(f"  • {name} — score {score}")
    return IntentResult.ok(
        "\n".join(lines), intent="top_leads", confidence=0.94,
        tool_calls=[{"name": "recent_list", "kind": "lead",
                     "items": [{"id": str(l.id), "name": f"{l.first_name} {l.last_name or ''}".strip()} for l in leads]}],
    )


def _handle_average_deal_size(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Ticket médio: average amount across open opportunities."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    opps = list(ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
        )
    ).all())
    if not opps:
        return IntentResult.ok(
            "Sem oportunidades abertas pra calcular ticket médio." if lang == "pt"
            else "No open opportunities to average.",
            intent="average_deal_size", confidence=0.9,
        )
    total = sum(o.amount or 0 for o in opps)
    avg = total / len(opps)
    currency = opps[0].currency
    if lang == "pt":
        body = f"🎫 Ticket médio: **{_fmt_money(avg, currency)}** ({len(opps)} oportunidades · total {_fmt_money(total, currency)})"
    else:
        body = f"🎫 Average deal: **{_fmt_money(avg, currency)}** ({len(opps)} deals · total {_fmt_money(total, currency)})"
    return IntentResult.ok(body, intent="average_deal_size", confidence=0.94)


def _handle_go_home(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Bare 'dashboard'/'painel'/'home' — return quick overview since the chat can't navigate."""
    lang = _detect_lang(text)
    c = snap.counts or {}
    if lang == "pt":
        body = (
            f"🏠 Painel — visão rápida:\n"
            f"  • Contatos: {c.get('contacts', 0)}\n"
            f"  • Empresas: {c.get('companies', 0)}\n"
            f"  • Leads: {c.get('leads', 0)}\n"
            f"  • Oportunidades: {c.get('opportunities', 0)}\n"
            f"  • Tarefas abertas: {c.get('tasks_open', 0)}\n"
            f"\nDica: clique em \"Painel\" na barra lateral pra ver dashboard visual."
        )
    else:
        body = (
            f"🏠 Dashboard — quick view:\n"
            f"  • Contacts: {c.get('contacts', 0)}\n"
            f"  • Companies: {c.get('companies', 0)}\n"
            f"  • Leads: {c.get('leads', 0)}\n"
            f"  • Opportunities: {c.get('opportunities', 0)}\n"
            f"  • Open tasks: {c.get('tasks_open', 0)}\n"
            f"\nTip: click \"Painel\" in the sidebar for the visual dashboard."
        )
    return IntentResult.ok(body, intent="go_home", confidence=0.9)


def _handle_insights(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Curated insights: nudges from the workspace snapshot + a couple of derived tips."""
    lang = _detect_lang(text)
    nudges = list(snap.nudges or [])
    lines = ["💡 Insights:" if lang == "pt" else "💡 Insights:"]
    if nudges:
        for n in nudges[:8]:
            label = n.get("label") if isinstance(n, dict) else str(n)
            lines.append(f"  • {label}")
    # Derived tips based on snapshot state
    overdue = len(snap.overdue_tasks or [])
    if overdue >= 3:
        lines.append(f"  • {overdue} tarefas atrasadas — priorize as vencidas há mais tempo" if lang == "pt"
                     else f"  • {overdue} overdue tasks — prioritize the oldest first")
    open_opps = len(snap.open_opportunities or [])
    if open_opps == 0:
        lines.append("  • Pipeline vazio — hora de prospectar novos leads" if lang == "pt"
                     else "  • Pipeline empty — time to prospect new leads")
    upcoming = len(snap.upcoming_meetings or [])
    if upcoming == 0 and open_opps > 3:
        lines.append("  • Nenhuma reunião marcada mas pipeline ativo — agende follow-ups" if lang == "pt"
                     else "  • No meetings but active pipeline — schedule follow-ups")
    if len(lines) == 1:
        lines.append("  • Sem alertas — bom trabalho!" if lang == "pt" else "  • No alerts — nice job!")
    return IntentResult.ok("\n".join(lines), intent="insights", confidence=0.92)


# Form A: verb + all/todas + [filter] + tasks + [filter]
_BULK_DELETE_TASKS_RE = re.compile(
    r"^\s*(?:apaga|apague|apagar|delete|remove|remover|remova|excluir|clear|limpe|limpar)\s+"
    r"(?:todas?|all)\s+"
    r"(?:as\s+|the\s+)?"
    r"(?:(?P<pre>conclu[íi]das?|feitas?|done|completed|canceladas?|cancelled|abertas?|open|todo|pending|pendentes?|atrasadas?|overdue|late|vencidas?)\s+)?"
    r"(?:tarefas?|tasks?)\s*"
    r"(?P<post>conclu[íi]das?|feitas?|done|completed|canceladas?|cancelled|abertas?|open|todo|pending|pendentes?|atrasadas?|overdue|late|vencidas?)?"
    r"\s*[?!.]?\s*$",
    re.IGNORECASE,
)
# Form B: verb + tasks + filter (no "all")
_BULK_DELETE_TASKS_RE_B = re.compile(
    r"^\s*(?:apaga|apague|apagar|delete|remove|remover|remova|excluir|clear|limpe|limpar)\s+"
    r"(?:as\s+|all\s+)?"
    r"(?:tarefas?|tasks?)\s+"
    r"(?P<post>conclu[íi]das?|feitas?|done|completed|canceladas?|cancelled|abertas?|open|todo|pending|pendentes?|atrasadas?|overdue|late|vencidas?)"
    r"\s*[?!.]?\s*$",
    re.IGNORECASE,
)


_ANALYZE_LEAD_RE = re.compile(
    r"^\s*(?:analise?|analisa|analyze|analyse)\s+"
    r"(?:o\s+|a\s+|the\s+)?"
    r"lead\s+"
    r"(?P<name>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_analyze_lead(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Mini-report on one lead: source, score, age, ownership hint."""
    from datetime import datetime, timezone
    from sqlmodel import select, or_
    from app.models import Lead
    from app.services.crud import like_escape
    m = _ANALYZE_LEAD_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().strip("\"'").rstrip(".!?")
    if not name:
        return IntentResult(handled=False)
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"
    lead = ctx.session.exec(
        select(Lead).where(
            Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
            or_(Lead.first_name.ilike(like, escape="\\"),
                Lead.last_name.ilike(like, escape="\\"),
                Lead.email.ilike(like, escape="\\")),
        ).limit(1)
    ).first()
    if not lead:
        return IntentResult.ok(
            f"Lead \"{name}\" não encontrado." if lang == "pt"
            else f"Lead \"{name}\" not found.",
            intent="analyze_lead", confidence=0.7,
        )
    full = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or lead.email or "?"
    now = datetime.now(timezone.utc)
    created = lead.created_at if lead.created_at.tzinfo else lead.created_at.replace(tzinfo=timezone.utc)
    age_days = (now - created).days

    tone = (snap.preferences or {}).get("tone", "formal")
    if tone == "casual":
        lines = [f"🌱 Lead {full}:" if lang == "pt" else f"🌱 Lead {full}:"]
    elif tone == "concise":
        lines = [f"{full}:"]
    elif tone == "technical":
        lines = [f"lead[{full!r}]:"]
    else:
        lines = [f"🌱 Análise: {full}" if lang == "pt" else f"🌱 Analysis: {full}"]
    if lead.email:
        lines.append(f"  Email: {lead.email}")
    if lead.phone:
        lines.append(f"  {'Telefone' if lang == 'pt' else 'Phone'}: {lead.phone}")
    if getattr(lead, "company_name", None):
        lines.append(f"  {'Empresa' if lang == 'pt' else 'Company'}: {lead.company_name}")
    if getattr(lead, "source", None):
        lines.append(f"  {'Origem' if lang == 'pt' else 'Source'}: {lead.source}")
    if getattr(lead, "score", None) is not None:
        lines.append(f"  Score: {int(lead.score)}")
    if getattr(lead, "status", None):
        st = lead.status.value if hasattr(lead.status, "value") else str(lead.status)
        lines.append(f"  Status: {st}")
    lines.append(f"  {'Cadastrado há' if lang == 'pt' else 'Added'}: {age_days}d")

    tip = ""
    if age_days > 14:
        tip = (f"⚠️ Sem contato há {age_days} dias — re-engaje." if lang == "pt"
               else f"⚠️ Silent for {age_days} days — re-engage.")
    elif not lead.email and not lead.phone:
        tip = ("💡 Sem email ou telefone — enriqueça o registro." if lang == "pt"
               else "💡 No email or phone — enrich the record.")
    if tip:
        lines.append("")
        lines.append(tip)

    return IntentResult.ok(
        "\n".join(lines), intent="analyze_lead", confidence=0.94,
        tool_calls=[{"name": "recent_list", "kind": "lead",
                     "items": [{"id": str(lead.id), "name": full}]}],
    )


_ANALYZE_COMPANY_RE = re.compile(
    r"^\s*(?:analise?|analisa|analyze|analyse)\s+"
    r"(?:a\s+|the\s+)?"
    r"(?:empresa|company)\s+"
    r"(?P<name>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_analyze_company(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Mini-report on one company: domain, industry, contacts, opps."""
    from datetime import datetime, timezone
    from sqlmodel import select
    from app.models import Company, Contact, Opportunity
    from app.services.crud import like_escape
    m = _ANALYZE_COMPANY_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().strip("\"'").rstrip(".!?")
    if not name:
        return IntentResult(handled=False)
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"
    company = ctx.session.exec(
        select(Company).where(
            Company.workspace_id == ctx.workspace_id, Company.deleted_at.is_(None),
            Company.name.ilike(like, escape="\\"),
        ).limit(1)
    ).first()
    if not company:
        return IntentResult.ok(
            f"Empresa \"{name}\" não encontrada." if lang == "pt"
            else f"Company \"{name}\" not found.",
            intent="analyze_company", confidence=0.7,
        )
    now = datetime.now(timezone.utc)
    created = company.created_at if company.created_at.tzinfo else company.created_at.replace(tzinfo=timezone.utc)
    age_days = (now - created).days
    contacts = ctx.session.exec(
        select(Contact).where(
            Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
            Contact.company_id == company.id,
        )
    ).all()
    opps = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
            Opportunity.company_id == company.id,
        )
    ).all()
    open_opps = [o for o in opps if (o.status.value if hasattr(o.status, "value") else str(o.status)) == "open"]
    won_opps = [o for o in opps if (o.status.value if hasattr(o.status, "value") else str(o.status)) == "won"]
    total_open = sum((o.amount or 0) for o in open_opps)
    total_won = sum((o.amount or 0) for o in won_opps)

    tone = (snap.preferences or {}).get("tone", "formal")
    if tone == "casual":
        lines = [f"🏢 Aqui vai {company.name}:" if lang == "pt" else f"🏢 Here's {company.name}:"]
    elif tone == "concise":
        lines = [f"{company.name}:"]
    elif tone == "technical":
        lines = [f"company[{company.name!r}]:"]
    else:
        lines = [f"🏢 Análise: {company.name}" if lang == "pt" else f"🏢 Analysis: {company.name}"]
    if company.domain:
        lines.append(f"  {'Domínio' if lang == 'pt' else 'Domain'}: {company.domain}")
    if company.industry:
        lines.append(f"  {'Indústria' if lang == 'pt' else 'Industry'}: {company.industry}")
    lines.append(f"  {'Cadastrada há' if lang == 'pt' else 'Added'}: {age_days}d")
    lines.append(f"  {'Contatos' if lang == 'pt' else 'Contacts'}: {len(contacts)}")
    currency = "R$" if lang == "pt" else "$"
    lines.append(f"  {'Pipeline aberto' if lang == 'pt' else 'Open pipeline'}: {len(open_opps)} ({currency} {total_open:,.0f})".replace(",", "."))
    if won_opps:
        lines.append(f"  {'Ganhas' if lang == 'pt' else 'Won'}: {len(won_opps)} ({currency} {total_won:,.0f})".replace(",", "."))

    tip = ""
    if not contacts:
        tip = ("💡 Nenhum contato vinculado — associe alguém desta empresa." if lang == "pt"
               else "💡 No contacts linked — associate someone from this company.")
    elif not opps:
        tip = ("💡 Nenhuma oportunidade aberta — crie uma para ativar o relacionamento." if lang == "pt"
               else "💡 No opportunities — create one to activate this relationship.")
    if tip:
        lines.append("")
        lines.append(tip)

    return IntentResult.ok(
        "\n".join(lines), intent="analyze_company", confidence=0.94,
        tool_calls=[{"name": "recent_list", "kind": "company",
                     "items": [{"id": str(company.id), "name": company.name}]}],
    )


_ANALYZE_CONTACT_RE = re.compile(
    r"^\s*(?:analise?|analisa|analyze|analyse)\s+"
    r"(?:o\s+|a\s+|the\s+)?"
    r"(?:contato|contact)\s+"
    r"(?P<name>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_analyze_contact(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Mini-report on one contact: email, phone, company, opps, tasks."""
    from datetime import datetime, timezone
    from sqlmodel import select, or_
    from app.models import Contact, Company, Opportunity, Task
    from app.services.crud import like_escape
    m = _ANALYZE_CONTACT_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().strip("\"'").rstrip(".!?")
    if not name:
        return IntentResult(handled=False)
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"
    contact = ctx.session.exec(
        select(Contact).where(
            Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
            or_(Contact.first_name.ilike(like, escape="\\"),
                Contact.last_name.ilike(like, escape="\\"),
                Contact.email.ilike(like, escape="\\")),
        ).limit(1)
    ).first()
    if not contact:
        return IntentResult.ok(
            f"Contato \"{name}\" não encontrado." if lang == "pt"
            else f"Contact \"{name}\" not found.",
            intent="analyze_contact", confidence=0.7,
        )
    full = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    now = datetime.now(timezone.utc)
    created = contact.created_at if contact.created_at.tzinfo else contact.created_at.replace(tzinfo=timezone.utc)
    age_days = (now - created).days
    company = None
    if contact.company_id:
        company = ctx.session.exec(select(Company).where(Company.id == contact.company_id)).first()
    opps = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
            Opportunity.contact_id == contact.id,
        )
    ).all()
    open_tasks = ctx.session.exec(
        select(Task).where(
            Task.workspace_id == ctx.workspace_id, Task.deleted_at.is_(None),
            Task.contact_id == contact.id if hasattr(Task, "contact_id") else True,
            Task.status != "done", Task.status != "cancelled",
        )
    ).all() if hasattr(Task, "contact_id") else []

    tone = (snap.preferences or {}).get("tone", "formal")
    if tone == "casual":
        lines = [f"🔍 Dá uma olhada em {full}:" if lang == "pt" else f"🔍 Here's {full}:"]
    elif tone == "concise":
        lines = [f"{full}:"]
    elif tone == "technical":
        lines = [f"contact[{full!r}]:"]
    else:
        lines = [f"🔍 Análise: {full}" if lang == "pt" else f"🔍 Analysis: {full}"]
    if contact.email:
        lines.append(f"  Email: {contact.email}")
    if contact.phone:
        lines.append(f"  {'Telefone' if lang == 'pt' else 'Phone'}: {contact.phone}")
    if contact.job_title:
        lines.append(f"  {'Cargo' if lang == 'pt' else 'Title'}: {contact.job_title}")
    if company:
        lines.append(f"  {'Empresa' if lang == 'pt' else 'Company'}: {company.name}")
    lines.append(f"  {'Cadastrado há' if lang == 'pt' else 'Added'}: {age_days}d")
    if opps:
        total = sum((o.amount or 0) for o in opps)
        open_opps = [o for o in opps if (o.status.value if hasattr(o.status, "value") else str(o.status)) == "open"]
        currency = "R$" if lang == "pt" else "$"
        lines.append(f"  {'Oportunidades' if lang == 'pt' else 'Opportunities'}: "
                     f"{len(opps)} ({len(open_opps)} {'abertas' if lang == 'pt' else 'open'}), "
                     f"{currency} {total:,.0f}".replace(",", "."))
    if open_tasks:
        lines.append(f"  {'Tarefas abertas' if lang == 'pt' else 'Open tasks'}: {len(open_tasks)}")

    # Nudge
    tip = ""
    if not contact.email:
        tip = ("💡 Sem email cadastrado — adicione." if lang == "pt"
               else "💡 No email on file — add one.")
    elif not opps:
        tip = ("💡 Nenhuma oportunidade vinculada — considere criar uma." if lang == "pt"
               else "💡 No opportunities linked — consider creating one.")
    if tip:
        lines.append("")
        lines.append(tip)

    return IntentResult.ok(
        "\n".join(lines), intent="analyze_contact", confidence=0.94,
        tool_calls=[{"name": "recent_list", "kind": "contact",
                     "items": [{"id": str(contact.id), "name": full}]}],
    )


_ANALYZE_OPP_RE = re.compile(
    r"^\s*(?:analise?|analisa|analyze|analyse|status\s+(?:d[aeo]\s+)?|report\s+(?:on\s+)?|how'?s|how\s+is|how\s+are|como\s+(?:est[áa]|vai|v[ãa]o))\s+"
    r"(?:a\s+|o\s+|the\s+)?"
    r"(?:oportunidade|opportunity|deal|neg[óo]cio|opp)?\s*"
    r"(?P<name>.+?)"
    r"(?:\s+(?:doing|indo|going))?"
    r"\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_analyze_opportunity(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Mini-report on one opportunity: amount, stage, probability, age, related."""
    from datetime import datetime, timezone
    from sqlmodel import select
    from app.models import Opportunity, PipelineStage, Contact, Company, Task, Meeting
    from app.services.crud import like_escape
    m = _ANALYZE_OPP_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().strip("\"'").rstrip(".!?")
    if not name or len(name) < 2:
        return IntentResult(handled=False)
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"
    opp = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.name.ilike(like, escape="\\"),
        ).limit(1)
    ).first()
    if not opp:
        return IntentResult.ok(
            f"Não encontrei oportunidade \"{name}\"." if lang == "pt"
            else f"No opportunity found matching \"{name}\".",
            intent="analyze_opportunity", confidence=0.7,
        )
    stage = ctx.session.exec(select(PipelineStage).where(PipelineStage.id == opp.stage_id)).first()
    stage_name = stage.name if stage else "?"
    now = datetime.now(timezone.utc)
    created = opp.created_at if opp.created_at.tzinfo else opp.created_at.replace(tzinfo=timezone.utc)
    age_days = (now - created).days
    amt_str = (f"R$ {opp.amount:,.0f}".replace(",", ".") if lang == "pt"
               else f"${opp.amount:,.0f}") if opp.amount else "?"
    prob = int(opp.probability or 0)
    contact = None
    if opp.contact_id:
        contact = ctx.session.exec(select(Contact).where(Contact.id == opp.contact_id)).first()
    company = None
    if opp.company_id:
        company = ctx.session.exec(select(Company).where(Company.id == opp.company_id)).first()
    open_tasks_count = len(ctx.session.exec(
        select(Task).where(
            Task.workspace_id == ctx.workspace_id,
            Task.deleted_at.is_(None),
            Task.opportunity_id == opp.id,
            Task.status != "done", Task.status != "cancelled",
        )
    ).all()) if hasattr(Task, "opportunity_id") else 0

    lines = []
    tone = (snap.preferences or {}).get("tone", "formal")
    if tone == "casual":
        header = f"🔍 Dá uma olhada em \"{opp.name}\":" if lang == "pt" else f"🔍 Here's \"{opp.name}\":"
    elif tone == "concise":
        header = f"\"{opp.name}\":"
    elif tone == "technical":
        header = f"opportunity[{opp.name!r}]:"
    else:
        header = f"🔍 Análise: \"{opp.name}\"" if lang == "pt" else f"🔍 Analysis: \"{opp.name}\""
    lines.append(header)
    status_str = opp.status.value if hasattr(opp.status, "value") else str(opp.status)
    lines.append(f"  Status: {status_str}")
    lines.append(f"  {'Estágio' if lang == 'pt' else 'Stage'}: {stage_name}")
    lines.append(f"  {'Valor' if lang == 'pt' else 'Amount'}: {amt_str}")
    lines.append(f"  {'Probabilidade' if lang == 'pt' else 'Probability'}: {prob}%")
    lines.append(f"  {'Idade' if lang == 'pt' else 'Age'}: {age_days}d")
    if contact:
        cname = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
        lines.append(f"  {'Contato' if lang == 'pt' else 'Contact'}: {cname}")
    if company:
        lines.append(f"  {'Empresa' if lang == 'pt' else 'Company'}: {company.name}")
    if open_tasks_count:
        lines.append(f"  {'Tarefas abertas' if lang == 'pt' else 'Open tasks'}: {open_tasks_count}")

    # Actionable nudge
    tip = ""
    if status_str == "open":
        if prob >= 70:
            tip = (f"💡 Alta probabilidade — considere fechar." if lang == "pt"
                   else f"💡 High probability — consider closing.")
        elif age_days > 30 and prob < 40:
            tip = (f"⚠️ Aberta há {age_days} dias com baixa probabilidade — reavalie." if lang == "pt"
                   else f"⚠️ Open for {age_days} days at low probability — reassess.")
        elif not contact:
            tip = (f"💡 Sem contato vinculado — associe um." if lang == "pt"
                   else f"💡 No contact linked — associate one.")
    if tip:
        lines.append("")
        lines.append(tip)

    return IntentResult.ok(
        "\n".join(lines), intent="analyze_opportunity", confidence=0.94,
        tool_calls=[{"name": "recent_list", "kind": "opportunity",
                     "items": [{"id": str(opp.id), "name": opp.name}]}],
    )


_OPPS_BY_AMOUNT_RE = re.compile(
    r"^\s*(?:oportunidades?|opportunit(?:y|ies)|deals?|opps?)\s+"
    r"(?:com\s+(?:valor\s+)?|acima\s+(?:de\s+)?|abaixo\s+(?:de\s+)?|maior(?:es)?\s+(?:que|do\s+que)\s+|menor(?:es)?\s+(?:que|do\s+que)\s+|above\s+|below\s+|over\s+|under\s+|greater\s+than\s+|less\s+than\s+|[><]=?)\s*"
    r"(?P<amount>R?\$?\s*\d[\d.,]*\s*(?:k|mil|m|milh[õo]es?|milhao)?)"
    r"\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _parse_amount(raw: str) -> float | None:
    s = raw.strip().lower().replace("r$", "").replace("$", "").replace(" ", "")
    mult = 1
    if s.endswith("k"):
        mult = 1_000; s = s[:-1]
    elif s.endswith("mil"):
        mult = 1_000; s = s[:-3]
    elif s.endswith("m") or s.endswith("milhao"):
        mult = 1_000_000; s = s.rstrip("m").rstrip("milhao")
    elif s.endswith("milhoes") or s.endswith("milhões"):
        mult = 1_000_000; s = s[:-7] if s.endswith("milhoes") else s[:-7]
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s) * mult
    except ValueError:
        return None


def _handle_opportunities_by_amount(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Filter open opportunities by amount: 'oportunidades acima de 10k'."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    m = _OPPS_BY_AMOUNT_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    lang = _detect_lang(text)
    amount = _parse_amount(m.group("amount"))
    if amount is None:
        return IntentResult.ok(
            f"Não entendi o valor \"{m.group('amount')}\"." if lang == "pt"
            else f"Couldn't parse amount \"{m.group('amount')}\".",
            intent="opportunities_by_amount", confidence=0.6,
        )
    lower = text.lower()
    direction = "above"
    if any(k in lower for k in ("abaixo", "menor", "below", "under", "less than", "<")):
        direction = "below"
    stmt = select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
        Opportunity.amount.is_not(None),
    )
    if direction == "above":
        stmt = stmt.where(Opportunity.amount >= amount)
    else:
        stmt = stmt.where(Opportunity.amount <= amount)
    stmt = stmt.order_by(Opportunity.amount.desc()).limit(10)
    opps = ctx.session.exec(stmt).all()
    label = f"acima de R$ {amount:,.0f}".replace(",", ".") if lang == "pt" else f"above ${amount:,.0f}"
    if direction == "below":
        label = f"abaixo de R$ {amount:,.0f}".replace(",", ".") if lang == "pt" else f"below ${amount:,.0f}"
    if not opps:
        return IntentResult.ok(
            f"Nenhuma oportunidade {label}." if lang == "pt"
            else f"No opportunities {label}.",
            intent="opportunities_by_amount", confidence=0.9,
        )
    header = f"💰 Oportunidades {label}:" if lang == "pt" else f"💰 Opportunities {label}:"
    lines = [header]
    for opp in opps:
        amt_str = f"R$ {opp.amount:,.0f}".replace(",", ".") if lang == "pt" else f"${opp.amount:,.0f}"
        lines.append(f"  • {opp.name} — {amt_str}")
    return IntentResult.ok(
        "\n".join(lines), intent="opportunities_by_amount", confidence=0.94,
        tool_calls=[{"name": "recent_list", "kind": "opportunity",
                     "items": [{"id": str(o.id), "name": o.name} for o in opps]}],
    )


def _handle_bulk_delete_tasks(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Soft-delete tasks in bulk, optionally filtered by status.

    "apaga todas tarefas concluídas" / "delete all done tasks" /
    "delete all overdue tasks".
    """
    from datetime import datetime, timezone
    from sqlmodel import select
    from app.models import Task, TaskStatus
    m = _BULK_DELETE_TASKS_RE.match(text.strip())
    if not m:
        m = _BULK_DELETE_TASKS_RE_B.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    lang = _detect_lang(text)
    # Either pre- or post-tasks position holds the filter
    filt = ""
    try:
        filt = (m.group("pre") or m.group("post") or "").lower()
    except IndexError:
        filt = (m.group("post") or "").lower()
    now = datetime.now(timezone.utc)
    stmt = select(Task).where(
        Task.workspace_id == ctx.workspace_id, Task.deleted_at.is_(None),
    )
    label = "tarefas" if lang == "pt" else "tasks"
    if filt in ("concluidas", "concluída", "concluídas", "feita", "feitas", "done", "completed"):
        stmt = stmt.where(Task.status == TaskStatus.done)
        label = "tarefas concluídas" if lang == "pt" else "completed tasks"
    elif filt in ("cancelada", "canceladas", "cancelled"):
        stmt = stmt.where(Task.status == TaskStatus.cancelled)
        label = "tarefas canceladas" if lang == "pt" else "cancelled tasks"
    elif filt in ("abertas", "aberta", "open", "todo", "pending", "pendente", "pendentes"):
        stmt = stmt.where(Task.status != TaskStatus.done, Task.status != TaskStatus.cancelled)
        label = "tarefas abertas" if lang == "pt" else "open tasks"
    elif filt in ("atrasada", "atrasadas", "overdue"):
        stmt = stmt.where(
            Task.due_at.is_not(None),
            Task.due_at < now,
            Task.status != TaskStatus.done,
            Task.status != TaskStatus.cancelled,
        )
        label = "tarefas atrasadas" if lang == "pt" else "overdue tasks"
    tasks = ctx.session.exec(stmt).all()
    if not tasks:
        return IntentResult.ok(
            f"Nenhuma {label} pra apagar." if lang == "pt"
            else f"No {label} to delete.",
            intent="bulk_delete_tasks", confidence=0.9,
        )
    ids = [str(t.id) for t in tasks]
    for t in tasks:
        t.deleted_at = now
        ctx.session.add(t)
    ctx.session.commit()
    n = len(tasks)
    return IntentResult.ok(
        (f"🗑 {n} {label} apagadas." if lang == "pt"
         else f"🗑 {n} {label} deleted."),
        intent="bulk_delete_tasks", confidence=0.94,
        tool_calls=[{"name": "bulk_delete_tasks", "input": {"filter": filt or "all"},
                     "result": {"count": n, "ids": ids}}],
    )


_CONVERT_LEAD_RE = re.compile(
    r"^\s*(?:convert|converta|converte|converter|promova?|promote)\s+"
    r"(?:o\s+|a\s+|the\s+)?lead\s+"
    r"(?P<name>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_convert_lead(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Convert a lead to a contact (+ optional opportunity), preserving lead data."""
    from datetime import datetime, timezone
    from sqlmodel import select, or_
    from app.models import Lead, Contact
    from app.services.crud import like_escape
    m = _CONVERT_LEAD_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().strip("\"'").rstrip(".!?")
    if not name:
        return IntentResult(handled=False)
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"
    lead = ctx.session.exec(
        select(Lead).where(
            Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
            or_(Lead.first_name.ilike(like, escape="\\"),
                Lead.last_name.ilike(like, escape="\\"),
                Lead.email.ilike(like, escape="\\")),
        ).limit(1)
    ).first()
    if not lead:
        return IntentResult.ok(
            f"Lead \"{name}\" não encontrado." if lang == "pt"
            else f"Lead \"{name}\" not found.",
            intent="convert_lead", confidence=0.7,
        )
    if lead.converted_contact_id:
        return IntentResult.ok(
            f"Lead \"{name}\" já foi convertido antes." if lang == "pt"
            else f"Lead \"{name}\" was already converted.",
            intent="convert_lead", confidence=0.85,
        )
    contact = Contact(
        workspace_id=ctx.workspace_id,
        first_name=lead.first_name,
        last_name=lead.last_name,
        email=lead.email,
        phone=lead.phone,
    )
    ctx.session.add(contact)
    ctx.session.flush()
    lead.converted_contact_id = contact.id
    lead.converted_at = datetime.now(timezone.utc)
    from app.models import LeadStatus
    lead.status = LeadStatus.qualified if hasattr(LeadStatus, "qualified") else lead.status
    ctx.session.add(lead)
    ctx.session.commit()
    ctx.session.refresh(contact)
    full = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or "?"
    return IntentResult.ok(
        (f"✅ Lead convertido: contato \"{full}\" criado a partir do lead." if lang == "pt"
         else f"✅ Lead converted: contact \"{full}\" created from lead."),
        intent="convert_lead", confidence=0.94,
        tool_calls=[{"name": "convert_lead",
                     "input": {"lead_id": str(lead.id)},
                     "result": {"contact_id": str(contact.id)}}],
    )


def _handle_data_quality(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Flag entities missing critical fields (email/phone/amount/probability)."""
    from sqlmodel import select, or_
    from app.models import Contact, Opportunity, OpportunityStatus
    lang = _detect_lang(text)

    contacts_no_email = ctx.session.exec(
        select(Contact).where(
            Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
            or_(Contact.email.is_(None), Contact.email == ""),
        )
    ).all()
    contacts_no_phone = ctx.session.exec(
        select(Contact).where(
            Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
            or_(Contact.phone.is_(None), Contact.phone == ""),
        )
    ).all()
    opps_no_amount = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
            or_(Opportunity.amount.is_(None), Opportunity.amount == 0),
        )
    ).all()
    opps_no_prob = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
            or_(Opportunity.probability.is_(None), Opportunity.probability == 0),
        )
    ).all()

    total_issues = (
        len(contacts_no_email) + len(contacts_no_phone)
        + len(opps_no_amount) + len(opps_no_prob)
    )
    if total_issues == 0:
        return IntentResult.ok(
            "✅ Dados completos — nenhum campo crítico faltando." if lang == "pt"
            else "✅ Data complete — no critical fields missing.",
            intent="data_quality", confidence=0.94,
        )
    tone = (snap.preferences or {}).get("tone", "formal")
    if tone == "casual":
        header = "🔍 Achei uns campos faltando:" if lang == "pt" else "🔍 Some fields are missing:"
    elif tone == "concise":
        header = "🔍 Faltando:" if lang == "pt" else "🔍 Missing:"
    elif tone == "technical":
        header = "data_quality.gaps:"
    else:
        header = "🔍 Qualidade dos dados:" if lang == "pt" else "🔍 Data quality:"
    lines = [header]
    if contacts_no_email:
        lines.append((f"  • {len(contacts_no_email)} contato(s) sem email"
                      if lang == "pt"
                      else f"  • {len(contacts_no_email)} contact(s) missing email"))
    if contacts_no_phone:
        lines.append((f"  • {len(contacts_no_phone)} contato(s) sem telefone"
                      if lang == "pt"
                      else f"  • {len(contacts_no_phone)} contact(s) missing phone"))
    if opps_no_amount:
        lines.append((f"  • {len(opps_no_amount)} oportunidade(s) abertas sem valor"
                      if lang == "pt"
                      else f"  • {len(opps_no_amount)} open opportunities missing amount"))
    if opps_no_prob:
        lines.append((f"  • {len(opps_no_prob)} oportunidade(s) abertas sem probabilidade"
                      if lang == "pt"
                      else f"  • {len(opps_no_prob)} open opportunities missing probability"))
    lines.append("")
    lines.append("💡 Use `email do X é ...` ou `amount da opp X = ...` pra completar." if lang == "pt"
                 else "💡 Use `email of X is ...` or `amount of opp X = ...` to fill.")
    return IntentResult.ok(
        "\n".join(lines), intent="data_quality", confidence=0.94,
    )


def _handle_stats_by_owner(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Breakdown of open opportunities per owner (user)."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus, User
    lang = _detect_lang(text)
    opps = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
        )
    ).all()
    if not opps:
        return IntentResult.ok(
            "Pipeline vazio." if lang == "pt" else "Pipeline empty.",
            intent="stats_by_owner", confidence=0.9,
        )
    by_owner: dict[str, tuple[int, float]] = {}
    owner_ids = {o.owner_user_id for o in opps if o.owner_user_id}
    users = {u.id: u for u in ctx.session.exec(
        select(User).where(User.id.in_(owner_ids)) if owner_ids else select(User).where(User.id == None)
    ).all()}
    for o in opps:
        if o.owner_user_id and o.owner_user_id in users:
            u = users[o.owner_user_id]
            name = u.full_name or u.email or "?"
        else:
            name = ("Sem dono" if lang == "pt" else "No owner")
        cnt, tot = by_owner.get(name, (0, 0.0))
        by_owner[name] = (cnt + 1, tot + (o.amount or 0))

    header = "👥 Pipeline por dono:" if lang == "pt" else "👥 Pipeline by owner:"
    lines = [header]
    currency = "R$" if lang == "pt" else "$"
    # Sort by total desc
    for name, (cnt, tot) in sorted(by_owner.items(), key=lambda kv: -kv[1][1]):
        lines.append(f"  • {name}: {cnt} · {currency} {tot:,.0f}".replace(",", "."))
    return IntentResult.ok(
        "\n".join(lines), intent="stats_by_owner", confidence=0.94,
    )


def _handle_pipeline_health(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Overall pipeline health: open count, total value, avg age, stale count, avg probability."""
    from datetime import datetime, timezone, timedelta
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)
    open_opps = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
        )
    ).all()
    if not open_opps:
        return IntentResult.ok(
            "Pipeline vazio — hora de prospectar." if lang == "pt"
            else "Pipeline empty — time to prospect.",
            intent="pipeline_health", confidence=0.9,
        )
    total_value = sum((o.amount or 0) for o in open_opps)
    avg_prob = sum((o.probability or 0) for o in open_opps) / len(open_opps)
    weighted = sum((o.amount or 0) * (o.probability or 0) / 100 for o in open_opps)

    def days_since(dt):
        d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return (now - d).days

    ages = [days_since(o.updated_at) for o in open_opps]
    avg_age = sum(ages) / len(ages)
    stale_count = sum(1 for a in ages if a > 30)
    high_prob = sum(1 for o in open_opps if (o.probability or 0) >= 70)
    currency = "R$" if lang == "pt" else "$"

    lines = []
    tone = (snap.preferences or {}).get("tone", "formal")
    if tone == "casual":
        header = "🩺 Como tá o pipeline:" if lang == "pt" else "🩺 How's the pipeline:"
    elif tone == "concise":
        header = "🩺 Pipeline:"
    elif tone == "technical":
        header = "pipeline.health:"
    else:
        header = "🩺 Saúde do pipeline:" if lang == "pt" else "🩺 Pipeline health:"
    lines.append(header)
    lines.append(f"  {'Abertas' if lang == 'pt' else 'Open'}: {len(open_opps)}")
    lines.append(f"  {'Valor total' if lang == 'pt' else 'Total value'}: {currency} {total_value:,.0f}".replace(",", "."))
    lines.append(f"  {'Valor ponderado' if lang == 'pt' else 'Weighted value'}: {currency} {weighted:,.0f}".replace(",", "."))
    lines.append(f"  {'Probabilidade média' if lang == 'pt' else 'Avg probability'}: {int(avg_prob)}%")
    lines.append(f"  {'Idade média' if lang == 'pt' else 'Avg age'}: {int(avg_age)}d")
    lines.append(f"  {'Alta probabilidade (≥70%)' if lang == 'pt' else 'High-prob (≥70%)'}: {high_prob}")
    lines.append(f"  {'Paradas (>30d)' if lang == 'pt' else 'Stale (>30d)'}: {stale_count}")

    # Diagnosis
    diag = None
    if stale_count > len(open_opps) * 0.5:
        diag = ("⚠️ Mais da metade parada — reveja ou marque como perdida." if lang == "pt"
                else "⚠️ Over half stale — review or mark as lost.")
    elif high_prob == 0:
        diag = ("⚠️ Nenhuma com alta prob — trabalhe qualificação." if lang == "pt"
                else "⚠️ None high-prob — work on qualification.")
    elif avg_prob >= 60 and stale_count == 0:
        diag = ("🚀 Pipeline saudável — foque em fechar." if lang == "pt"
                else "🚀 Pipeline healthy — focus on closing.")
    if diag:
        lines.append("")
        lines.append(diag)

    return IntentResult.ok(
        "\n".join(lines), intent="pipeline_health", confidence=0.94,
    )


def _handle_hot_leads(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """List leads with score above a threshold (default 70)."""
    from sqlmodel import select
    from app.models import Lead
    lang = _detect_lang(text)
    m = re.search(r"(\d{1,3})", text)
    threshold = int(m.group(1)) if m else 70
    threshold = max(0, min(threshold, 100))
    leads = ctx.session.exec(
        select(Lead).where(
            Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
            Lead.score >= threshold,
        ).order_by(Lead.score.desc()).limit(10)
    ).all()
    if not leads:
        return IntentResult.ok(
            f"Nenhum lead com score ≥ {threshold}." if lang == "pt"
            else f"No leads with score ≥ {threshold}.",
            intent="hot_leads", confidence=0.9,
        )
    tone = (snap.preferences or {}).get("tone", "formal")
    if tone == "casual":
        header = f"🔥 Uns leads bem quentes (score ≥ {threshold}):" if lang == "pt" else f"🔥 Some hot leads (score ≥ {threshold}):"
    elif tone == "concise":
        header = f"🔥 Score ≥ {threshold}:"
    elif tone == "technical":
        header = f"leads[score>={threshold}]:"
    else:
        header = f"🔥 Leads quentes (score ≥ {threshold}):" if lang == "pt" else f"🔥 Hot leads (score ≥ {threshold}):"
    lines = [header]
    for lead in leads:
        full = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or lead.email or "?"
        parts = [f"{full}", f"score {int(lead.score or 0)}"]
        if lead.email:
            parts.append(lead.email)
        if getattr(lead, "company_name", None):
            parts.append(lead.company_name)
        lines.append("  • " + " — ".join(parts))
    return IntentResult.ok(
        "\n".join(lines), intent="hot_leads", confidence=0.94,
        tool_calls=[{"name": "recent_list", "kind": "lead",
                     "items": [{"id": str(l.id),
                                "name": f"{l.first_name or ''} {l.last_name or ''}".strip() or (l.email or '?')}
                               for l in leads]}],
    )


def _handle_momentum_check(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Compare this month's closed-won metrics against last month's."""
    from datetime import datetime, timezone
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)

    def month_range(year: int, month: int):
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        return start, end

    this_start, this_end = month_range(now.year, now.month)
    last_year, last_month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    last_start, last_end = month_range(last_year, last_month)

    def won_in(start, end):
        return ctx.session.exec(
            select(Opportunity).where(
                Opportunity.workspace_id == ctx.workspace_id,
                Opportunity.deleted_at.is_(None),
                Opportunity.status == OpportunityStatus.won,
                Opportunity.closed_at.is_not(None),
                Opportunity.closed_at >= start,
                Opportunity.closed_at < end,
            )
        ).all()

    this_won = won_in(this_start, this_end)
    last_won = won_in(last_start, last_end)
    this_count, last_count = len(this_won), len(last_won)
    this_amt = sum((o.amount or 0) for o in this_won)
    last_amt = sum((o.amount or 0) for o in last_won)

    def delta_pct(cur, prev):
        if prev == 0:
            return "∞" if cur > 0 else "0"
        pct = (cur - prev) / prev * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.0f}%"

    count_delta = delta_pct(this_count, last_count)
    amt_delta = delta_pct(this_amt, last_amt)
    trend = "📈" if this_amt >= last_amt else "📉"
    currency = "R$" if lang == "pt" else "$"

    tone = (snap.preferences or {}).get("tone", "formal")
    if lang == "pt":
        month_names = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
        cur_lbl = f"{month_names[now.month - 1]}/{now.year}"
        prev_lbl = f"{month_names[last_month - 1]}/{last_year}"
    else:
        cur_lbl = now.strftime('%b %Y')
        prev_lbl = last_start.strftime('%b %Y')
    if tone == "concise":
        header = f"{trend} {cur_lbl} vs {prev_lbl}:"
    elif tone == "technical":
        header = f"momentum[{cur_lbl}|{prev_lbl}] trend={trend}"
    elif tone == "casual":
        header = f"{trend} Como tá indo {cur_lbl} vs {prev_lbl}:" if lang == "pt" else f"{trend} How's {cur_lbl} vs {prev_lbl}:"
    else:
        header = f"{trend} Momentum — {cur_lbl} vs {prev_lbl}:"

    lines = [header]
    lines.append(f"  {'Ganhos' if lang == 'pt' else 'Wins'}: {this_count} ({count_delta} vs {last_count})")
    lines.append(f"  {'Receita' if lang == 'pt' else 'Revenue'}: {currency} {this_amt:,.0f} ({amt_delta} vs {currency} {last_amt:,.0f})".replace(",", "."))

    if this_count == 0 and last_count == 0:
        lines.append("")
        lines.append(("Nenhum fechamento em nenhum dos meses — priorize os deals maduros." if lang == "pt"
                      else "No closes in either month — prioritize mature deals."))
    elif this_amt > last_amt * 1.2:
        lines.append("")
        lines.append("🚀 Ótimo momento — mantenha o ritmo." if lang == "pt"
                     else "🚀 Great momentum — keep pushing.")
    elif last_amt > 0 and this_amt < last_amt * 0.7:
        lines.append("")
        lines.append("⚠️ Queda relevante — reveja oportunidades abertas." if lang == "pt"
                     else "⚠️ Notable drop — review open opportunities.")

    return IntentResult.ok(
        "\n".join(lines), intent="momentum_check", confidence=0.94,
    )


def _handle_stale_opportunities(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """List open opportunities that haven't been updated in N days (default 30)."""
    from datetime import datetime, timezone, timedelta
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    # Try to parse threshold from text ("30 dias", "60 days")
    m = re.search(r"(\d{1,3})\s*(?:d(?:ia)?s?|day)", text.lower())
    threshold_days = int(m.group(1)) if m else 30
    cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
    stmt = select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
        Opportunity.updated_at < cutoff,
    ).order_by(Opportunity.updated_at.asc()).limit(10)
    opps = ctx.session.exec(stmt).all()
    label = f"{threshold_days}d"
    if not opps:
        return IntentResult.ok(
            f"Nenhuma oportunidade parada há mais de {label}. 👍" if lang == "pt"
            else f"No opportunities stale for {label}+. 👍",
            intent="stale_opportunities", confidence=0.9,
        )
    now = datetime.now(timezone.utc)
    tone = (snap.preferences or {}).get("tone", "formal")
    if tone == "casual":
        header = f"⏰ Essas tão paradas há {label}:" if lang == "pt" else f"⏰ These have been idle {label}+:"
    elif tone == "concise":
        header = f"⏰ Paradas {label}+:" if lang == "pt" else f"⏰ Stale {label}+:"
    elif tone == "technical":
        header = f"opps.stale[>{label}]:"
    else:
        header = (f"⏰ Oportunidades paradas há mais de {label}:" if lang == "pt"
                  else f"⏰ Opportunities stale for {label}+:")
    lines = [header]
    for opp in opps:
        upd = opp.updated_at if opp.updated_at.tzinfo else opp.updated_at.replace(tzinfo=timezone.utc)
        days = (now - upd).days
        amt = (f"R$ {opp.amount:,.0f}".replace(",", ".") if lang == "pt"
               else f"${opp.amount:,.0f}") if opp.amount else "?"
        lines.append(f"  • {opp.name} — {amt} ({days}d {'sem update' if lang == 'pt' else 'idle'})")
    tip = ("💡 Reveja essas oportunidades ou marque como perdidas." if lang == "pt"
           else "💡 Review these or mark as lost.")
    lines.append("")
    lines.append(tip)
    return IntentResult.ok(
        "\n".join(lines), intent="stale_opportunities", confidence=0.94,
        tool_calls=[{"name": "recent_list", "kind": "opportunity",
                     "items": [{"id": str(o.id), "name": o.name} for o in opps]}],
    )


def _handle_daily_briefing(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Morning briefing: overdue tasks + today's meetings + top open opp + one action tip.

    A more compact, orientation-focused version of ``suggest_next_action``.
    """
    from datetime import datetime, timezone, timedelta
    from sqlmodel import select
    from app.models import Task, Meeting, Opportunity, TaskStatus, OpportunityStatus
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)
    day_end = now.replace(hour=23, minute=59, second=59)

    overdue = ctx.session.exec(
        select(Task).where(
            Task.workspace_id == ctx.workspace_id, Task.deleted_at.is_(None),
            Task.status != TaskStatus.done, Task.status != TaskStatus.cancelled,
            Task.due_at.is_not(None), Task.due_at < now,
        ).order_by(Task.due_at.asc()).limit(3)
    ).all()
    meetings_today = ctx.session.exec(
        select(Meeting).where(
            Meeting.workspace_id == ctx.workspace_id, Meeting.deleted_at.is_(None),
            Meeting.starts_at >= now, Meeting.starts_at <= day_end,
        ).order_by(Meeting.starts_at.asc()).limit(5)
    ).all()
    top_opps = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
        ).order_by(Opportunity.amount.desc().nulls_last()).limit(1)
    ).all()

    lines = []
    weekday_pt = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    tone = (snap.preferences or {}).get("tone", "formal")
    name = (snap.preferences or {}).get("preferred_name")
    salut = f", {name}" if name else ""
    if tone == "casual":
        if lang == "pt":
            lines.append(f"☀️ Bom dia{salut}! Segue o briefing de {weekday_pt[now.weekday()]} ({now.strftime('%d/%m')}):")
        else:
            lines.append(f"☀️ Morning{salut}! Here's the briefing for {now.strftime('%A, %b %d')}:")
    elif tone == "concise":
        if lang == "pt":
            lines.append(f"Briefing {now.strftime('%d/%m')}:")
        else:
            lines.append(f"Briefing {now.strftime('%b %d')}:")
    elif tone == "technical":
        if lang == "pt":
            lines.append(f"Briefing[{now.strftime('%Y-%m-%d')}] — {weekday_pt[now.weekday()]}")
        else:
            lines.append(f"Briefing[{now.strftime('%Y-%m-%d')}] — {now.strftime('%A')}")
    else:
        if lang == "pt":
            lines.append(f"☀️ Bom dia{salut}. Tomei a liberdade de preparar o briefing — {weekday_pt[now.weekday()]}, {now.strftime('%d/%m')}:")
        else:
            lines.append(f"☀️ Good morning{salut}. I've taken the liberty of preparing today's briefing — {now.strftime('%A, %b %d')}:")

    if overdue:
        lines.append("")
        lines.append(f"🔥 {'Tarefas atrasadas' if lang == 'pt' else 'Overdue tasks'} ({len(overdue)}):")
        for t in overdue:
            due = t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)
            d_days = (now - due).days
            lines.append(f"  • {t.title} ({d_days}d)")

    if meetings_today:
        lines.append("")
        lines.append(f"📅 {'Reuniões hoje' if lang == 'pt' else 'Meetings today'}:")
        for mt in meetings_today:
            starts = mt.starts_at if mt.starts_at.tzinfo else mt.starts_at.replace(tzinfo=timezone.utc)
            lines.append(f"  • {starts.strftime('%H:%M')} — {mt.title}")

    if top_opps:
        opp = top_opps[0]
        amt = f"R$ {opp.amount:,.0f}".replace(",", ".") if lang == "pt" else f"${opp.amount:,.0f}"
        lines.append("")
        header = "🎯 Foco de hoje" if lang == "pt" else "🎯 Today's focus"
        lines.append(f"{header}: \"{opp.name}\" ({amt}, {int(opp.probability or 0)}%)")

    if not overdue and not meetings_today and not top_opps:
        lines.append("")
        lines.append(("Sem pendências. Momento oportuno para prospectar." if lang == "pt"
                      else "Nothing pending. An opportune moment to prospect."))

    return IntentResult.ok(
        "\n".join(lines), intent="daily_briefing", confidence=0.94,
    )


def _handle_suggest_next_action(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Proactive agent: analyze workspace and hand back 3 concrete next actions.

    Unlike ``insights`` which surfaces abstract nudges, this returns
    entity-anchored steps a user can execute directly, e.g. "conclua tarefa X"
    or "agende follow-up com Y".
    """
    from datetime import datetime, timezone, timedelta
    from sqlmodel import select
    from app.models import Task, Opportunity, Contact, Lead, Meeting, TaskStatus, OpportunityStatus
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)
    actions: list[dict] = []

    # 1) Highest-priority overdue tasks (oldest first)
    overdue = ctx.session.exec(
        select(Task).where(
            Task.workspace_id == ctx.workspace_id,
            Task.deleted_at.is_(None),
            Task.status != TaskStatus.done,
            Task.due_at.is_not(None),
            Task.due_at < now,
        ).order_by(Task.due_at.asc()).limit(2)
    ).all()
    for t in overdue:
        due = t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=timezone.utc)
        days = (now - due).days
        actions.append({
            "kind": "task",
            "label": (f"Conclua tarefa \"{t.title}\" (atrasada {days}d)" if lang == "pt"
                      else f"Complete task \"{t.title}\" ({days}d overdue)"),
            "how": (f"digite: conclua \"{t.title}\"" if lang == "pt"
                    else f"type: complete \"{t.title}\""),
            "id": str(t.id),
        })

    # 2) High-value open opportunities in advanced stages with no recent activity
    open_opps = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
        ).order_by(Opportunity.amount.desc().nulls_last()).limit(3)
    ).all()
    for opp in open_opps[:2]:
        if len(actions) >= 3:
            break
        amount_str = f"R$ {opp.amount:,.0f}".replace(",", ".") if opp.amount else "?"
        if (opp.probability or 0) >= 60:
            actions.append({
                "kind": "opportunity",
                "label": (f"Feche \"{opp.name}\" — {amount_str}, {int(opp.probability or 0)}% de chance"
                          if lang == "pt"
                          else f"Close \"{opp.name}\" — {amount_str}, {int(opp.probability or 0)}% probability"),
                "how": (f"digite: ganhei \"{opp.name}\"" if lang == "pt"
                        else f"type: won \"{opp.name}\""),
                "id": str(opp.id),
            })
        else:
            actions.append({
                "kind": "opportunity",
                "label": (f"Faça follow-up em \"{opp.name}\" ({amount_str})" if lang == "pt"
                          else f"Follow up on \"{opp.name}\" ({amount_str})"),
                "how": (f"digite: agende reunião sobre \"{opp.name}\" amanhã 15h" if lang == "pt"
                        else f"type: schedule meeting about \"{opp.name}\" tomorrow 3pm"),
                "id": str(opp.id),
            })

    # 3) Stale leads (created >14 days ago, no updates) — re-engage
    if len(actions) < 3:
        cutoff = now - timedelta(days=14)
        stale_leads = ctx.session.exec(
            select(Lead).where(
                Lead.workspace_id == ctx.workspace_id,
                Lead.deleted_at.is_(None),
                Lead.created_at < cutoff,
            ).order_by(Lead.created_at.asc()).limit(1)
        ).all()
        for lead in stale_leads:
            days = (now - lead.created_at).days
            name = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or lead.email or "?"
            actions.append({
                "kind": "lead",
                "label": (f"Re-engaje lead \"{name}\" (sem contato há {days}d)" if lang == "pt"
                          else f"Re-engage lead \"{name}\" ({days}d silent)"),
                "how": (f"digite: nota no lead {name}: novo tentativa de contato" if lang == "pt"
                        else f"type: note on lead {name}: new outreach"),
                "id": str(lead.id),
            })

    # 4) Fallback: no open opps, no overdue → suggest prospecting
    if not actions:
        counts = ctx.session.exec(select(Contact).where(
            Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
        )).all()
        if not counts:
            actions.append({
                "kind": "empty",
                "label": ("Comece pelo básico: cadastre seu primeiro contato" if lang == "pt"
                          else "Start with the basics: add your first contact"),
                "how": ("digite: novo contato: Nome Sobrenome" if lang == "pt"
                        else "type: new contact: First Last"),
            })
        else:
            actions.append({
                "kind": "empty",
                "label": ("Pipeline saudável — sem ações urgentes" if lang == "pt"
                          else "Pipeline healthy — no urgent actions"),
                "how": ("digite: seed dados de exemplo (pra explorar)" if lang == "pt"
                        else "type: seed demo data (to explore)"),
            })

    tone = (snap.preferences or {}).get("tone", "formal")
    name = (snap.preferences or {}).get("preferred_name")
    salut = f", {name}" if name else ""
    if tone == "casual":
        header = f"🎯 Aqui vão 3 pra hoje{salut}:" if lang == "pt" else f"🎯 3 for today{salut}:"
    elif tone == "concise":
        header = "🎯 Top 3:" if lang == "pt" else "🎯 Top 3:"
    elif tone == "technical":
        header = "priorities[3]:" if lang == "pt" else "priorities[3]:"
    else:
        header = f"🎯 Identifiquei 3 prioridades{salut}:" if lang == "pt" else f"🎯 I've identified 3 priorities{salut}:"
    body_lines = [header]
    for i, a in enumerate(actions[:3], 1):
        body_lines.append(f"  {i}. {a['label']}")
        body_lines.append(f"     → {a['how']}")
    reply = "\n".join(body_lines)
    return IntentResult.ok(
        reply, intent="suggest_next_action", confidence=0.92,
        tool_calls=[{"name": "recent_list", "kind": "action",
                     "items": [{"id": a.get("id"), "name": a["label"]} for a in actions[:3]]}],
    )


_SCHEDULE_MEETING_RE = re.compile(
    r"^(?:agende?|marque?|marca|schedule|book|create)\s+(?:uma?\s+|a\s+|an\s+)?(?:reuni[ãa]o|meeting|call|encontro)\s+"
    r"(?:(?:com|with)\s+(?P<who>[^,]+?)\s+)?"
    r"(?:(?:sobre|about)\s+(?P<topic>[^,]+?)\s+)?"
    r"(?:para|em|for|at|on|[àa]s?|na?|pr[óo]xim[oa])\s+(?P<when>.+)$",
    re.IGNORECASE,
)

# Fallback: no preposition (implicit "when" — e.g., "agende reunião com Ada amanha 15h")
_SCHEDULE_MEETING_LOOSE_RE = re.compile(
    r"^(?:agende?|marque?|marca|schedule|book|create)\s+(?:uma?\s+|a\s+|an\s+)?(?:reuni[ãa]o|meeting|call|encontro)\s+"
    r"(?:(?:com|with)\s+(?P<who>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-'\.]*(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-'\.]*)?)\s+)?"
    # Explicit date/time trigger words to anchor the when clause
    r"(?P<when>(?:hoje|amanh[ãa]|amanha|tonight|today|tomorrow|next\s+\S+|pr[óo]xim[oa]\s+\S+|seg(?:unda)?|ter(?:[cç]a)?|qua(?:rta)?|qui(?:nta)?|sex(?:ta)?|s[áa]b(?:ado)?|dom(?:ingo)?|mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}[:h/-]\d{0,2}\S*|\d{1,2}\s*(?:am|pm|h)).*)$",
    re.IGNORECASE,
)

# Time/date tail markers that must be stripped from `who` — the schedule regex
# is non-greedy but has no way to know that "tomorrow", "hoje", etc. belong to
# the temporal segment, not the name.
_WHO_TAIL_STRIP_RE = re.compile(
    r"\s+(?:tomorrow|today|tonight|hoje|amanh[ãa]|amanha|"
    r"seg(?:unda)?|ter(?:ca|ça|cça)?|qua(?:rta)?|qui(?:nta)?|sex(?:ta)?|s[áa]b(?:ado)?|dom(?:ingo)?|"
    r"mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?|"
    r"pr[óo]xima|next|semana|week)"
    r"(?:\s+.*)?$",
    re.IGNORECASE,
)




_DELETE_TASK_RE = re.compile(
    r"^(?:apague?|delete|remova|remove|excluir)\s+(?:a\s+|the\s+)?(?:tarefa|task)\s+(?P<title>.+)$",
    re.IGNORECASE,
)
_MARK_OPP_RE = re.compile(
    r"^(?:marque?|mark|mova?|move|set)\s+(?:a\s+|the\s+)?(?:oportunidade|opportunity|opp|deal|neg[oó]cio)\s+"
    r"(?P<name>.+?)\s+(?:como|as|for|to)\s+"
    r"(?P<status>won|ganhad?a?|ganho|lost|perdid?a?|perdeu)\s*[?!.]?\s*$",
    re.IGNORECASE,
)
# Shortcut: "ganhei X" / "perdi X" / "won X" / "lost X" (X = opportunity name).
# Guards against matching phrases like "won this month" / "lost opportunities".
_MARK_OPP_SHORT_RE = re.compile(
    r"^(?P<status>ganhei|perdi|won|lost)\s+(?:o\s+|a\s+|the\s+)?"
    r"(?!(?:this|last|these|those|opportunit(?:y|ies)|deals?|oportunidades?|neg[óo]cios?|opps?|quanto|much|m[êe]s|semana|ano|month|week|year)\b)"
    r"(?P<name>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)


_DELETE_ENTITY_RE = re.compile(
    r"^(?:apague?|delete|remova|remove|excluir)\s+(?:o\s+|a\s+|the\s+)?"
    r"(?P<kind>contato|contact|empresa|company|oportunidade|opportunity|opp|deal|lead)\s+"
    r"(?P<name>.+)$",
    re.IGNORECASE,
)

_ENTITY_MAP = {
    "contato": "contact", "contact": "contact",
    "empresa": "company", "company": "company",
    "oportunidade": "opportunity", "opportunity": "opportunity", "opp": "opportunity", "deal": "opportunity",
    "lead": "lead",
}


def _handle_delete_entity(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    from sqlmodel import select, or_
    from datetime import datetime, timezone
    from app.models import Contact, Company, Opportunity, Lead
    from app.services.crud import like_escape
    m = _DELETE_ENTITY_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    kind = _ENTITY_MAP[m.group("kind").lower()]
    name = m.group("name").strip().rstrip("?.!").strip('"\'')
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"

    MODEL_MAP = {
        "contact": (Contact, [Contact.first_name, Contact.last_name, Contact.email]),
        "company": (Company, [Company.name, Company.domain]),
        "opportunity": (Opportunity, [Opportunity.name]),
        "lead": (Lead, [Lead.first_name, Lead.last_name, Lead.email, Lead.company_name]),
    }
    model, name_cols = MODEL_MAP[kind]
    conds = or_(*[c.ilike(like, escape="\\") for c in name_cols])
    obj = ctx.session.exec(
        select(model).where(
            model.workspace_id == ctx.workspace_id,
            model.deleted_at.is_(None),
            conds,
        ).limit(1)
    ).first()
    if obj is None:
        label = {"contact": "contato", "company": "empresa", "opportunity": "oportunidade", "lead": "lead"}[kind] if lang == "pt" else kind
        return IntentResult.ok(
            f"Não encontrei {label} com '{name}'." if lang == "pt" else f"No {label} matching '{name}'.",
            intent=f"delete_{kind}", confidence=0.85,
        )
    obj.deleted_at = datetime.now(timezone.utc)
    ctx.session.add(obj)
    ctx.session.commit()
    ctx.session.refresh(obj)
    label = getattr(obj, "name", None) or f"{getattr(obj, 'first_name', '') or ''} {getattr(obj, 'last_name', '') or ''}".strip() or "?"
    return IntentResult.ok(
        f"🗑 {kind.capitalize()} \"{label}\" apagado(a)." if lang == "pt" else f"🗑 {kind.capitalize()} \"{label}\" deleted.",
        intent=f"delete_{kind}", confidence=0.94,
        tool_calls=[{"name": f"delete_{kind}", "input": {"name": name}, "result": {"id": str(obj.id)}}],
    )


_DELETE_BARE_RE = re.compile(
    r"^(?:apague?|apagar|delete|remova|remover?|excluir?|drop)\s+"
    r"(?:o\s+|a\s+|the\s+)?"
    r"(?!(?:contato|contact|empresa|company|oportunidade|opportunity|opp|deal|neg[óo]cio|lead|task|tarefa|nota|note|all|tudo|todos?|todas?|every|everything)\b)"
    r"(?P<name>.+?)\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_delete_bare(intent: Intent, text: str, snap: WorkspaceSnapshot, ctx: ToolContext) -> IntentResult:
    """Delete an entity by bare name — search across all kinds and disambiguate."""
    from sqlmodel import select, or_
    from datetime import datetime, timezone
    from app.models import Contact, Company, Opportunity, Lead
    from app.services.crud import like_escape
    m = _DELETE_BARE_RE.match(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().strip("\"'").rstrip(".!?")
    lang = _detect_lang(text)
    if not name or len(name) < 2 or not re.search(r"\w", name):
        return IntentResult(handled=False)
    like = f"%{like_escape(name)}%"
    matches: list[tuple[str, object, str]] = []  # (kind, obj, display_name)
    # Split multi-word name for better matching (e.g., "Alice Silva" → first=Alice, last=Silva)
    tokens = [t for t in name.split() if t]
    contact_conds = [
        Contact.first_name.ilike(like, escape="\\"),
        Contact.last_name.ilike(like, escape="\\"),
        Contact.email.ilike(like, escape="\\"),
    ]
    if len(tokens) >= 2:
        from sqlmodel import and_
        contact_conds.append(and_(
            Contact.first_name.ilike(f"%{like_escape(tokens[0])}%", escape="\\"),
            Contact.last_name.ilike(f"%{like_escape(tokens[-1])}%", escape="\\"),
        ))
    # Contacts
    for c in ctx.session.exec(
        select(Contact).where(
            Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
            or_(*contact_conds),
        ).limit(5)
    ).all():
        matches.append(("contact", c, f"{c.first_name} {c.last_name or ''}".strip()))
    # Companies
    for co in ctx.session.exec(
        select(Company).where(
            Company.workspace_id == ctx.workspace_id, Company.deleted_at.is_(None),
            or_(Company.name.ilike(like, escape="\\"), Company.domain.ilike(like, escape="\\")),
        ).limit(5)
    ).all():
        matches.append(("company", co, co.name))
    # Opportunities
    for o in ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
            Opportunity.name.ilike(like, escape="\\"),
        ).limit(5)
    ).all():
        matches.append(("opportunity", o, o.name))
    # Leads
    for l in ctx.session.exec(
        select(Lead).where(
            Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
            or_(Lead.first_name.ilike(like, escape="\\"),
                Lead.last_name.ilike(like, escape="\\"),
                Lead.email.ilike(like, escape="\\")),
        ).limit(5)
    ).all():
        matches.append(("lead", l, f"{l.first_name} {l.last_name or ''}".strip()))

    if not matches:
        return IntentResult.ok(
            f"Nada encontrado para \"{name}\"." if lang == "pt" else f"Nothing matching \"{name}\".",
            intent="delete_bare", confidence=0.7,
        )
    if len(matches) == 1:
        kind, obj, disp = matches[0]
        obj.deleted_at = datetime.now(timezone.utc)
        ctx.session.add(obj)
        ctx.session.commit()
        return IntentResult.ok(
            f"🗑 {kind.capitalize()} \"{disp}\" apagado." if lang == "pt" else f"🗑 {kind.capitalize()} \"{disp}\" deleted.",
            intent=f"delete_{kind}", confidence=0.94,
            tool_calls=[{"name": f"delete_{kind}", "input": {"name": name}, "result": {"id": str(obj.id)}}],
        )
    # Multiple matches — disambiguate
    if lang == "pt":
        header = f"\"{name}\" bate com {len(matches)} itens. Seja específico:"
        kind_pt = {"contact": "contato", "company": "empresa", "opportunity": "oportunidade", "lead": "lead"}
        lines = [header]
        for kind, _, disp in matches:
            lines.append(f"  • apague {kind_pt[kind]} {disp}")
    else:
        header = f"\"{name}\" matches {len(matches)} items. Be specific:"
        lines = [header]
        for kind, _, disp in matches:
            lines.append(f"  • delete {kind} {disp}")
    return IntentResult.ok(
        "\n".join(lines), intent="delete_bare", confidence=0.8,
        tool_calls=[{
            "name": "ambiguity", "kind": "delete_choice",
            "original_message": text,
            "options": [{"kind": k, "id": str(o.id), "name": d} for k, o, d in matches],
        }],
    )


_SNOOZE_TASK_RE = re.compile(
    r"^(?:snooze|adie?|posterguer?|adiar|reagende?)\s+(?:a\s+|the\s+)?(?:tarefa|task)\s+(?P<title>.+?)\s+"
    r"(?:por|for|by|em)\s+(?P<n>\d+)\s*(?:dias?|days?|d)\s*[?!.]?\s*$",
    re.IGNORECASE,
)


def _handle_snooze_task(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    from sqlmodel import select
    from datetime import datetime, timezone, timedelta
    from app.models import Task
    from app.services.crud import like_escape
    m = _SNOOZE_TASK_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    title = m.group("title").strip().strip("\"'")
    days = min(int(m.group("n")), 365)
    lang = _detect_lang(text)
    like = f"%{like_escape(title)}%"
    task = ctx.session.exec(select(Task).where(
        Task.workspace_id == ctx.workspace_id,
        Task.deleted_at.is_(None),
        Task.title.ilike(like, escape="\\"),
    ).limit(1)).first()
    if task is None:
        return IntentResult.ok(
            f"Não encontrei tarefa com '{title}'." if lang == "pt" else f"No task matching '{title}'.",
            intent="snooze_task", confidence=0.8,
        )
    base = task.due_at
    if base is None or (base if base.tzinfo else base.replace(tzinfo=timezone.utc)) < datetime.now(timezone.utc):
        base = datetime.now(timezone.utc)
    else:
        base = base if base.tzinfo else base.replace(tzinfo=timezone.utc)
    task.due_at = base + timedelta(days=days)
    ctx.session.add(task)
    ctx.session.commit()
    ctx.session.refresh(task)
    when = task.due_at.strftime("%Y-%m-%d %H:%M")
    return IntentResult.ok(
        f"⏰ \"{task.title}\" adiada por {days}d → {when}" if lang == "pt" else f"⏰ \"{task.title}\" snoozed {days}d → {when}",
        intent="snooze_task", confidence=0.93,
        tool_calls=[{"name": "snooze_task", "input": {"title": title, "days": days}, "result": {"id": str(task.id), "new_due_at": task.due_at.isoformat()}}],
    )


def _handle_delete_task(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    from sqlmodel import select
    from datetime import datetime, timezone
    from app.models import Task
    from app.services.crud import like_escape
    m = _DELETE_TASK_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    title = m.group("title").strip().rstrip("?.!").strip('"\'')
    lang = _detect_lang(text)
    like = f"%{like_escape(title)}%"
    task = ctx.session.exec(
        select(Task).where(
            Task.workspace_id == ctx.workspace_id,
            Task.deleted_at.is_(None),
            Task.title.ilike(like, escape="\\"),
        ).limit(1)
    ).first()
    if task is None:
        return IntentResult.ok(
            f"Não encontrei tarefa com '{title}'." if lang == "pt" else f"No task matching '{title}'.",
            intent="delete_task", confidence=0.8,
        )
    task.deleted_at = datetime.now(timezone.utc)
    ctx.session.add(task)
    ctx.session.commit()
    return IntentResult.ok(
        f"🗑 Tarefa \"{task.title}\" apagada." if lang == "pt" else f"🗑 Task \"{task.title}\" deleted.",
        intent="delete_task", confidence=0.94,
        tool_calls=[{"name": "delete_task", "input": {"title": title}, "result": {"id": str(task.id)}}],
    )


_BRIEF_OPP_RE = re.compile(
    r"^(?:brief|resumo|resumir|sum(?:m)?arize|briefing)\s+(?:opp|deal|oportunidade|neg[oó]cio)\s+(?P<name>.+)$",
    re.IGNORECASE,
)


_BRIEF_COMPANY_RE = re.compile(
    r"^(?:brief|resumo|resumir|sum(?:m)?arize|briefing)\s+(?:empresa|company|companhia)\s+(?P<name>.+)$",
    re.IGNORECASE,
)
_BRIEF_LEAD_RE = re.compile(
    r"^(?:brief|resumo|resumir|sum(?:m)?arize|briefing)\s+(?:lead)\s+(?P<name>.+)$",
    re.IGNORECASE,
)
_BRIEF_CONTACT_RE = re.compile(
    r"^(?:brief|resumo|resumir|sum(?:m)?arize|briefing)\s+(?:contato|contact)\s+(?P<name>.+)$",
    re.IGNORECASE,
)


def _handle_brief_company(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    from sqlmodel import select
    from datetime import datetime, timezone
    from app.models import Company, Contact, Opportunity, OpportunityStatus, Activity
    from app.services.crud import like_escape
    m = _BRIEF_COMPANY_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().rstrip("?.!").strip('"\'')
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"
    co = ctx.session.exec(select(Company).where(
        Company.workspace_id == ctx.workspace_id, Company.deleted_at.is_(None),
        Company.name.ilike(like, escape="\\"),
    ).limit(1)).first()
    if co is None:
        return IntentResult.ok(
            f"Não encontrei empresa com '{name}'." if lang == "pt" else f"No company matching '{name}'.",
            intent="brief_company", confidence=0.85,
        )
    contacts = list(ctx.session.exec(select(Contact).where(
        Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None),
        Contact.company_id == co.id,
    )).all())
    # Opportunities linked via contact
    opp_ids = set()
    for c in contacts:
        ops = list(ctx.session.exec(select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
        )).all())
        for o in ops:
            opp_ids.add(o.id)
    ops_all = list(ctx.session.exec(select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
    )).all())
    open_val = sum((o.amount or 0) for o in ops_all if o.status == OpportunityStatus.open)
    won_val = sum((o.amount or 0) for o in ops_all if o.status == OpportunityStatus.won)

    last_act = ctx.session.exec(select(Activity).where(
        Activity.workspace_id == ctx.workspace_id,
        Activity.subject_type == "company", Activity.subject_id == co.id,
    ).order_by(Activity.occurred_at.desc()).limit(1)).first()
    days_since = ""
    if last_act:
        occ = last_act.occurred_at if last_act.occurred_at.tzinfo else last_act.occurred_at.replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - occ).days

    if lang == "pt":
        lines = [
            f"🏢 **{co.name}**",
            f"Domínio: {co.domain or '?'} · Indústria: {co.industry or '?'}",
            f"Website: {co.website or '?'}",
            f"Contatos: {len(contacts)}",
            f"Última atividade: {days_since if days_since != '' else 'sem histórico'}{'d atrás' if days_since != '' else ''}",
            "",
            f"➡ **Ação sugerida**: {'Ligar hoje — sem toque recente' if days_since != '' and days_since > 30 else 'Nutrir contato regular'}",
        ]
    else:
        lines = [
            f"🏢 **{co.name}**",
            f"Domain: {co.domain or '?'} · Industry: {co.industry or '?'}",
            f"Website: {co.website or '?'}",
            f"Contacts: {len(contacts)}",
            f"Last activity: {days_since if days_since != '' else 'none'}{'d ago' if days_since != '' else ''}",
            "",
            f"➡ **Suggested action**: {'Call today — no recent touch' if days_since != '' and days_since > 30 else 'Regular nurture'}",
        ]
    return IntentResult.ok(
        "\n".join(lines), intent="brief_company", confidence=0.93,
        tool_calls=[{"name": "brief_company", "input": {"name": name}, "result": {"company_id": str(co.id)}}],
    )


def _handle_brief_lead(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    from sqlmodel import select, or_
    from datetime import datetime, timezone
    from app.models import Lead, Activity
    from app.services.crud import like_escape
    m = _BRIEF_LEAD_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().rstrip("?.!").strip('"\'')
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"
    lead = ctx.session.exec(select(Lead).where(
        Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
        or_(Lead.first_name.ilike(like, escape="\\"), Lead.last_name.ilike(like, escape="\\"),
            Lead.email.ilike(like, escape="\\"), Lead.company_name.ilike(like, escape="\\")),
    ).limit(1)).first()
    if lead is None:
        return IntentResult.ok(
            f"Não encontrei lead com '{name}'." if lang == "pt" else f"No lead matching '{name}'.",
            intent="brief_lead", confidence=0.85,
        )
    last_act = ctx.session.exec(select(Activity).where(
        Activity.workspace_id == ctx.workspace_id,
        Activity.subject_type == "lead", Activity.subject_id == lead.id,
    ).order_by(Activity.occurred_at.desc()).limit(1)).first()
    days_since = ""
    if last_act:
        occ = last_act.occurred_at if last_act.occurred_at.tzinfo else last_act.occurred_at.replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - occ).days
    full = f"{lead.first_name} {lead.last_name or ''}".strip()
    if lang == "pt":
        lines = [
            f"🎯 **{full}**",
            f"Empresa: {lead.company_name or '?'} · Fonte: {lead.source or '?'}",
            f"Email: {lead.email or '?'} · Score: **{lead.score}**",
            f"Status: {lead.status.value if hasattr(lead.status, 'value') else lead.status}",
            f"Última atividade: {days_since if days_since != '' else 'sem histórico'}{'d atrás' if days_since != '' else ''}",
            "",
            f"➡ **Próximo passo**: {'🔥 Alta pontuação — qualifique agora' if lead.score >= 50 else '📞 Prospecção / follow-up'}",
        ]
    else:
        lines = [
            f"🎯 **{full}**",
            f"Company: {lead.company_name or '?'} · Source: {lead.source or '?'}",
            f"Email: {lead.email or '?'} · Score: **{lead.score}**",
            f"Status: {lead.status.value if hasattr(lead.status, 'value') else lead.status}",
            f"Last activity: {days_since if days_since != '' else 'none'}{'d ago' if days_since != '' else ''}",
            "",
            f"➡ **Next step**: {'🔥 High score — qualify now' if lead.score >= 50 else '📞 Prospect / follow-up'}",
        ]
    return IntentResult.ok(
        "\n".join(lines), intent="brief_lead", confidence=0.93,
        tool_calls=[{"name": "brief_lead", "input": {"name": name}, "result": {"lead_id": str(lead.id)}}],
    )


def _handle_brief_opp(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Executive brief on one opportunity — 8-line summary with next-step suggestion."""
    from sqlmodel import select
    from datetime import datetime, timezone
    from app.models import Opportunity, PipelineStage, Contact, Activity, Note
    from app.services.crud import like_escape
    m = _BRIEF_OPP_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().rstrip("?.!").strip('"\'')
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"
    opp = ctx.session.exec(select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
        Opportunity.name.ilike(like, escape="\\"),
    ).limit(1)).first()
    if opp is None:
        return IntentResult.ok(
            f"Não encontrei oportunidade com '{name}'." if lang == "pt" else f"No opportunity matching '{name}'.",
            intent="brief_opp", confidence=0.85,
        )
    stage_name = ""
    if opp.stage_id:
        st = ctx.session.exec(select(PipelineStage).where(PipelineStage.id == opp.stage_id)).first()
        stage_name = st.name if st else ""
    # Related contact (via any Task or Activity)
    last_act = ctx.session.exec(select(Activity).where(
        Activity.workspace_id == ctx.workspace_id,
        Activity.subject_type == "opportunity", Activity.subject_id == opp.id,
    ).order_by(Activity.occurred_at.desc()).limit(1)).first()
    days_since = ""
    if last_act:
        occ = last_act.occurred_at if last_act.occurred_at.tzinfo else last_act.occurred_at.replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - occ).days
    note_count = len(ctx.session.exec(select(Note).where(
        Note.workspace_id == ctx.workspace_id, Note.related_opportunity_id == opp.id,
        Note.deleted_at.is_(None),
    )).all())
    weighted = (opp.amount or 0) * ((opp.probability or 0) / 100.0)

    # Suggest next step
    if opp.status.value == "won":
        suggestion = "🏆 Ganha — envie agradecimento + onboarding" if lang == "pt" else "🏆 Won — send thank-you + start onboarding"
    elif opp.status.value == "lost":
        suggestion = "💔 Perdida — nota de motivo para pipeline futuro" if lang == "pt" else "💔 Lost — note the reason for future pipeline"
    elif days_since != "" and days_since > 14:
        suggestion = f"⏰ Sem toque há {days_since}d — considere ligar hoje" if lang == "pt" else f"⏰ No touch in {days_since}d — consider calling today"
    elif (opp.probability or 0) >= 70:
        suggestion = "🔥 Alta probabilidade — pressione para fechamento" if lang == "pt" else "🔥 High probability — push to close"
    else:
        suggestion = "📞 Continue nutrindo com contatos regulares" if lang == "pt" else "📞 Keep nurturing with regular touches"

    if lang == "pt":
        lines = [
            f"💼 **{opp.name}**",
            f"Estágio: {stage_name or '?'} · Status: {opp.status.value}",
            f"Valor: {opp.currency} {(opp.amount or 0):,.0f} · Probabilidade: {int(opp.probability or 0)}%",
            f"Ponderado: {opp.currency} {weighted:,.0f}",
            f"Fechamento esperado: {opp.expected_close_date or '?'}",
            f"Notas: {note_count} · Última atividade: {days_since if days_since != '' else '?'}d atrás",
            "",
            f"➡ **Próximo passo**: {suggestion}",
        ]
    else:
        lines = [
            f"💼 **{opp.name}**",
            f"Stage: {stage_name or '?'} · Status: {opp.status.value}",
            f"Value: {opp.currency} {(opp.amount or 0):,.0f} · Probability: {int(opp.probability or 0)}%",
            f"Weighted: {opp.currency} {weighted:,.0f}",
            f"Expected close: {opp.expected_close_date or '?'}",
            f"Notes: {note_count} · Last activity: {days_since if days_since != '' else '?'}d ago",
            "",
            f"➡ **Next step**: {suggestion}",
        ]
    return IntentResult.ok(
        "\n".join(lines), intent="brief_opp", confidence=0.94,
        tool_calls=[{"name": "brief_opp", "input": {"name": name}, "result": {"opp_id": str(opp.id)}}],
    )


def _handle_close_stale_opps(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Mark all open opportunities untouched for N days as lost."""
    from sqlmodel import select
    from datetime import datetime, timezone, timedelta
    from app.models import Opportunity, OpportunityStatus, Activity, Pipeline, PipelineStage
    lang = _detect_lang(text)
    m = re.search(r"\b(\d+)\s*(days?|dias?)\b", text, re.IGNORECASE)
    n_days = int(m.group(1)) if m else 60
    cutoff = datetime.now(timezone.utc) - timedelta(days=n_days)

    open_opps = list(ctx.session.exec(select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open,
    )).all())

    def last_touch(opp):
        act = ctx.session.exec(
            select(Activity).where(
                Activity.workspace_id == ctx.workspace_id,
                Activity.subject_type == "opportunity",
                Activity.subject_id == opp.id,
            ).order_by(Activity.occurred_at.desc()).limit(1)
        ).first()
        if act:
            occ = act.occurred_at
            return occ if occ.tzinfo else occ.replace(tzinfo=timezone.utc)
        upd = opp.updated_at or opp.created_at
        return upd if upd and upd.tzinfo else (upd.replace(tzinfo=timezone.utc) if upd else datetime.now(timezone.utc))

    pipeline = ctx.session.exec(select(Pipeline).where(
        Pipeline.workspace_id == ctx.workspace_id, Pipeline.deleted_at.is_(None), Pipeline.is_default.is_(True),
    )).first()
    stages = list(ctx.session.exec(select(PipelineStage).where(
        PipelineStage.pipeline_id == pipeline.id if pipeline else False
    )).all()) if pipeline else []
    lost_stage = next((s for s in stages if s.is_lost), None)

    closed = 0
    now = datetime.now(timezone.utc)
    total_amt = 0.0
    for opp in open_opps:
        if last_touch(opp) < cutoff:
            opp.status = OpportunityStatus.lost
            opp.probability = 0.0
            opp.closed_at = now
            if lost_stage:
                opp.stage_id = lost_stage.id
            ctx.session.add(opp)
            closed += 1
            total_amt += opp.amount or 0
    if closed:
        ctx.session.commit()

    if lang == "pt":
        reply = f"✅ {closed} oportunidade(s) sem toque há mais de {n_days} dias marcada(s) como perdida(s)" + (f" (total $ {total_amt:,.0f})." if closed else ".")
    else:
        reply = f"✅ {closed} opportunit{'y' if closed == 1 else 'ies'} stale for over {n_days} days marked as lost" + (f" (total $ {total_amt:,.0f})." if closed else ".")
    return IntentResult.ok(
        reply, intent="close_stale_opportunities", confidence=0.93,
        tool_calls=[{"name": "close_stale_opportunities", "input": {"days": n_days}, "result": {"closed": closed, "total_amt": total_amt}}],
    )


def _handle_plan_week(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Produce a compact weekly plan: tasks due, meetings, opps closing, suggested focus."""
    from sqlmodel import select
    from datetime import datetime, timezone, timedelta
    from app.models import Task, TaskStatus, Meeting, Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=7)

    tasks = list(ctx.session.exec(select(Task).where(
        Task.workspace_id == ctx.workspace_id, Task.deleted_at.is_(None),
        Task.status.in_([TaskStatus.todo, TaskStatus.in_progress]),
        Task.due_at.is_not(None),
    )).all())
    def _as_aware(dt):
        if dt is None: return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    tasks_week = sorted(
        [tk for tk in tasks if _as_aware(tk.due_at) and _as_aware(tk.due_at) <= end],
        key=lambda t: t.due_at,
    )[:10]
    meetings = list(ctx.session.exec(select(Meeting).where(
        Meeting.workspace_id == ctx.workspace_id, Meeting.deleted_at.is_(None),
        Meeting.starts_at >= now, Meeting.starts_at <= end,
    ).order_by(Meeting.starts_at.asc()).limit(10)).all())
    closing = list(ctx.session.exec(select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id, Opportunity.deleted_at.is_(None),
        Opportunity.status == OpportunityStatus.open, Opportunity.expected_close_date.is_not(None),
    )).all())
    closing_week = sorted(
        [o for o in closing if o.expected_close_date and _as_aware(o.expected_close_date) <= end],
        key=lambda o: o.expected_close_date,
    )[:10]
    total_pipeline = sum(o.amount or 0 for o in closing_week)

    if lang == "pt":
        lines = ["📆 Plano da semana:", ""]
        lines.append(f"🎯 Foco sugerido: {'Fechar as ' + str(len(closing_week)) + ' oportunidades acima' if closing_week else 'Prospecção + tarefas atrasadas'}")
        lines.append(f"💰 Pipeline fechando: {len(closing_week)} deals · $ {total_pipeline:,.0f}")
        lines.append(f"📅 Reuniões: {len(meetings)}")
        lines.append(f"✓ Tarefas com prazo: {len(tasks_week)}")
    else:
        lines = ["📆 Weekly plan:", ""]
        lines.append(f"🎯 Suggested focus: {'Close the ' + str(len(closing_week)) + ' opps above' if closing_week else 'Prospect + overdue tasks'}")
        lines.append(f"💰 Pipeline closing: {len(closing_week)} deals · $ {total_pipeline:,.0f}")
        lines.append(f"📅 Meetings: {len(meetings)}")
        lines.append(f"✓ Tasks due: {len(tasks_week)}")

    if closing_week:
        lines.append("")
        lines.append("💼 Fechando esta semana:" if lang == "pt" else "💼 Closing this week:")
        for o in closing_week[:5]:
            when = o.expected_close_date.strftime("%d/%m") if lang == "pt" else o.expected_close_date.strftime("%b %d")
            lines.append(f"  • {o.name} — $ {o.amount or 0:,.0f} — {when}")

    if tasks_week:
        lines.append("")
        lines.append("✓ Próximas tarefas:" if lang == "pt" else "✓ Upcoming tasks:")
        for tk in tasks_week[:5]:
            when = tk.due_at.strftime("%d/%m %H:%M") if lang == "pt" else tk.due_at.strftime("%b %d %H:%M")
            lines.append(f"  • {tk.title} — {when}")

    return IntentResult.ok(
        "\n".join(lines), intent="plan_week", confidence=0.93,
        tool_calls=[{"name": "plan_week", "result": {"tasks": len(tasks_week), "meetings": len(meetings), "closing": len(closing_week)}}],
    )


def _handle_mark_opportunity(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    from sqlmodel import select
    from datetime import datetime, timezone
    from app.models import Opportunity, OpportunityStatus, Pipeline, PipelineStage
    from app.services.crud import like_escape
    m = _MARK_OPP_RE.search(text.strip()) or _MARK_OPP_SHORT_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().rstrip("?.!").strip('"\'')
    status_word = m.group("status").lower()
    is_won = status_word.startswith("w") or status_word.startswith("gan")
    lang = _detect_lang(text)
    like = f"%{like_escape(name)}%"
    opp = ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.name.ilike(like, escape="\\"),
        ).limit(1)
    ).first()
    if opp is None:
        return IntentResult.ok(
            f"Não encontrei oportunidade com '{name}'." if lang == "pt" else f"No opportunity matching '{name}'.",
            intent="mark_opportunity", confidence=0.8,
        )
    # Move to the terminal stage of the default pipeline
    pipeline = ctx.session.exec(select(Pipeline).where(
        Pipeline.workspace_id == ctx.workspace_id, Pipeline.deleted_at.is_(None), Pipeline.is_default.is_(True),
    )).first()
    stages = ctx.session.exec(select(PipelineStage).where(
        PipelineStage.pipeline_id == pipeline.id if pipeline else False
    )).all() if pipeline else []
    terminal_stage = next((s for s in stages if (s.is_won if is_won else s.is_lost)), None)
    if terminal_stage:
        opp.stage_id = terminal_stage.id
    opp.status = OpportunityStatus.won if is_won else OpportunityStatus.lost
    opp.probability = 100.0 if is_won else 0.0
    opp.closed_at = datetime.now(timezone.utc)
    ctx.session.add(opp)
    ctx.session.commit()
    ctx.session.refresh(opp)
    emoji = "🏆" if is_won else "💔"
    action = ("ganha" if is_won else "perdida") if lang == "pt" else ("won" if is_won else "lost")
    reply = (
        f"{emoji} Oportunidade \"{opp.name}\" marcada como {action}."
        if lang == "pt"
        else f"{emoji} Opportunity \"{opp.name}\" marked as {action}."
    )
    return IntentResult.ok(
        reply, intent="mark_opportunity", confidence=0.94,
        tool_calls=[{"name": "mark_opportunity", "input": {"name": name, "won": is_won}, "result": {"id": str(opp.id), "status": opp.status.value if hasattr(opp.status, 'value') else str(opp.status)}}],
    )


_MARKETING_COPY_RE = re.compile(
    r"^(?:escreva|crie|gere|write|create|generate|draft)\s+(?:um\s+|uma\s+|a\s+)?(?:post|texto|copy)\s*"
    r"(?:para\s+(?:o\s+)?(?P<platform>linkedin|twitter|x|instagram))?\s*"
    r"(?:sobre|about|on)\s+(?P<topic>.+)$",
    re.IGNORECASE,
)


def _handle_generate_marketing_copy(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    m = _MARKETING_COPY_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    topic = m.group("topic").strip().rstrip("?.!").strip('"\'')
    if len(topic) < 3:
        return IntentResult(handled=False)
    platform = (m.group("platform") or "linkedin").lower().replace("x", "twitter") or "linkedin"
    lang = _detect_lang(text)
    reg = default_registry()
    result = reg.call("generate_marketing_copy", ctx, {
        "topic": topic, "platform": platform, "lang": lang,
    })
    if "error" in result:
        return IntentResult.ok(
            f"Falha ao gerar copy: {result['error']}" if lang == "pt" else f"Copy generation failed: {result['error']}",
            intent="generate_marketing_copy", confidence=0.7,
        )
    header = f"✍️ Copy para {platform} sobre \"{topic}\":" if lang == "pt" else f"✍️ Copy for {platform} about \"{topic}\":"
    hint = "\n\n📋 Copie e cole no seu navegador para publicar." if lang == "pt" else "\n\n📋 Copy and paste in your browser to publish."
    return IntentResult.ok(
        f"{header}\n\n{result['content']}{hint}",
        intent="generate_marketing_copy",
        tool_calls=[{"name": "generate_marketing_copy", "input": {"topic": topic, "platform": platform}, "result": {"platform": platform, "char_count": result.get("char_count")}}],
        confidence=0.92,
    )


def _handle_schedule_meeting(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    from app.jarvis.date_parser import parse_when
    from datetime import timedelta
    from sqlmodel import select, or_
    from app.models import Contact
    from app.services.crud import like_escape
    m = _SCHEDULE_MEETING_RE.search(text.strip()) or _SCHEDULE_MEETING_LOOSE_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    when_text = m.group("when").strip().rstrip(".?!")
    who = (m.group("who") or "").strip()
    # Strip trailing time tokens that the regex swallowed into `who`
    who = _WHO_TAIL_STRIP_RE.sub("", who).strip()
    # Loose regex has no "topic" group — guard access.
    try:
        topic = (m.group("topic") or "").strip()
    except IndexError:
        topic = ""
    lang = _detect_lang(text)

    starts = parse_when(when_text)
    if starts is None:
        return IntentResult.ok(
            f"Não consegui entender a data '{when_text}'." if lang == "pt" else f"Couldn't parse '{when_text}'.",
            intent="schedule_meeting", confidence=0.6,
        )
    ends = starts + timedelta(minutes=30)

    # Slot-fill: try to resolve who → Contact
    resolved_contact = None
    if who:
        tokens = [t for t in who.split() if t]
        like_full = f"%{like_escape(who)}%"
        conditions = [
            Contact.first_name.ilike(like_full, escape="\\"),
            Contact.last_name.ilike(like_full, escape="\\"),
            Contact.email.ilike(like_full, escape="\\"),
        ]
        # If who has 2+ tokens ("Ada Lovelace"), also match first_name=t0 AND last_name=t1
        if len(tokens) >= 2:
            t0 = f"%{like_escape(tokens[0])}%"
            t_last = f"%{like_escape(tokens[-1])}%"
            from sqlmodel import and_
            conditions.append(and_(
                Contact.first_name.ilike(t0, escape="\\"),
                Contact.last_name.ilike(t_last, escape="\\"),
            ))
        matches = list(ctx.session.exec(
            select(Contact).where(
                Contact.workspace_id == ctx.workspace_id,
                Contact.deleted_at.is_(None),
                or_(*conditions),
            ).limit(6)
        ).all())
        if len(matches) > 1:
            # Ambiguous — ask user to pick
            options = [
                {"id": str(c.id),
                 "name": f"{c.first_name} {c.last_name or ''}".strip(),
                 "email": c.email or ""}
                for c in matches
            ]
            header = f"Encontrei {len(matches)} contatos que batem com \"{who}\". Qual você quis dizer?" if lang == "pt" \
                     else f"I found {len(matches)} contacts matching \"{who}\". Which one?"
            lines = [header]
            for i, o in enumerate(options, 1):
                lines.append(f"  {i}. {o['name']}{' — ' + o['email'] if o['email'] else ''}")
            return IntentResult.ok(
                "\n".join(lines), intent="schedule_meeting", confidence=0.7,
                tool_calls=[{
                    "name": "ambiguity",
                    "kind": "contact_choice",
                    "field": "who",
                    "original_message": text,
                    "options": options,
                }],
            )
        elif len(matches) == 1:
            resolved_contact = matches[0]

    summary = topic or (
        f"Reunião com {resolved_contact.first_name} {resolved_contact.last_name or ''}".strip() if resolved_contact and lang == "pt"
        else (f"Meeting with {resolved_contact.first_name} {resolved_contact.last_name or ''}".strip() if resolved_contact
              else (f"Reunião com {who}" if who and lang == "pt"
                    else (f"Meeting with {who}" if who
                          else ("Reunião" if lang == "pt" else "Meeting"))))
    )

    from app.models import Meeting
    from app.services import crud
    obj = Meeting(
        workspace_id=ctx.workspace_id, title=summary,
        starts_at=starts, ends_at=ends,
        related_contact_id=resolved_contact.id if resolved_contact else None,
    )
    obj = crud.create_scoped(ctx.session, obj)
    linked_note = ""
    if resolved_contact:
        linked_note = (f" · vinculado a {resolved_contact.first_name}" if lang == "pt"
                       else f" · linked to {resolved_contact.first_name}")
    reply = (
        f"✅ Reunião criada: \"{summary}\" — {starts.isoformat()}{linked_note}"
        if lang == "pt"
        else f"✅ Meeting created: \"{summary}\" — {starts.isoformat()}{linked_note}"
    )
    return IntentResult.ok(
        reply, intent="schedule_meeting",
        tool_calls=[{"name": "create_meeting", "input": {"summary": summary, "starts_at": starts.isoformat()}, "result": {"id": str(obj.id)}}],
        confidence=0.94,
    )


_READ_FILE_RE = re.compile(
    r"^(?:leia|abra|read|open|resuma|summarize|resumir)\s+(?:o\s+arquivo|the\s+file|file|arquivo)\s+(?P<name>\S+?)\s*[?!]?\s*$",
    re.IGNORECASE,
)


def _handle_read_local_file(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    m = _READ_FILE_RE.search(text.strip())
    if not m:
        return IntentResult(handled=False)
    name = m.group("name").strip().strip("\"'")
    lang = _detect_lang(text)
    reg = default_registry()
    result = reg.call("read_local_file", ctx, {"filename": name})
    if result.get("error"):
        msg_map = {
            "not_found": (f"Não encontrei '{name}' na pasta." if lang == "pt" else f"'{name}' not found in the folder."),
            "path_escape": ("Caminho fora da pasta permitida." if lang == "pt" else "Path escape blocked."),
            "no_workdir": ("Pasta de trabalho não disponível." if lang == "pt" else "Work directory unavailable."),
            "pdf_needs_dep": (result.get("message", "PDF precisa pypdf") if lang == "pt" else result.get("message", "PDF needs pypdf")),
            "unsupported_ext": (f"Não posso ler {result.get('ext', '?')} nativamente." if lang == "pt" else f"Can't read {result.get('ext', '?')} natively."),
            "read_failed": (f"Falha: {result.get('message', '?')}" if lang == "pt" else f"Read failed: {result.get('message', '?')}"),
        }
        return IntentResult.ok(
            msg_map.get(result["error"], result["error"]),
            intent="read_local_file", confidence=0.7,
        )
    text_body = result.get("text", "")
    header = f"📄 {result['name']} ({result.get('size', 0) // 1024} KB)" if lang == "pt" else f"📄 {result['name']} ({result.get('size', 0) // 1024} KB)"
    truncated = "\n…(truncado)" if result.get("truncated") else ""
    return IntentResult.ok(
        f"{header}\n\n{text_body}{truncated}",
        intent="read_local_file", confidence=0.94,
        tool_calls=[{"name": "read_local_file", "input": {"filename": name}, "result": {"size": result.get("size"), "truncated": result.get("truncated")}}],
    )


def _handle_auto_import_contacts(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    lang = _detect_lang(text)
    confirm = bool(re.search(r"\b(confirme|confirmar|confirm|yes|sim|sim\s+importe)\b", text, re.IGNORECASE))
    reg = default_registry()
    result = reg.call("auto_import_contacts", ctx, {"confirm": confirm})
    if result.get("status") == "no_workdir":
        return IntentResult.ok(
            "Pasta de trabalho não disponível." if lang == "pt" else "Work directory unavailable.",
            intent="auto_import_contacts", confidence=0.85,
        )
    if result.get("status") == "ok":
        created = result.get("created", 0)
        return IntentResult.ok(
            f"✅ {created} contato(s) importados dos arquivos locais." if lang == "pt" else f"✅ Imported {created} contact(s) from local files.",
            intent="auto_import_contacts", confidence=0.95,
            tool_calls=[{"name": "auto_import_contacts", "input": {"confirm": True}, "result": {"created": created}}],
        )
    # Preview
    would = result.get("would_import", 0)
    if would == 0:
        return IntentResult.ok(
            "📂 Nenhum novo contato encontrado nos arquivos da pasta." if lang == "pt" else "📂 No new contacts found in the folder files.",
            intent="auto_import_contacts", confidence=0.92,
        )
    lines = []
    if lang == "pt":
        lines.append(f"📥 Encontrei {would} contatos para importar (nas primeiras 5):")
        for c in result.get("sample", []):
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            email = c.get("email", "")
            lines.append(f"  • {name}{' — ' + email if email else ''}")
        if result.get("skipped_dupes"):
            lines.append(f"({result['skipped_dupes']} duplicatas puladas)")
        lines.append("")
        lines.append("Diga \"importe contatos confirme\" para criar tudo.")
    else:
        lines.append(f"📥 Found {would} contacts to import (first 5):")
        for c in result.get("sample", []):
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            email = c.get("email", "")
            lines.append(f"  • {name}{' — ' + email if email else ''}")
        if result.get("skipped_dupes"):
            lines.append(f"({result['skipped_dupes']} duplicates skipped)")
        lines.append("")
        lines.append("Say \"import contacts confirm\" to create them all.")
    return IntentResult.ok(
        "\n".join(lines), intent="auto_import_contacts", confidence=0.93,
        tool_calls=[{"name": "auto_import_contacts", "input": {"confirm": False}, "result": {"would_import": would}}],
    )


def _handle_scan_work_dir(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    lang = _detect_lang(text)
    reg = default_registry()
    result = reg.call("scan_work_dir", ctx, {})
    if result.get("status") != "ok":
        return IntentResult.ok(
            "Pasta de trabalho não disponível." if lang == "pt" else "Work directory unavailable.",
            intent="scan_work_dir", confidence=0.85,
        )
    counts = result.get("counts", {})
    total = sum(counts.values())
    if total == 0:
        msg = (
            f"📂 Pasta {result['root']} está vazia. Solte arquivos aqui: .ics (agenda), .csv (contatos), .vcf (vCards)."
            if lang == "pt"
            else f"📂 Folder {result['root']} is empty. Drop files here: .ics (calendar), .csv (contacts), .vcf (vCards)."
        )
        return IntentResult.ok(msg, intent="scan_work_dir", confidence=0.92)
    lines = [f"📂 {result['root']}", ""]
    labels = {"calendars": "📅 Agendas", "contacts": "👥 Contatos",
              "docs": "📄 Docs", "spreadsheets": "📊 Planilhas", "images": "🖼️ Imagens"} if lang == "pt" else \
             {"calendars": "📅 Calendars", "contacts": "👥 Contacts",
              "docs": "📄 Docs", "spreadsheets": "📊 Sheets", "images": "🖼️ Images"}
    for cat, label in labels.items():
        n = counts.get(cat, 0)
        if n:
            lines.append(f"{label}: {n}")
            for f in result["categories"].get(cat, [])[:5]:
                lines.append(f"  • {f['name']} ({f['size'] // 1024} KB)")
    if result.get("other"):
        other_lbl = "🗂 Outros" if lang == "pt" else "🗂 Other"
        lines.append(f"{other_lbl}: {len(result['other'])}")
    return IntentResult.ok(
        "\n".join(lines), intent="scan_work_dir", confidence=0.92,
        tool_calls=[{"name": "scan_work_dir", "result": {"counts": counts, "root": result["root"]}}],
    )


def _handle_read_calendar(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    lang = _detect_lang(text)
    # Optional "N dias" / "N days" hint
    m = re.search(r"\b(\d+)\s*(dias?|days?)\b", text, re.IGNORECASE)
    days = int(m.group(1)) if m else 7
    reg = default_registry()
    result = reg.call("read_calendar", ctx, {"days": days})
    if result.get("status") == "not_connected":
        return IntentResult.ok(result.get("message", ""), intent="read_calendar", confidence=0.9)
    if result.get("status") == "token_expired":
        return IntentResult.ok(result.get("message", ""), intent="read_calendar", confidence=0.9)
    if result.get("status") == "coming_soon":
        return IntentResult.ok(result.get("message", ""), intent="read_calendar", confidence=0.85)
    if "error" in result:
        msg = result.get("message", result["error"])
        return IntentResult.ok(
            f"Não consegui ler sua agenda: {msg}" if lang == "pt" else f"Couldn't read your calendar: {msg}",
            intent="read_calendar", confidence=0.7,
        )
    events = result.get("events", [])
    if not events:
        return IntentResult.ok(
            f"Nenhum evento nos próximos {days} dias." if lang == "pt" else f"No events in the next {days} days.",
            intent="read_calendar", confidence=0.9,
        )
    header = f"📅 {len(events)} eventos nos próximos {days} dias:" if lang == "pt" else f"📅 {len(events)} events in the next {days} days:"
    lines = [header]
    for ev in events[:10]:
        when = (ev.get("start") or "")[:16].replace("T", " ")
        loc = f" — {ev['location']}" if ev.get("location") else ""
        lines.append(f"  • {when} — {ev['summary']}{loc}")
    if len(events) > 10:
        lines.append(f"  … +{len(events) - 10}")
    return IntentResult.ok(
        "\n".join(lines), intent="read_calendar",
        tool_calls=[{"name": "read_calendar", "input": {"days": days}, "result": {"count": len(events), "status": result.get("status")}}],
        confidence=0.92,
    )


def _handle_stale_leads(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Leads not touched in the last N days (default 14)."""
    from sqlmodel import select
    from app.models import Lead, LeadStatus, Activity
    from datetime import datetime, timezone, timedelta
    lang = _detect_lang(text)
    m = re.search(r"\b(\d+)\s*(days?|dias?)\b", text, re.IGNORECASE)
    n_days = int(m.group(1)) if m else 14
    cutoff = datetime.now(timezone.utc) - timedelta(days=n_days)
    stmt = select(Lead).where(
        Lead.workspace_id == ctx.workspace_id,
        Lead.deleted_at.is_(None),
        Lead.status != LeadStatus.converted,
        Lead.status != LeadStatus.unqualified,
    )
    leads = list(ctx.session.exec(stmt).all())
    # Filter by last activity or fall back to updated_at
    def last_touch(lead):
        act = ctx.session.exec(
            select(Activity).where(
                Activity.workspace_id == ctx.workspace_id,
                Activity.subject_type == "lead",
                Activity.subject_id == lead.id,
            ).order_by(Activity.occurred_at.desc()).limit(1)
        ).first()
        if act:
            occ = act.occurred_at
            return occ if occ.tzinfo else occ.replace(tzinfo=timezone.utc)
        upd = lead.updated_at or lead.created_at
        return upd if upd and upd.tzinfo else (upd.replace(tzinfo=timezone.utc) if upd else datetime.now(timezone.utc))
    stale = [(l, last_touch(l)) for l in leads]
    stale = [(l, ts) for l, ts in stale if ts < cutoff]
    stale.sort(key=lambda x: x[1])
    if not stale:
        reply = f"Nenhum lead parado há mais de {n_days} dias. ✅" if lang == "pt" else f"No leads stale for more than {n_days} days. ✅"
        return IntentResult.ok(reply, intent="stale_leads", confidence=0.92)
    header = f"{len(stale)} leads sem toque há mais de {n_days} dias:" if lang == "pt" else f"{len(stale)} leads with no touch in over {n_days} days:"
    lines = [header]
    for l, ts in stale[:10]:
        name = f"{l.first_name} {l.last_name or ''}".strip()
        days_since = (datetime.now(timezone.utc) - ts).days
        lines.append(f"  • {name}{' — ' + l.company_name if l.company_name else ''} — {days_since}d")
    if len(stale) > 10:
        lines.append(f"  … +{len(stale) - 10}")
    return IntentResult.ok("\n".join(lines), intent="stale_leads", confidence=0.92)


def _handle_weekly_digest(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    """Detailed digest: wins, losses, new opps, tasks completed, meetings held.

    Defaults to 7 days but recognizes 'monthly' → 30 days.
    """
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus, Task, TaskStatus, Meeting, Activity, Lead, LeadStatus
    from datetime import datetime, timezone, timedelta
    lang = _detect_lang(text)
    now = datetime.now(timezone.utc)
    is_monthly = bool(re.search(r"\b(monthly|mensal|mes|mês|30\s*dias)\b", text, re.IGNORECASE))
    days = 30 if is_monthly else 7
    week_ago = now - timedelta(days=days)

    def in_week(dt):
        if dt is None: return False
        d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return week_ago <= d <= now

    opps = list(ctx.session.exec(select(Opportunity).where(
        Opportunity.workspace_id == ctx.workspace_id,
        Opportunity.deleted_at.is_(None),
    )).all())
    wins = [o for o in opps if o.status == OpportunityStatus.won and in_week(o.closed_at)]
    losses = [o for o in opps if o.status == OpportunityStatus.lost and in_week(o.closed_at)]
    new_opps = [o for o in opps if in_week(o.created_at)]
    tasks_done = list(ctx.session.exec(select(Task).where(
        Task.workspace_id == ctx.workspace_id, Task.deleted_at.is_(None),
        Task.status == TaskStatus.done,
    )).all())
    tasks_done = [tk for tk in tasks_done if in_week(tk.updated_at)]
    meetings = list(ctx.session.exec(select(Meeting).where(
        Meeting.workspace_id == ctx.workspace_id, Meeting.deleted_at.is_(None),
    )).all())
    meetings_held = [m for m in meetings if in_week(m.starts_at) and (m.starts_at if m.starts_at.tzinfo else m.starts_at.replace(tzinfo=timezone.utc)) <= now]
    new_leads = list(ctx.session.exec(select(Lead).where(
        Lead.workspace_id == ctx.workspace_id, Lead.deleted_at.is_(None),
    )).all())
    new_leads = [l for l in new_leads if in_week(l.created_at)]
    won_amt = sum(o.amount or 0 for o in wins)
    lost_amt = sum(o.amount or 0 for o in losses)

    period_pt = f"últimos {days} dias" if not is_monthly else "últimos 30 dias (mensal)"
    period_en = f"last {days} days" if not is_monthly else "last 30 days (monthly)"
    if lang == "pt":
        lines = [
            f"📊 Digest ({period_pt}):",
            "",
            f"  💚 Ganhas: {len(wins)} · $ {won_amt:,.0f}",
            f"  💔 Perdidas: {len(losses)} · $ {lost_amt:,.0f}",
            f"  ➕ Novas oportunidades: {len(new_opps)}",
            f"  🎯 Novos leads: {len(new_leads)}",
            f"  ✅ Tarefas concluídas: {len(tasks_done)}",
            f"  📅 Reuniões realizadas: {len(meetings_held)}",
        ]
    else:
        lines = [
            f"📊 Digest ({period_en}):",
            "",
            f"  💚 Wins: {len(wins)} · $ {won_amt:,.0f}",
            f"  💔 Losses: {len(losses)} · $ {lost_amt:,.0f}",
            f"  ➕ New opportunities: {len(new_opps)}",
            f"  🎯 New leads: {len(new_leads)}",
            f"  ✅ Tasks completed: {len(tasks_done)}",
            f"  📅 Meetings held: {len(meetings_held)}",
        ]
    return IntentResult.ok("\n".join(lines), intent="weekly_digest", confidence=0.94)


def _handle_who_am_i(intent: "Intent", text: str, snap: "WorkspaceSnapshot", ctx: "ToolContext") -> "IntentResult":
    from sqlmodel import select
    from app.models import User
    lang = _detect_lang(text)
    user = ctx.session.exec(select(User).where(User.id == ctx.user_id)).first()
    name = user.full_name or (user.email.split("@")[0] if user else "?")
    reply = f"Você é {name} ({user.email})." if lang == "pt" else f"You are {name} ({user.email})."
    return IntentResult.ok(reply, intent="who_am_i", confidence=0.98)


# ---- Registry -------------------------------------------------------------

def _re(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


DEFAULT_INTENTS: list[Intent] = [
    Intent(
        # Data quality check: flag entities missing critical fields
        name="data_quality",
        patterns=_re([
            r"^\s*(?:data\s+quality|qualidade\s+(?:dos\s+)?dados|dq\s+check|check\s+data|dados\s+(?:incompletos|faltando))\s*[?!.]?\s*$",
            r"^\s*(?:o\s+que\s+(?:est[áa]|falta)\s+faltando|what.?s\s+missing|what\s+is\s+missing)\s*[?!.]?\s*$",
        ]),
        handler=_handle_data_quality,
    ),
    Intent(
        # Convert lead → contact (CRM workflow)
        name="convert_lead",
        patterns=_re([
            r"^\s*(?:convert|converta|converte|converter|promova?|promote)\s+(?:o\s+|a\s+|the\s+)?lead\s+\S",
        ]),
        handler=_handle_convert_lead,
    ),
    Intent(
        # Breakdown of open opps by owner user
        name="stats_by_owner",
        patterns=_re([
            r"^\s*(?:pipeline\s+(?:por\s+dono|by\s+owner|by\s+rep)|deals?\s+(?:per|by)\s+(?:owner|rep|user)|oportunidades?\s+por\s+dono)\s*[?!.]?\s*$",
            r"^\s*(?:quem\s+tem\s+mais\s+(?:opp?s?|oportunidades|deals))\s*[?!.]?\s*$",
        ]),
        handler=_handle_stats_by_owner,
    ),
    Intent(
        # Pipeline overall health check with diagnosis
        name="pipeline_health",
        patterns=_re([
            r"^\s*(?:pipeline\s+(?:health|sa[úu]de)|sa[úu]de\s+(?:do\s+)?pipeline|health\s+check|como\s+(?:est[áa]|vai)\s+(?:meu\s+|o\s+)?pipeline)\s*[?!.]?\s*$",
        ]),
        handler=_handle_pipeline_health,
    ),
    Intent(
        # List leads with score above threshold (default 70)
        name="hot_leads",
        patterns=_re([
            r"^\s*(?:hot\s+leads?|leads?\s+(?:quentes?|hot|top))\s*(?:\d+)?\s*[?!.]?\s*$",
            r"^\s*leads?\s+(?:com\s+)?score\s+(?:acima|maior|>|>=)\s*\d",
        ]),
        handler=_handle_hot_leads,
    ),
    Intent(
        # MoM comparison of closed-won deals
        name="momentum_check",
        patterns=_re([
            r"^\s*(?:momentum|momento(?:\s+do\s+m[êe]s)?|mom(?:\s+check)?|month(?:\s+over\s+month)?|mes\s+vs\s+mes|m[êe]s\s+atual\s+vs)\s*[?!.]?\s*$",
            r"^\s*(?:como\s+estamos|how\s+are\s+we\s+doing)\s+(?:esse\s+m[êe]s|this\s+month)\s*[?!.]?\s*$",
            r"^\s*(?:evolu[çc][ãa]o|trend|tendencia|tend[êe]ncia)\s*[?!.]?\s*$",
        ]),
        handler=_handle_momentum_check,
    ),
    Intent(
        # List open opportunities stale for N+ days
        name="stale_opportunities",
        patterns=_re([
            # Read-only listing — must NOT start with an action verb (feche/close/mark)
            # or "close_stale_opportunities" wouldn't get a chance to run.
            r"^\s*(?!(?:feche|close|marque?|mark)\b).*\b(?:oportunidades?|opps?|deals?)\s+(?:paradas?|stale|velhas?|antigas?|old|idle)\b",
            r"^\s*(?!(?:feche|close|marque?|mark)\b).*\b(?:stale|idle|old)\s+(?:opportunit(?:y|ies)|opps?|deals?)\b",
            r"^\s*opps?\s+parad[oa]s?\s+h[áa]\s+\d",
        ]),
        handler=_handle_stale_opportunities,
    ),
    Intent(
        # Morning briefing: overdue + meetings today + top open opp
        name="daily_briefing",
        patterns=_re([
            r"^\s*(?:briefing|resumo\s+(?:matinal|do\s+dia)|daily\s+briefing|morning\s+briefing|me\s+d[êe]\s+um\s+briefing|meu\s+dia|my\s+day)\s*[?!.]?\s*$",
        ]),
        handler=_handle_daily_briefing,
        description="Morning briefing: overdue + meetings + top opp.",
    ),
    Intent(
        # Proactive agent: 3 concrete next actions based on state
        name="suggest_next_action",
        patterns=_re([
            r"^\s*(?:o\s+que\s+(?:eu\s+)?(?:devo|preciso)\s+fazer|o\s+que\s+fa[çc]o|pr[óo]xim[oa]s?\s+(?:passos?|a[çc][ãa]o|a[çc][õo]es))\s*[?!.]?\s*$",
            r"^\s*(?:sugest[õo]es?|sugira|sugere|me\s+sugira|recomenda(?:[çc][ãa]o|[çc][õo]es|coes|caoes)|recomende|recommendations?|next\s+steps?|next\s+action|what\s+(?:should|do|next)|suggest\s+(?:actions?)?|proximas?\s+a[çc][ãa]o)\s*[?!.]?\s*$",
            r"^\s*(?:me\s+ajude?\s+a\s+priorizar|what\s+should\s+i\s+(?:do|focus)|help\s+me\s+prioritize)\s*[?!.]?\s*$",
        ]),
        handler=_handle_suggest_next_action,
        description="Suggest 3 concrete next actions based on state.",
    ),
    Intent(
        # Agent explains its last action in plain terms.
        name="explain_last",
        patterns=_re([
            r"^\s*(?:explique?|explica|explain|why|por\s*qu[êe]|porque|pq)\s*(?:isso|isto|that|it|essa|essa\s+a[çc][ãa]o|the\s+last)?\s*[?!.]?\s*$",
            r"^\s*(?:o\s+que\s+voc[êe]\s+fez|what\s+did\s+you\s+(?:just\s+)?do)\s*[?!.]?\s*$",
        ]),
        handler=_handle_explain_last,
    ),
    Intent(
        name="undo_last",
        patterns=_re([
            r"^\s*(?:desfa[çc]a?|desfaz|desfazer|reverte(?:r)?|reverta|volta(?:r)?|volte)\s*(?:isso|essa|essa\s+altera[çc][ãa]o|essa\s+mudan[çc]a|último|ultimo|a\s+última|a\s+ultima)?\s*[.!?]?\s*$",
            r"^\s*undo(?:\s+(?:that|it|the\s+last(?:\s+change)?))?\s*[.!?]?\s*$",
            r"^\s*(?:rollback|revert)(?:\s+last)?\s*[.!?]?\s*$",
        ]),
        handler=_handle_undo_last,
        description="Reverse the most recent field update.",
    ),
    Intent(
        name="greeting",
        patterns=_re([
            # Optional emoji prefix (👋, 👍, 🙌, etc.) — chat is more natural this way
            r"^[\s\W]*(oi|olá|ola|hi|hello|hey|bom dia|boa tarde|boa noite|good (morning|afternoon|evening))\b",
            r"^\s*(e\s+ai|eai|salve|iai|i\s+ai)\s*[?!.]?\s*$",
        ]),
        handler=_handle_greeting,
        description="Say hi and orient the user.",
    ),
    Intent(
        name="how_are_you",
        patterns=_re([
            r"\b(como\s+voc[eê]\s+est[aá]|tudo\s+bem|beleza|how\s+are\s+you|how'?s\s+it\s+going)\b",
        ]),
        handler=_handle_how_are_you,
    ),
    Intent(
        name="who_are_you",
        patterns=_re([
            r"\b(quem\s+[eé]\s+voc[eê]|who\s+are\s+you|what\s+are\s+you|o\s+que\s+voc[eê]\s+[eé])\b",
            r"^\s*(jarvis)\s*[?!.]?\s*$",
            r"\bsobre\s+(voc[eê]|o\s+jarvis|si)\b",
            r"\babout\s+(you|jarvis|yourself)\b",
            r"\bqual\s+(?:é\s+)?(?:o\s+)?seu\s+nome\b",
            r"\bwhat.?s\s+your\s+name\b",
            r"\bcomo\s+voc[eê]\s+se\s+chama\b",
        ]),
        handler=_handle_who_are_you,
    ),
    Intent(
        name="capabilities",
        patterns=_re([
            r"\b(o\s+que\s+voc[eê]\s+(pode|faz|consegue)|what\s+can\s+you\s+do|what\s+do\s+you\s+do|capacidades|comandos|commands)\b",
        ]),
        handler=_handle_capabilities,
    ),
    Intent(
        name="help_me_focus",
        patterns=_re([
            r"\b(help\s+me\s+focus|ajude?\s+a\s+focar|foca?\s+em|focus\s+today)\b",
            r"^\s*focus\s*[?!.]?\s*$",
            r"^\s*3\s+(a[çc]?[oõ]es|actions|tarefas)\b",
            r"^\s*focar\s*[?!.]?\s*$",
            r"\bfoco\s+de?\s+hoje\b",
            r"\bajude?\s+(me\s+)?a?\s*priorizar\b",
            r"\bmelhor\s+uso\s+do\s+tempo\b",
            r"\bpriori(?:dade|zar)\s+de?\s+hoje\b",
        ]),
        handler=_handle_help_me_focus,
    ),
    Intent(
        name="help",
        patterns=_re([
            r"^\s*(help|ajuda)\s*[?!.]?\s*$",
            r"\b(o que voc[eê] (pode|faz)|what can you do)\b",
            r"\bpreciso\s+de\s+ajuda\b",
            r"^\s*help\s+me\s*[?!.]?\s*$",
            r"\bme\s+ajude?\b",
            # Chat abbreviations: "oq eu posso fazer", "o q vc faz", etc.
            r"\b(oq|o\s*q|q)\s+(?:eu\s+|vc\s+|voce\s+|você\s+|tu\s+)?(?:posso|faz|fazer|pode)\b",
            r"\b(o\s+que|q)\s+(?:vc|voce|você|tu)\s+(?:faz|pode\s+fazer)\b",
            # Meta questions about the app
            r"^\s*(?:como\s+(?:isso\s+|voc[êe]\s+|vc\s+)?funciona|how\s+does\s+(?:this|it)\s+work)\s*[?!.]?\s*$",
            r"^\s*(?:pra\s+que\s+serve|what.?s\s+this\s+for|what\s+is\s+this)\s*[?!.]?\s*$",
        ]),
        handler=_handle_help,
    ),
    Intent(
        name="today_summary",
        patterns=_re([
            r"\b(today|hoje)\b.*\b(schedule|agenda|summary|resumo|plan)\b",
            r"\bwhat('s| is)?\s+(on|going\s+on)\s+today\b",
            r"\bo\s+que\s+(tem|h[aá])\s+hoje\b",
            r"\bagenda\s+de?\s+hoje\b",
            r"^\s*(hoje|today)\s*[?!.]?\s*$",
        ]),
        handler=_handle_today,
    ),
    Intent(
        name="snooze_task",
        patterns=_re([
            r"^(snooze|adie?|adiar|posterguer?|reagende?)\s+(a\s+|the\s+)?(tarefa|task)\b.*\b(por|for|by|em)\s+\d+",
        ]),
        handler=_handle_snooze_task,
    ),
    Intent(
        name="delete_entity",
        patterns=_re([
            r"^(apague?|delete|remova|remove|excluir)\s+(o\s+|a\s+|the\s+)?(contato|contact|empresa|company|oportunidade|opportunity|opp|deal|lead)\b",
        ]),
        handler=_handle_delete_entity,
    ),
    Intent(
        name="delete_task",
        patterns=_re([
            r"^(apague?|delete|remova|remove|excluir)\s+(a\s+|the\s+)?(tarefa|task)\b",
        ]),
        handler=_handle_delete_task,
    ),
    Intent(
        # Bulk delete tasks by filter: "apaga todas tarefas concluídas"
        # Must come BEFORE delete_bare (whose negative-lookahead already excludes "all/todas").
        name="bulk_delete_tasks",
        patterns=_re([
            # "delete all tasks" / "apaga todas tarefas concluídas" / "delete all overdue tasks"
            r"^\s*(?:apaga|apague|apagar|delete|remove|remover|remova|excluir|clear|limpe|limpar)\s+(?:todas?|all)\s+(?:as\s+|the\s+)?(?:(?:conclu[íi]das?|feitas?|done|completed|canceladas?|cancelled|abertas?|open|todo|pending|pendentes?|atrasadas?|overdue|late|vencidas?)\s+)?(?:tarefas?|tasks?)\b",
            # filter-before-tasks alt order: "apaga tarefas concluídas" (no "todas")
            r"^\s*(?:apaga|apague|apagar|delete|remove|remover|remova|excluir|clear|limpe|limpar)\s+(?:as\s+|all\s+)?(?:tarefas?|tasks?)\s+(?:conclu[íi]das?|feitas?|done|completed|canceladas?|cancelled|abertas?|open|todo|pending|pendentes?|atrasadas?|overdue|late|vencidas?)\b",
        ]),
        handler=_handle_bulk_delete_tasks,
    ),
    Intent(
        # Clear field: "apaga o email do Alice" / "remove Alice email"
        # Must come BEFORE delete_bare because "remove/delete/apaga" verbs overlap;
        # this pattern is more specific (requires a field name), so try it first.
        name="clear_field",
        patterns=_re([
            r"^\s*(?:apaga|apagar|apague|remove|remover|remova|limpa|limpar|limpe|clear|delete)\s+(?:o\s+|a\s+|the\s+)?(?:email|e-mail|telefone|phone|cargo|title|job[_\s]?title|nome|name|amount|valor|probabilidade|probability|website|site|dom[íi]nio|domain|ind[úu]stria|industry|score)\s+(?:do|da|de|of|from|for)\s+\S",
            r"^\s*(?:clear|remove|delete|apaga|apagar|apague|remova|limpa|limpar|limpe)\s+\S.*?\s+(?:email|e-mail|telefone|phone|cargo|title|job[_\s]?title|nome|name|amount|valor|probabilidade|probability|website|site|dom[íi]nio|domain|ind[úu]stria|industry|score)\s*[?!.]?\s*$",
        ]),
        handler=_handle_clear_field,
    ),
    Intent(
        # Bare-name delete: search across all entity kinds. Must come AFTER the
        # scoped variants above so "delete contact X" doesn't fall through here.
        name="delete_bare",
        patterns=_re([
            r"^(apague?|apagar|delete|remova|remover?|excluir?|drop)\s+(o\s+|a\s+|the\s+)?"
            r"(?!(?:contato|contact|empresa|company|oportunidade|opportunity|opp|deal|neg[óo]cio|lead|task|tarefa|nota|note|all|tudo|todos?|todas?|every|everything)\b)\S",
        ]),
        handler=_handle_delete_bare,
    ),
    Intent(
        name="brief_company",
        patterns=_re([
            r"^(brief|resumo|resumir|summarize|briefing)\s+(empresa|company|companhia)\s+\S",
        ]),
        handler=_handle_brief_company,
    ),
    Intent(
        name="brief_lead",
        patterns=_re([
            r"^(brief|resumo|resumir|summarize|briefing)\s+lead\s+\S",
        ]),
        handler=_handle_brief_lead,
    ),
    Intent(
        name="brief_opp",
        patterns=_re([
            r"^(brief|resumo|resumir|summarize|briefing)\s+(opp|deal|oportunidade|neg[oó]cio)\s+\S",
        ]),
        handler=_handle_brief_opp,
    ),
    Intent(
        name="close_stale_opportunities",
        patterns=_re([
            r"^(feche|close|marque?|mark)\s+(as\s+|all\s+)?(oportunidades?|opportunities|deals|opps)\s+(sem\s+toque|stale|parad[oa]s|inact(ive|ivas)|antig(a|o)s?|old)\b",
            r"\bclose\s+stale\s+(deals|opportunities|opps)\b",
        ]),
        handler=_handle_close_stale_opps,
    ),
    Intent(
        name="plan_week",
        patterns=_re([
            r"^(planeje?|plan)\s+(minha|my|a|the)?\s*(semana|week)\b",
            r"^weekly\s+plan\b",
            r"^plano\s+d[ea]?\s+semana\b",
        ]),
        handler=_handle_plan_week,
    ),
    Intent(
        name="mark_opportunity",
        patterns=_re([
            r"^(marque?|mark|mova?|move|set)\s+(a\s+|the\s+)?(oportunidade|opportunity|opp|deal|neg[oó]cio)\b.*\b(como|as|for|to)\b\s+(won|ganhad?a?|ganho|lost|perdid?a?|perdeu)\b",
            # Short form: "ganhei/perdi/won/lost <opp name>". Exclude phrases like
            # "won this month" / "lost opportunities" / "won quanto" — those go to other intents.
            r"^(ganhei|perdi|won|lost)\s+(o\s+|a\s+|the\s+)?(?!(this|last|these|those|opportunit(?:y|ies)|deals?|oportunidades?|neg[óo]cios?|opps?|quanto|much|m[êe]s|semana|ano|month|week|year)\b)\S",
        ]),
        handler=_handle_mark_opportunity,
    ),
    Intent(
        name="generate_marketing_copy",
        patterns=_re([
            r"^(escreva|crie|gere|write|create|generate|draft)\s+(um\s+|uma\s+|a\s+)?(post|texto|copy)\b.*\b(sobre|about|on)\b",
        ]),
        handler=_handle_generate_marketing_copy,
    ),
    Intent(
        name="schedule_meeting",
        patterns=_re([
            r"^(agende?|marque?|marca|schedule|book|create)\s+(uma?\s+|a\s+|an\s+)?(reuni[ãa]o|meeting|call|encontro)\b.*(\b(para|em|for|at|on|amanh[ãa]|amanha|hoje|today|tomorrow|next|pr[óo]xim[oa]|na?|seg(?:unda)?|ter(?:[cç]a)?|qua(?:rta)?|qui(?:nta)?|sex(?:ta)?|s[áa]b(?:ado)?|dom(?:ingo)?|monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b|\s[àa]s?\s|\d)",
        ]),
        handler=_handle_schedule_meeting,
    ),
    Intent(
        name="read_local_file",
        patterns=_re([
            r"^(leia|abra|read|open|resuma|summarize|resumir)\s+(o\s+arquivo|the\s+file|file|arquivo)\s+.+",
        ]),
        handler=_handle_read_local_file,
    ),
    Intent(
        name="auto_import_contacts",
        patterns=_re([
            r"^(importe?|import|auto-?import|detecte?|carregar)\s+(os\s+)?(contatos?|contacts?)\b",
            r"^(auto|automatic).*\bimport(ar)?\s+contatos?\b",
        ]),
        handler=_handle_auto_import_contacts,
    ),
    Intent(
        name="scan_work_dir",
        patterns=_re([
            r"^(scan|escaneie?|varra|listar?)\s+(arquivos?|files|minha\s+pasta|my\s+folder|pasta\s+de\s+trabalho|work\s+dir)\b",
            r"^(onde|where)\s+(estão|estao|are)\s+(meus|my)\s+arquivos?\b",
            r"^(que|what|quais)\s+(arquivos|files)\b.*\b(tenho|have|há|ha)\b",
            r"^(meus\s+)?arquivos\s*[?!.]?\s*$",
        ]),
        handler=_handle_scan_work_dir,
    ),
    Intent(
        name="read_calendar",
        patterns=_re([
            r"\b(minha|read\s+my|check\s+my|show\s+my)\s+(agenda|calend[aá]rio|calendar)\b",
            r"\b(pr[oó]ximos\s+)?(eventos|meetings?)\s+(da\s+)?(minha\s+)?(agenda|calend[aá]rio)\b",
            r"\b(what.?s\s+on\s+my|any)\s+calendar\b",
            r"\b(quais\s+)?eventos\s+(tenho|estão)\s+(hoje|amanh[ãa]|semana|na\s+minha\s+agenda)\b",
            r"^\s*(agenda|calend[aá]rio|calendar)\s*[?!.]?\s*$",
        ]),
        handler=_handle_read_calendar,
    ),
    Intent(
        name="weekly_digest",
        patterns=_re([
            r"\b(weekly|week|monthly|month)\s+(digest|recap|breakdown|briefing)\b",
            r"\b(digest|resumo\s+detalhado)\s+(da\s+)?(semana|m[êe]s)\b",
            r"\bresumo\s+(semanal|mensal)\s+(detalhado|completo)\b",
        ]),
        handler=_handle_weekly_digest,
    ),
    Intent(
        name="stale_leads",
        patterns=_re([
            r"\bstale\s+leads?\b",
            r"\bleads?\s+(parados?|frios?|sem\s+toque)\b",
            r"\bleads?\s+(que\s+esfriaram|esfriando)\b",
            r"\binactive\s+leads?\b",
        ]),
        handler=_handle_stale_leads,
    ),
    Intent(
        # Priority over week_summary: "perdi quanto esta semana" contains "esta semana"
        # but is really a revenue query, not a summary.
        name="amount_this_period",
        patterns=_re([
            r"\b(ganhei|perdi)\s+quanto\b",
            r"\bquanto\s+(ganhei|perdi)\b",
            r"\b(won|lost)\s+(this|last|)\s*(month|week|year|m[êe]s|semana|ano)\b",
            r"\b(ganhos?|perdas?|receita)\s+(deste?\s+|este\s+|desta\s+|esta\s+|do\s+|da\s+)?(m[êe]s|semana|ano)\b",
        ]),
        handler=_handle_amount_this_period,
    ),
    Intent(
        name="week_summary",
        # Tightened after tick 27: bare `weekly` matched any message that
        # happened to contain the word (e.g. "reschedule Nebula WEEKLY sync
        # to tomorrow 3pm" hijacked this intent). Require an anchor phrase
        # so incidental uses don't fire.
        # Tightened again: "meetings this week" / "reuniões esta semana" belong
        # to upcoming_meetings, not week_summary — exclude via negative lookbehind.
        patterns=_re([
            r"(?<!meetings\s)(?<!reuni[õo]es\s)\b(this\s+week|week\s+summary|weekly\s+summary|weekly\s+report)\b",
            r"(?<!reuni[õo]es\s)\b(resumo\s+d[ea]\s+semana|resumo\s+semanal|esta\s+semana)\b",
        ]),
        handler=_handle_week_summary,
        fuzzy_keywords=["week|weekly|semana|semanal", "summary|resumo|report|relatorio"],
    ),
    Intent(
        name="list_preferences",
        patterns=_re([
            r"\b(what|o que)\s+(do\s+)?you\s+(remember|know)\b",
            r"\b(o que voc[eê]|que voc[eê])\s+(lembra|sabe)\b",
            r"^\s*(preferences?|prefer[eê]ncias?)\s*[?!.]?\s*$",
        ]),
        handler=_handle_list_preferences,
    ),
    Intent(
        name="remember",
        # Match "remember X" but NOT "what do you remember" (the list intent already
        # caught that above). We require content after the trigger word.
        # Also NOT "me lembre …" which is a task-creation phrasing (create_task
        # picks that up further down).
        patterns=_re([
            r"(?<!me\s)\b(remember|lembre(?:-se)?|guarde)\s*[:\-]?\s+\S",
            r"\b(call\s+me|me\s+chame|pode\s+me\s+chamar\s+de)\s+\S",
            r"\b(prefer(?:o|ir)?|fale?\s+comigo\s+em|responda\s+em)\b.*\b(portugu[êe]s|ingl[êe]s|english|portuguese|pt(?:-?br)?|en(?:-us)?)\b",
            # Tone preference: "seja formal", "modo casual", "be more technical"
            r"\b(?:seja|be|modo|mode|estilo|style|tom|tone)\s+(?:mais\s+|more\s+)?(?:formal|casual|t[eé]cnic[oa]|technical|amig[áa]vel|friendly|neutro|neutral|conciso|concise|verbose|prolix[oa])\b",
        ]),
        handler=_handle_remember,
    ),
    Intent(
        name="log_interaction",
        patterns=_re([
            r"\b(log|register|registrar|anotar)\b.*\b(call|liga(?:ç|c)[ãa]o|email|e-mail|sms|whatsapp|zap|chat|conversa)\b",
        ]),
        handler=_handle_log_interaction,
    ),
    Intent(
        name="tag_entity",
        patterns=_re([
            r"\b(tag|marcar|marque|etiquetar)\b.+\b(as|como)\b",
        ]),
        handler=_handle_tag_entity,
    ),
    Intent(
        name="reschedule_meeting",
        patterns=_re([
            r"\b(reschedule|remarcar|reagendar)\b",
            r"\b(move|mover)\b.*\b(meeting|reuni[ãa]o)\b.*\b(to|para|for)\b",
        ]),
        handler=_handle_reschedule_meeting,
    ),
    Intent(
        name="move_opportunity_stage",
        patterns=_re([
            r"\b(move|mover|advance|avan(?:ç|c)ar|change|mudar|mark)\b.*\b(opportunity|oportunidade|deal|neg[óo]cio)\b.*\b(to|para|as|como)\b",
        ]),
        handler=_handle_move_stage,
    ),
    Intent(
        name="forecast",
        patterns=_re([
            r"\b(forecast|forecasted|previs[ãa]o|proje(?:ç|c)[ãa]o)\b",
            r"\brevenue\s+by\s+(close|closing|expected)\b",
        ]),
        handler=_handle_forecast,
        fuzzy_keywords=["forecast|forecasted|previsao|projecao"],
    ),
    Intent(
        name="list_contacts_by_company",
        patterns=_re([
            r"\bwho\s+(?:works?|is)\s+at\b",
            r"\bcontacts?\s+at\b",
            r"\bcontatos?\s+(?:d[ea]|em|na|no)\b",
            r"\bquem\s+trabalha\s+(?:em|n[ao]s?)\b",
        ]),
        handler=_handle_contacts_at_company,
    ),
    Intent(
        name="mark_task_done",
        patterns=_re([
            r"\b(mark|complete|finish|conclu(?:ir|a|iu|i|ida?)|marcar|marque|encerrar)\b.*\b(task|tarefa)\b",
            r"^\s*conclu[iíaoue]{1,2}(?:r|a|iu|ir)?\s+(?:a\s+)?(?:tarefa\s+)?\S",
            r"^\s*marque?\s+como\s+(?:feit[ao]|conclu[íi]d[ao]|done)\s+\S",
        ]),
        handler=_handle_mark_task_done,
    ),
    Intent(
        # Direct entity lookup: "detalhes do contato Alice", "info da Big Deal"
        # Update field: "email do Alice é X" / "muda telefone do Bob para Y" / "update Alice email = Z"
        # Comes BEFORE entity_details so "email do Alice" (no value) still routes there.
        name="update_field",
        patterns=_re([
            # Form A: field first
            r"^\s*(?:atualize?|atualizar|muda|mude|mudar|edit|update|set|troca|troque|trocar)?\s*(?:o\s+|a\s+|the\s+)?(?:email|e-mail|telefone|phone|cargo|title|job[_\s]?title|nome|name|amount|valor|probabilidade|probability|website|site|dom[íi]nio|domain|ind[úu]stria|industry|score)\s+(?:do|da|de|of|from|for)\s+\S.*?\s*(?:é|=|:|\s+para|\s+to)\s+\S",
            # Form B: verb + subject + field + separator (EN order)
            r"^\s*(?:update|set|edit|muda|mude|atualize?|troca|troque)\s+\S.*?\s+(?:email|e-mail|telefone|phone|cargo|title|job[_\s]?title|nome|name|amount|valor|probabilidade|probability|website|site|dom[íi]nio|domain|ind[úu]stria|industry|score)\s+(?:=|to|para|é|:)\s+\S",
        ]),
        handler=_handle_update_field,
    ),
    Intent(
        name="entity_details",
        patterns=_re([
            r"^\s*(detalhes?|infos?|informa[çc][ãa]o|details|show|mostre?|open|abrir?)\s+(d[eoa]s?\s+|do\s+|da\s+|of\s+the\s+|of\s+|the\s+|o\s+|a\s+)?(contato|contact|empresa|company|oportunidade|opportunity|deal|neg[óo]cio|lead)\b",
            # Bare form: "oportunidade Big Deal" / "empresa Acme" — treat as details lookup
            r"^\s*(?:contato|contact|empresa|company|oportunidade|opportunity|deal|neg[óo]cio|lead)\s+\S",
        ]),
        handler=_handle_entity_details,
    ),
    Intent(
        # More specific: note attached to an entity. Must come before create_note.
        name="note_on_entity",
        patterns=_re([
            r"^\s*(?:nota|note)\s+(?:no|na|on|para|for|a[oa]?)\s+(?:o|a|the)?\s*(?:contato|contact|empresa|company|oportunidade|opportunity|lead|deal)\b",
        ]),
        handler=_handle_note_on_entity,
    ),
    Intent(
        name="create_note",
        patterns=_re([
            r"\b(create|add|criar|crie|adicionar|adicione|nova)\b.*\b(note|nota)\b",
            r"^\s*(note|nota)\s*[:\-]",
        ]),
        handler=_handle_create_note,
    ),
    Intent(
        name="create_contact",
        patterns=_re([
            r"^\s*(novo|new|adicione?|adicionar|add|crie?|cria|criar|create)\s+(o\s+|a\s+|um\s+|uma\s+|the\s+)?(contato|contact)\b",
        ]),
        handler=_handle_create_contact,
    ),
    Intent(
        name="create_company",
        patterns=_re([
            r"^\s*(nova|new|adicione?|adicionar|add|crie?|cria|criar|create)\s+(a\s+|uma\s+|the\s+)?(empresa|company)\b",
        ]),
        handler=_handle_create_company,
    ),
    Intent(
        name="create_opportunity",
        patterns=_re([
            r"^\s*(nova|new|adicione?|adicionar|add|crie?|cria|criar|create)\s+(a\s+|uma\s+|the\s+)?(oportunidade|opportunity|deal|neg[óo]cio|opp)\b",
        ]),
        handler=_handle_create_opportunity,
    ),
    Intent(
        name="current_date_time",
        patterns=_re([
            r"^\s*que\s+(dia|hora[s]?)\s+(é|e|s[aã]o)\s+(hoje|amanh[ãa]|ontem)?",
            r"^\s*(what|which)\s+(day|date|time)\s+(is\s+)?(it|today|tomorrow|yesterday)?",
            r"^\s*(today|hoje)\s+(date|data)\s*[?!.]?\s*$",
            r"^\s*(what|qual)\s+(time|hora)\s+is\s+it\b",
        ]),
        handler=_handle_current_date_time,
    ),
    Intent(
        name="activity_timeline",
        patterns=_re([
            r"\b(recent|latest|últimas?|ultimas?)\s+(activity|activities|atividades?)\b",
            r"\batividades?\s+recentes?\b",
            r"\b(timeline|linha\s+do\s+tempo|hist[óo]rico)\b",
        ]),
        handler=_handle_activity_timeline,
    ),
    Intent(
        name="find_company",
        patterns=_re([
            r"\b(find|search|buscar|busque|busca|localizar|localize|encontrar|encontre|procurar|procure|procura|ache)\b.*\b(company|companies|empresa|empresas)\b",
        ]),
        handler=_handle_find_company,
    ),
    Intent(
        name="summarize_pipeline",
        patterns=_re([
            r"\b(summari[sz]e|resum(o|ir)|show|mostre?|tell|diga|display)\s+(the\s+|o\s+|me\s+o\s+)?pipeline\b",
            r"\bpipeline\s+summary\b",
            r"^\s*pipeline\s*[?!.]?\s*$",  # bare "pipeline" as shortcut
            r"\bme\s+(diga|mostre|d[eê])\s+o?\s*pipeline\b",
        ]),
        handler=_handle_summarize_pipeline,
        # Typo tolerance — "resumir pipeine" or "sumarize pipelne" still resolve.
        fuzzy_keywords=["summarize|summarise|resumir|resumo|summary", "pipeline"],
    ),
    Intent(
        name="overdue_tasks",
        patterns=_re([
            r"\b(overdue|late)\s+tasks?\b",
            r"\btarefas?\s+(vencidas?|atrasadas?)\b",
        ]),
        handler=_handle_overdue_tasks,
        fuzzy_keywords=["overdue|late|vencidas|atrasadas", "task|tasks|tarefa|tarefas"],
    ),
    Intent(
        name="upcoming_meetings",
        patterns=_re([
            r"\b(upcoming|next)\s+(meetings?|calls?)\b",
            r"\b(pr[oó]ximas?)\s+(reuni[õo]es|reuni[oõ]es)\b",
            r"\breuni[õo]es?\s+(hoje|amanh[aã]|(?:d?esta|essa|nessa)?\s*semana|da\s+semana)\b",
            r"\bmeetings?\s+(today|tomorrow|this\s+week|next\s+week|of\s+the\s+week)\b",
        ]),
        handler=_handle_upcoming_meetings,
        fuzzy_keywords=["upcoming|next|proximas|proxima", "meetings|meeting|reunioes|reuniao"],
    ),
    Intent(
        name="top_opportunities",
        patterns=_re([
            r"\btop\s+\d+\s*(opportunities|deals|opps|oportunidades|neg[oó]cios)\b",
            r"\b(maiores|melhores)\s+\d*\s*(oportunidades|neg[oó]cios|deals)\b",
            r"\bbiggest\s+(deals|opportunities)\b",
            r"\btop\s+deals\b",
        ]),
        handler=_handle_top_opportunities,
    ),
    Intent(
        name="revenue_by_stage",
        patterns=_re([
            r"\b(revenue|value|pipeline|amount)\s+by\s+stage\b",
            r"\b(receita|valor|pipeline|montante)\s+por\s+(est[aá]gio|etapa)\b",
            r"\boportunidades?\s+por\s+(est[aá]gio|etapa)\b",
            r"\bopportunit(?:y|ies)\s+by\s+stage\b",
            r"\bstage\s+breakdown\b",
            r"\bbreakdown\s+by\s+stage\b",
        ]),
        handler=_handle_revenue_by_stage,
    ),
    Intent(
        name="daily_briefing",
        patterns=_re([
            r"\b(daily|do\s+dia)\s+(briefing|resumo)\b",
            r"\bbriefing\s+(do\s+dia|of\s+the\s+day|today)\b",
            r"\bwhat'?s?\s+my\s+day\b",
            r"^\s*meu\s+dia\s*[?!.]?\s*$",
            r"^\s*briefing\s*[?!.]?\s*$",
        ]),
        handler=_handle_daily_briefing,
    ),
    Intent(
        name="who_to_call_today",
        patterns=_re([
            r"\b(quem\s+devo\s+ligar|who\s+should\s+i\s+call|priorit(ies?|ários?)|prioridades?)(?:\s+(?:hoje|today))?\b",
            r"^\s*(who\s+to\s+call|quem\s+ligar|para\s+quem\s+ligar)\b",
        ]),
        handler=_handle_who_to_call_today,
    ),
    Intent(
        name="top_companies_by_opps",
        patterns=_re([
            r"\btop\s+(companies?|empresas?)\s+(by|por)\s+(opps?|deals?|oportunidades?|value|valor)\b",
            r"\bmelhores\s+empresas\s+(por\s+)?(oportunidades?|valor|deals?)\b",
            r"\bempresas?\s+com\s+mais\s+oportunidades\b",
        ]),
        handler=_handle_top_companies_by_opps,
    ),
    Intent(
        name="orphan_contacts",
        patterns=_re([
            r"\b(contatos?|contacts?)\s+(sem|without|órfãos|orfaos)\s+(empresa|company)\b",
            r"\borphan(ed)?\s+contacts\b",
            r"\bcontatos?\s+órfãos?\b",
        ]),
        handler=_handle_orphan_contacts,
    ),
    Intent(
        name="orphan_companies",
        patterns=_re([
            r"\b(empresas?|companies?)\s+(sem|without|órfãs|orfas)\s+(contatos?|contacts?)\b",
            r"\borphan(ed)?\s+companies\b",
            r"\bempresas?\s+órfãs?\b",
        ]),
        handler=_handle_orphan_companies,
    ),
    Intent(
        name="top_lead_sources",
        patterns=_re([
            r"\b(top|best|melhores|principais)\s+(lead\s+)?(sources|fontes)\b",
            r"\bfontes?\s+de\s+leads?\b",
            r"\blead\s+sources?\b",
        ]),
        handler=_handle_top_lead_sources,
    ),
    Intent(
        name="leads_by_status",
        patterns=_re([
            r"\bleads?\s+by\s+status\b",
            r"\bleads?\s+por\s+status\b",
            r"\bdistribui[cç][aã]o\s+de\s+leads?\b",
        ]),
        handler=_handle_leads_by_status,
    ),
    Intent(
        name="closing_this_week",
        patterns=_re([
            r"\b(closing|deals|opportunities)\s+(this\s+week)\b",
            r"\boportunidades?\s+(desta|essa|nesta|esta)?\s*semana\b",
            r"\b(fechando|fecha)\s+(esta|essa|nesta|desta)\s+semana\b",
        ]),
        handler=_handle_closing_this_week,
    ),
    Intent(
        name="closing_this_month",
        patterns=_re([
            r"\b(closing|deals|opportunities)\s+(this\s+month)\b",
            r"\b(fechando|fecham|fecha)\s+(este|nesse|esse|neste)?\s*m[êe]s\b",
            r"\boportunidades?\s+fechando\b",
            r"\boportunidades?\s+(deste|neste|desse)\s+m[êe]s\b",
            r"\bexpected\s+close\s+(this\s+)?month\b",
        ]),
        handler=_handle_closing_this_month,
    ),
    Intent(
        name="opportunities_at_company",
        patterns=_re([
            r"\b(oportunidades?|opportunit(?:ies|y)|deals?)\s+(d[ea]|em|na|no|at|from|for)\b",
        ]),
        handler=_handle_opportunities_at_company,
    ),
    Intent(
        name="insights",
        patterns=_re([
            r"^\s*(insights?|dicas?|sugest[õo]es|sugestao|tips?|advice)\s*[?!.]?\s*$",
            r"\bo\s+que\s+devo\s+fazer\s+agora\b",
            r"\bwhat\s+should\s+i\s+do\s+(now|next)\b",
            r"\bme\s+d[êe]\s+(dicas|insights|sugest[õo]es)\b",
        ]),
        handler=_handle_insights,
    ),
    Intent(
        name="onboarding",
        patterns=_re([
            r"^\s*(primeiros?\s+passos?|primeiros\s+passos)\b",
            r"^\s*(onboarding|walkthrough|wizard|tour)\b",
            r"^\s*(get\s+started|getting\s+started|start\s+here)\b",
            r"^\s*(comec(?:e|ei|ar)|come[çc]ar)\s+(agora|aqui|do\s+zero)?\b",
            r"\bcomo\s+(comec|com[eé]?[çc]?ar|iniciar|usar)(?:\s+(?:o\s+)?(?:visiquost|jarvis|crm))?\s*[?!.]?\s*$",
            r"\bhow\s+do\s+i\s+(start|begin|use)\b",
        ]),
        handler=_handle_onboarding,
    ),
    Intent(
        name="seed_demo",
        patterns=_re([
            r"\b(popular|popule?)\s+(demo|dados|exemplo|amostra)\b",
            r"\bseed\s+(demo|sample|data)\b",
            r"\bdemo\s+data\b",
            r"\bdados\s+de\s+(demo|exemplo|amostra)\b",
            r"\bpopular\s+(o\s+)?workspace\b",
        ]),
        handler=_handle_seed_demo,
    ),
    Intent(
        name="system_check",
        patterns=_re([
            r"\b(system\s+check|healthcheck|health\s+check|diagn[oó]stico|sanity\s+check)\b",
            r"\best[aá]\s+tudo\s+(bem|ok|certo)\b",
            r"\bstatus\s+(do\s+)?sistema\b",
            r"^\s*status\s*[?!.]?\s*$",
            r"\bcheck\s+system\b",
        ]),
        handler=_handle_system_check,
    ),
    Intent(
        name="urgent_tasks",
        patterns=_re([
            r"\btarefas?\s+urgentes?\b",
            r"\btarefas?\s+de\s+alta\s+prioridade\b",
            r"\b(high|urgent)\s+priorit(?:y|ies)\s+tasks?\b",
            r"\btasks?\s+(urgent|high\s+priority)\b",
            r"\b(urgent|high)\s+tasks?\b",
            r"\b(urgente|alta\s+prioridade)\s+tarefas?\b",
        ]),
        handler=_handle_urgent_tasks,
    ),
    Intent(
        name="top_leads",
        patterns=_re([
            r"\bmelhor(?:es)?\s+leads?\b",
            r"\btop\s+(\d+\s+)?leads?\b",
            r"\bleads?\s+(por|by)\s+score\b",
            r"\blead\s+com\s+maior\s+score\b",
            r"\bhigh(?:est)?[- ]score\s+leads?\b",
        ]),
        handler=_handle_top_leads,
    ),
    Intent(
        name="average_deal_size",
        patterns=_re([
            r"\bticket\s+m[eé]dio\b",
            r"\bvalor\s+m[eé]dio\s+(das?|do)?\s*(oportunidades?|deals?|neg[óo]cios)?\b",
            r"\baverage\s+(deal|opportunity)\s+size\b",
            r"\b(avg|average)\s+deal(?:\s+size)?\b",
        ]),
        handler=_handle_average_deal_size,
    ),
    Intent(
        name="go_home",
        patterns=_re([
            r"^\s*(dashboard|painel|home|inicio|início|main)\s*[?!.]?\s*$",
        ]),
        handler=_handle_go_home,
    ),
    Intent(
        # Mini-report on one lead by name: 'analise lead Bob'.
        name="analyze_lead",
        patterns=_re([
            r"^\s*(?:analise?|analisa|analyze|analyse)\s+(?:o\s+|a\s+|the\s+)?lead\s+\S",
        ]),
        handler=_handle_analyze_lead,
    ),
    Intent(
        # Mini-report on one company by name: 'analise empresa Acme'.
        # Must come BEFORE analyze_contact and analyze_opportunity.
        name="analyze_company",
        patterns=_re([
            r"^\s*(?:analise?|analisa|analyze|analyse)\s+(?:a\s+|the\s+)?(?:empresa|company)\s+\S",
        ]),
        handler=_handle_analyze_company,
    ),
    Intent(
        # Mini-report on one contact by name: 'analise contato Alice'.
        # Must come BEFORE analyze_opportunity since both start with 'analise'.
        name="analyze_contact",
        patterns=_re([
            r"^\s*(?:analise?|analisa|analyze|analyse)\s+(?:o\s+|a\s+|the\s+)?(?:contato|contact)\s+\S",
        ]),
        handler=_handle_analyze_contact,
    ),
    Intent(
        # Mini-report on one opportunity by name: 'analise Big Deal' / 'how is Big Deal doing?'
        name="analyze_opportunity",
        patterns=_re([
            r"^\s*(?:analise?|analisa|analyze|analyse)\s+(?:a\s+|o\s+|the\s+)?(?:oportunidade|opportunity|deal|neg[óo]cio|opp)?\s*\S",
            r"^\s*(?:status|report(?:\s+on)?)\s+(?:d[aeo]\s+)?(?:oportunidade|opportunity|deal|neg[óo]cio|opp)\s+\S",
            r"^\s*(?:how'?s|how\s+is|how\s+are|como\s+(?:est[áa]|vai|v[ãa]o))\s+(?:a\s+|o\s+|the\s+)?(?:oportunidade|opportunity|deal|neg[óo]cio|opp)?\s*\S.*?(?:\s+(?:doing|indo|going))?\s*[?!.]?\s*$",
        ]),
        handler=_handle_analyze_opportunity,
    ),
    Intent(
        # Filter open opps by amount: 'oportunidades acima de 10k' / 'deals > 50000'
        name="opportunities_by_amount",
        patterns=_re([
            r"^\s*(?:oportunidades?|opportunit(?:y|ies)|deals?|opps?)\s+(?:com\s+(?:valor\s+)?|acima\s+(?:de\s+)?|abaixo\s+(?:de\s+)?|maior(?:es)?\s+(?:que|do\s+que)\s+|menor(?:es)?\s+(?:que|do\s+que)\s+|above\s+|below\s+|over\s+|under\s+|greater\s+than\s+|less\s+than\s+|[><]=?)\s*R?\$?\s*\d",
        ]),
        handler=_handle_opportunities_by_amount,
    ),
    Intent(
        name="open_opportunities",
        patterns=_re([
            r"\bopen\s+opportunities\b",
            r"\boportunidades?\s+abertas?\b",
            r"\bopps?\s+(abertas?|open)\b",
            r"^\s*open\s+opps?\s*[?!.]?\s*$",
        ]),
        handler=_handle_open_opportunities,
        fuzzy_keywords=["open|abertas", "opportunities|opportunity|oportunidades|oportunidade"],
    ),
    Intent(
        name="opportunities_by_status",
        patterns=_re([
            r"\b(won|lost)\s+opportunities\b",
            r"\boportunidades?\s+(ganhas?|perdidas?|vencidas?)\b",
        ]),
        handler=_handle_opportunities_by_status,
    ),
    Intent(
        name="win_rate",
        patterns=_re([
            r"\bwin\s*rate\b",
            r"\bconversion\s+rate\b",
            r"\btaxa\s+de\s+(vit[óo]ria|convers[ãa]o|ganho)\b",
            r"\bconvers[ãa]o\s+(do\s+)?funil\b",
        ]),
        handler=_handle_win_rate,
    ),
    Intent(
        name="tasks_today",
        patterns=_re([
            r"\btarefas?\s+(de\s+|para\s+|hoje)",
            r"\bminhas\s+tarefas\b",
            r"\bmy\s+tasks\b",
            r"\btasks?\s+today\b",
            r"\btasks?\s+for\s+today\b",
            r"\btasks?\s+hoje\b",
        ]),
        handler=_handle_tasks_today,
    ),
    Intent(
        # Must come before create_task so "follow up with X" doesn't get swallowed
        name="follow_up",
        patterns=_re([
            r"^\s*(?:agende?|schedule|marque?|book|create|crie|criar)?\s*(?:um\s+|uma\s+|a\s+|the\s+)?(?:follow[\s-]?up|follow[\s-]?ups?|acompanhamento|retorno)\b",
            r"^\s*(?:ligar?|call|telefonar)\s+(?:com|para|to|with|a\s+|o\s+)?\S",
        ]),
        handler=_handle_follow_up,
    ),
    Intent(
        name="create_task",
        patterns=_re([
            r"\b(create|add|criar|crie|cria|adicionar|adicione|adiciona)\b.*\b(task|tarefa)\b",
            r"^lembre[-\s]me\s+(?:de|a|para)\s+",
            r"^me\s+lembr[ae]\s+",
            r"^lembrete\s*[:\-]",
            r"^remind\s+me\s+to\s+",
        ]),
        handler=_handle_create_task,
    ),
    Intent(
        name="find_contact",
        patterns=_re([
            # Parens matter — without them the second alternative fires on the
            # bare word "contact" anywhere in the text.
            r"\b(find|search|buscar|busque|busca|localizar|localize|encontrar|encontre|procurar|procure|procura|ache)\b.*\b(contat[oa]|contact)\b",
        ]),
        handler=_handle_find_contact,
    ),
    Intent(
        name="search_everywhere",
        patterns=_re([
            r"\b(search|find|look\s+up|procurar|procure|buscar|localizar|encontr(?:e|ar))\b\s+(everywhere|anywhere|em\s+tudo|por\s+tudo)\b",
            r"\bsearch\s+everywhere\s+for\b",
            r"\bfind\s+anywhere\b",
            # Bare "verb X" where X isn't a scoped entity kind — global search.
            # find/search/busca/ache/localize <name> — but NOT when scoped to
            # a specific entity (find_contact/find_company handle those).
            r"^\s*(busca|buscas|busque|buscar|search|find|ache|acha|acho|encontre|encontrar|procure|procura|procurar|localize|localizar)\s+(por\s+|for\s+|a\s+|o\s+)?(?!(?:contato|contact|empresa|company|oportunidade|opportunity|deal|neg[óo]cio|lead|task|tarefa|nota|note)\b)\S",
            r"^\s*onde\s+(est[áa]|fica|encontro)\s+",
            # "quem é X" / "who is X" / "me fale de X" / "tell me about X"
            r"^\s*quem\s+(é|eh|e)\s+(?!(?:voc[eê]|jarvis)\b)\S",
            r"^\s*who\s+is\s+(?!(?:the|jarvis)\b)\S",
            r"^\s*(me\s+fale|me\s+conte|me\s+diga|diga|conte|fale|tell\s+me)\s+(sobre|de|da|do|about)\s+(?!(?:o\s+jarvis|voc[eê]|yourself)\b)\S",
        ]),
        handler=_handle_search_everywhere,
    ),
    Intent(
        name="recalculate_lead_scores",
        patterns=_re([
            r"\b(recalculate|recompute|rescore|recalcular|reprocessar)\b.*\b(lead|leads|scores?|pontua(?:ç|c)[ãa]o|pontua(?:ç|c)[ãa]oes)\b",
            r"\bscore\s+all\s+leads\b",
        ]),
        handler=_handle_recalculate_scores,
    ),
    Intent(
        name="thanks",
        patterns=_re([
            r"^\s*(thanks|thank\s+you|thx|obrigad[oa]|valeu|vlw)\b",
            r"^\s*(ok|okay|beleza|blz|kk|k|fmz|firmeza|show|show\s+de\s+bola|top|maneiro|d[ae]hora|dhora|tmj|tamo\s+junto|ta\s+bom|t[áa]\s+bom|t[áa]\s+ok)\s*[?!.]?\s*$",
            r"^\s*ok\s+obrigad[oa]\b",
            r"^\s*(sounds\s+good|got\s+it|cool|nice)\b",
        ]),
        handler=_handle_thanks,
    ),
    Intent(
        name="goodbye",
        patterns=_re([
            r"^\s*(bye|goodbye|tchau|até\s+(mais|logo)|ate\s+(mais|logo)|falou|flw|sair|exit|quit|xau|adeus|see\s+you|cya)\s*[.!]?\s*$",
        ]),
        handler=_handle_goodbye,
    ),
    Intent(
        name="who_am_i",
        patterns=_re([
            r"^\s*(who\s+am\s+i|quem\s+sou(\s+eu)?|meu\s+nome|my\s+name)\s*[?!.]?\s*$",
        ]),
        handler=_handle_who_am_i,
    ),
    Intent(
        name="count",
        patterns=_re([
            r"\bhow\s+many\b",
            r"\bquant[oa]s\b",
            r"\btotal\s+(de\s+|of\s+)?(contatos?|contacts?|empresas?|companies|leads?|oportunidades?|opportunit(?:y|ies)|tarefas?|tasks?|deals?|neg[óo]cios?)\b",
            r"\b(quantidade|n[uú]mero|count)\s+(de\s+|of\s+)?(contatos?|contacts?|empresas?|companies|leads?|oportunidades?|opportunit(?:y|ies)|tarefas?|tasks?|deals?|neg[óo]cios?)\b",
        ]),
        handler=_handle_count,
    ),
    Intent(
        name="list_all_contacts",
        patterns=_re([
            r"^\s*(?:list(?:e|ar|\s+all)?|mostre?|todos?|todas?)\s+(?:os\s+|as\s+|the\s+)?contat[oa]s?\b",
            r"^\s*all\s+contacts?\s*[?!.]?\s*$",
            r"^\s*contat[oa]s?\s*[?!.]?\s*$",  # bare "contatos" / "contactos"
            r"^\s*(?:meus|minhas|my)\s+(?:contat[oa]s?|contacts?)\b",  # "meus contatos" / "my contacts"
        ]),
        handler=lambda i, t, s, c: _handle_list_all(i, t, s, c, "contact"),
    ),
    Intent(
        name="list_all_companies",
        patterns=_re([
            r"^\s*(?:list(?:e|ar|\s+all)?|mostre?|todas?|todos?)\s+(?:as\s+|the\s+)?(?:empresas?|companies|company)\b",
            r"^\s*all\s+compan(y|ies)\s*[?!.]?\s*$",
            r"^\s*empresas?\s*[?!.]?\s*$",  # bare "empresas"
            r"^\s*(?:minhas?|meus|my)\s+empresas?\b",  # "minha empresa"
        ]),
        handler=lambda i, t, s, c: _handle_list_all(i, t, s, c, "company"),
    ),
    Intent(
        name="list_all_opportunities",
        patterns=_re([
            r"^\s*(?:list(?:e|ar|\s+all)?|mostre?|todas?|todos?)\s+(?:as\s+|the\s+)?(?:oportunidades?|opportunities|deals?|opps?)\b",
            r"^\s*(?:oportunidades?|opportunit(?:y|ies)|deals?)\s*[?!.]?\s*$",  # bare
            r"^\s*(?:meus|minhas?|my)\s+(?:oportunidades?|opportunit(?:y|ies)|deals?|opps?)\b",
        ]),
        handler=lambda i, t, s, c: _handle_list_all(i, t, s, c, "opportunity"),
    ),
    Intent(
        name="pipeline_total",
        patterns=_re([
            r"\b(total|soma|sum)\s+(do\s+|of\s+the\s+|of\s+)?pipeline\b",
            r"\bvalor\s+total\s+(do\s+)?pipeline\b",
            r"\bquanto\s+(vale|tem)\s+(meu\s+|o\s+|no\s+)?pipeline\b",
            r"\bpipeline\s+(total|value|worth)\b",
        ]),
        handler=lambda i, t, s, c: _handle_pipeline_total(i, t, s, c),
    ),
    Intent(
        name="biggest_opportunity",
        patterns=_re([
            r"\bmaior\s+(oportunidade|deal|neg[óo]cio)\b",
            r"\bbiggest\s+(opportunity|deal)\b",
            r"\btop\s+deal\b",
        ]),
        handler=lambda i, t, s, c: _handle_top_opportunities(
            Intent(name="top_opportunities", patterns=[], handler=_handle_top_opportunities),
            "top 1 opportunities", s, c,
        ),
    ),
]


def _handle_list_all(intent, text, snap, ctx, kind: str):
    """List all entities of a given kind (contact/company/opportunity), capped at 25."""
    lang = _detect_lang(text)
    from sqlmodel import select
    if kind == "contact":
        from app.models import Contact
        rows = list(ctx.session.exec(
            select(Contact).where(
                Contact.workspace_id == ctx.workspace_id,
                Contact.deleted_at.is_(None),
            ).order_by(Contact.first_name.asc()).limit(25)
        ).all())
        if not rows:
            return IntentResult.ok(
                "Nenhum contato ainda." if lang == "pt" else "No contacts yet.",
                intent="list_all_contacts", confidence=0.9,
            )
        header = f"Contatos ({len(rows)}):" if lang == "pt" else f"Contacts ({len(rows)}):"
        lines = [header]
        for i, c in enumerate(rows, 1):
            name = f"{c.first_name} {c.last_name or ''}".strip()
            det = c.email or ""
            lines.append(f"  {i}. {name}{(' — ' + det) if det else ''}")
        return IntentResult.ok(
            "\n".join(lines), intent="list_all_contacts", confidence=0.94,
            tool_calls=[{"name": "recent_list", "kind": "contact",
                         "items": [{"id": str(c.id),
                                    "name": f"{c.first_name} {c.last_name or ''}".strip()} for c in rows]}],
        )
    if kind == "company":
        from app.models import Company
        rows = list(ctx.session.exec(
            select(Company).where(
                Company.workspace_id == ctx.workspace_id,
                Company.deleted_at.is_(None),
            ).order_by(Company.name.asc()).limit(25)
        ).all())
        if not rows:
            return IntentResult.ok(
                "Nenhuma empresa ainda." if lang == "pt" else "No companies yet.",
                intent="list_all_companies", confidence=0.9,
            )
        header = f"Empresas ({len(rows)}):" if lang == "pt" else f"Companies ({len(rows)}):"
        lines = [header]
        for i, o in enumerate(rows, 1):
            det = o.domain or ""
            lines.append(f"  {i}. {o.name}{(' — ' + det) if det else ''}")
        return IntentResult.ok(
            "\n".join(lines), intent="list_all_companies", confidence=0.94,
        )
    if kind == "opportunity":
        from app.models import Opportunity
        rows = list(ctx.session.exec(
            select(Opportunity).where(
                Opportunity.workspace_id == ctx.workspace_id,
                Opportunity.deleted_at.is_(None),
            ).order_by(Opportunity.amount.desc().nulls_last()).limit(25)
        ).all())
        if not rows:
            return IntentResult.ok(
                "Nenhuma oportunidade ainda." if lang == "pt" else "No opportunities yet.",
                intent="list_all_opportunities", confidence=0.9,
            )
        header = f"Oportunidades ({len(rows)}):" if lang == "pt" else f"Opportunities ({len(rows)}):"
        lines = [header]
        for i, o in enumerate(rows, 1):
            lines.append(f"  {i}. {o.name} — {_fmt_money(o.amount, o.currency)}")
        return IntentResult.ok(
            "\n".join(lines), intent="list_all_opportunities", confidence=0.94,
            tool_calls=[{"name": "recent_list", "kind": "opportunity",
                         "items": [{"id": str(o.id), "name": o.name} for o in rows]}],
        )
    return IntentResult(handled=False)


def _handle_pipeline_total(intent, text, snap, ctx):
    """Sum of amount * probability across open opportunities (weighted pipeline)."""
    from sqlmodel import select
    from app.models import Opportunity, OpportunityStatus
    lang = _detect_lang(text)
    opps = list(ctx.session.exec(
        select(Opportunity).where(
            Opportunity.workspace_id == ctx.workspace_id,
            Opportunity.deleted_at.is_(None),
            Opportunity.status == OpportunityStatus.open,
        )
    ).all())
    total = sum(o.amount or 0 for o in opps)
    weighted = sum((o.amount or 0) * (o.probability or 0) / 100.0 for o in opps)
    currency = opps[0].currency if opps else "USD"
    if lang == "pt":
        body = (f"💰 Pipeline: {_fmt_money(total, currency)} bruto · "
                f"{_fmt_money(weighted, currency)} ponderado · {len(opps)} oportunidades abertas")
    else:
        body = (f"💰 Pipeline: {_fmt_money(total, currency)} raw · "
                f"{_fmt_money(weighted, currency)} weighted · {len(opps)} open opportunities")
    return IntentResult.ok(body, intent="pipeline_total", confidence=0.94)


# ---- Message normalization for typo/accent tolerance ---------------------
import unicodedata

def _normalize_message(msg: str) -> str:
    """Strip accents, collapse whitespace, lowercase — for permissive matching."""
    if not msg:
        return ""
    nfkd = unicodedata.normalize("NFKD", msg)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_only.strip().lower())


# Common misspelling → canonical hints (added incrementally as bugs surface)
_TYPO_MAP = {
    "opotunidades": "oportunidades",
    "oportunidads": "oportunidades",
    "oportuidade": "oportunidade",
    "reuniao": "reunião",
    "rewunião": "reunião",
    "reunioes": "reuniões",
    "tarefass": "tarefas",
    "contatoss": "contatos",
    "epresa": "empresa",
    "empersas": "empresas",
    "agndar": "agendar",
    "pipiline": "pipeline",
    "pilepine": "pipeline",
    "agenta": "agenda",
    "calenrio": "calendário",
    "leds": "leads",
    "briefng": "briefing",
    "resmo": "resumo",
    "briefigng": "briefing",
    # EN
    "oppotunities": "opportunities",
    "opportuniites": "opportunities",
    "oportunities": "opportunities",
    "cotacts": "contacts",
    "comapny": "company",
    "comapnies": "companies",
    "meating": "meeting",
    "brieifng": "briefing",
    "shedule": "schedule",
    "schedual": "schedule",
    "calnedar": "calendar",
    "sumary": "summary",
    "conatct": "contact",
    "contactss": "contacts",
    "opportuniy": "opportunity",
    "opportunies": "opportunities",
    "delelte": "delete",
    "creat": "create",
    "reunio": "reunião",
    "reunuiao": "reunião",
    "reuniåo": "reunião",
    "amanha": "amanhã",
    "prox": "próximas",
    "proximas": "próximas",
    "proximo": "próximo",
    "hj": "hoje",
    "ajd": "ajuda",
    "hlp": "help",
}


def _apply_typo_corrections(msg: str) -> str:
    tokens = msg.split()
    corrected = [_TYPO_MAP.get(t.lower(), t) for t in tokens]
    if any(a != b for a, b in zip(tokens, corrected)):
        return " ".join(corrected)
    return msg


# Similarity-based fallback suggestion (when no intent matches)
_INTENT_HINTS_PT = {
    "help": "\"ajuda\" — o que o Jarvis faz",
    "greeting": "\"oi\" — cumprimento e visão geral",
    "briefing": "\"meu dia\" — resumo matinal",
    "week_summary": "\"resumo da semana\" ou \"esta semana\"",
    "pipeline": "\"pipeline\" — resumo das oportunidades abertas",
    "overdue": "\"tarefas atrasadas\" — o que passou do prazo",
    "top_opps": "\"top 5 oportunidades\" — ranking por valor",
    "calendar": "\"minha agenda\" — próximos eventos (.ics)",
    "meetings": "\"próximas reuniões\" — nas próximas 48h",
    "create": "\"crie tarefa: <título>\" — para novos itens",
    "focus": "\"ajude a focar\" — 3 ações prioritárias",
    "call_today": "\"quem devo ligar hoje\" — priorização automática",
    "files": "\"meus arquivos\" — lista da pasta de trabalho",
    "import": "\"importe contatos\" — de .csv/.vcf",
}
_INTENT_HINTS_EN = {
    "help": "\"help\" — what Jarvis can do",
    "greeting": "\"hi\" — greet and orient",
    "briefing": "\"what's my day\" — morning briefing",
    "week_summary": "\"this week\" — weekly rollup",
    "pipeline": "\"pipeline\" — open opportunities",
    "overdue": "\"overdue tasks\" — what's past due",
    "top_opps": "\"top 5 opportunities\" — ranked by value",
    "calendar": "\"my calendar\" — upcoming events (.ics)",
    "meetings": "\"upcoming meetings\" — next 48h",
    "create": "\"create task: <title>\" — for new items",
    "focus": "\"help me focus\" — 3 top priorities",
    "call_today": "\"who should I call today\" — auto-prioritized",
    "files": "\"my files\" — list work-dir contents",
    "import": "\"import contacts\" — from .csv/.vcf",
}


def _suggest_by_keyword(msg: str, lang: str) -> list[str]:
    """Given an unrecognized message, suggest 3 relevant commands based on keyword overlap."""
    tokens = set(re.findall(r"\w+", msg.lower()))
    hints = _INTENT_HINTS_PT if lang == "pt" else _INTENT_HINTS_EN
    KEYWORDS = {
        "help": ["ajuda", "help", "que", "what", "pode"],
        "greeting": ["oi", "olá", "hi", "hello"],
        "briefing": ["dia", "day", "hoje", "today", "brief"],
        "week_summary": ["semana", "week", "resumo", "summary"],
        "pipeline": ["pipeline", "opps", "oportunidades", "deals", "vendas"],
        "overdue": ["atrasadas", "overdue", "vencidas", "atrasa"],
        "top_opps": ["top", "maiores", "melhores", "biggest", "ranking"],
        "calendar": ["agenda", "calendar", "calendário", "eventos", "events"],
        "meetings": ["reunioes", "reuniões", "reunião", "meetings", "meeting"],
        "create": ["criar", "crie", "create", "nova", "new"],
        "focus": ["focar", "focus", "foco", "prioridade"],
        "call_today": ["ligar", "call", "phone", "contatar"],
        "files": ["arquivos", "files", "pasta", "folder"],
        "import": ["importar", "import", "csv", "vcf", "contatos"],
    }
    scored = []
    for key, kw_list in KEYWORDS.items():
        overlap = len(tokens & set(kw_list))
        if overlap > 0:
            scored.append((overlap, key))
    scored.sort(reverse=True)
    picked = [hints[k] for _, k in scored[:3] if k in hints]
    if not picked:
        picked = list(hints.values())[:3]
    return picked


# --- Conversational context ---------------------------------------------------
# Words that look like a numeric pick after Jarvis asked "which one?"
_PICK_NUMBER_RE = re.compile(
    r"^\s*(?:(?:o\s+)?(?:primeiro|primeira|1[oª°]?)|"
    r"(?:o\s+|a\s+)?(?:segundo|segunda|2[oª°]?)|"
    r"(?:o\s+|a\s+)?(?:terceiro|terceira|3[oª°]?)|"
    r"(?:the\s+)?(?:first|1st)|(?:the\s+)?(?:second|2nd)|(?:the\s+)?(?:third|3rd)|"
    r"([1-9]))\s*[.!]?\s*$",
    re.IGNORECASE,
)


def _parse_pick_number(message: str) -> int | None:
    """Return the 1-based index the user picked, or None."""
    m = _PICK_NUMBER_RE.match(message.strip())
    if not m:
        return None
    lower = message.strip().lower()
    if m.group(1):
        return int(m.group(1))
    if "primeiro" in lower or "primeira" in lower or "first" in lower or lower.startswith("1"):
        return 1
    if "segundo" in lower or "segunda" in lower or "second" in lower or lower.startswith("2"):
        return 2
    if "terceiro" in lower or "terceira" in lower or "third" in lower or lower.startswith("3"):
        return 3
    return None


_ORDINAL_WORDS = {
    "primeiro": 1, "primeira": 1, "first": 1, "1o": 1, "1a": 1, "1º": 1, "1ª": 1,
    "segundo": 2, "segunda": 2, "second": 2, "2o": 2, "2a": 2, "2º": 2, "2ª": 2,
    "terceiro": 3, "terceira": 3, "third": 3, "3o": 3, "3a": 3, "3º": 3, "3ª": 3,
    "quarto": 4, "quarta": 4, "fourth": 4,
    "quinto": 5, "quinta": 5, "fifth": 5,
}


def _pick_ordinal_from_message(message: str) -> int | None:
    """Extract an ordinal reference like 'a segunda', 'the first', '#2', 'o 3o' from a message."""
    lower = _normalize(message).strip()
    # #N or "numero N" style
    m = re.search(r"[#nº]\s*(\d)\b", lower)
    if m:
        return int(m.group(1))
    m = re.search(r"\bn(?:umero)?\s*(\d)\b", lower)
    if m:
        return int(m.group(1))
    # Ordinal word anywhere
    for word, num in _ORDINAL_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", lower):
            return num
    return None


def _contact_details_reply(session: Session, workspace_id: UUID, contact_id: str | None, lang: str) -> str | None:
    """Return a short details reply for a contact by id, or None if not found."""
    if not contact_id:
        return None
    try:
        c_uuid = UUID(contact_id)
    except (ValueError, TypeError):
        return None
    from sqlmodel import select
    from app.models import Contact
    c = session.exec(
        select(Contact).where(
            Contact.id == c_uuid,
            Contact.workspace_id == workspace_id,
            Contact.deleted_at.is_(None),
        )
    ).first()
    if not c:
        return None
    name = f"{c.first_name} {c.last_name or ''}".strip()
    if lang == "pt":
        parts = [f"👤 {name}"]
        if c.email:
            parts.append(f"  Email: {c.email}")
        if c.phone:
            parts.append(f"  Telefone: {c.phone}")
        if c.job_title:
            parts.append(f"  Cargo: {c.job_title}")
    else:
        parts = [f"👤 {name}"]
        if c.email:
            parts.append(f"  Email: {c.email}")
        if c.phone:
            parts.append(f"  Phone: {c.phone}")
        if c.job_title:
            parts.append(f"  Role: {c.job_title}")
    return "\n".join(parts)


def _opportunity_details_reply(session: Session, workspace_id: UUID, opp_id: str | None, lang: str) -> str | None:
    """Return a short details reply for an opportunity by id, or None if not found."""
    if not opp_id:
        return None
    try:
        opp_uuid = UUID(opp_id)
    except (ValueError, TypeError):
        return None
    from sqlmodel import select
    from app.models import Opportunity
    opp = session.exec(
        select(Opportunity).where(
            Opportunity.id == opp_uuid,
            Opportunity.workspace_id == workspace_id,
            Opportunity.deleted_at.is_(None),
        )
    ).first()
    if not opp:
        return None
    if lang == "pt":
        parts = [f"📊 {opp.name}"]
        parts.append(f"  Valor: {opp.currency} {opp.amount:,.0f}")
        parts.append(f"  Probabilidade: {opp.probability:.0f}%")
        parts.append(f"  Status: {opp.status.value if hasattr(opp.status, 'value') else opp.status}")
        if opp.expected_close_date:
            parts.append(f"  Fechamento previsto: {opp.expected_close_date}")
    else:
        parts = [f"📊 {opp.name}"]
        parts.append(f"  Amount: {opp.currency} {opp.amount:,.0f}")
        parts.append(f"  Probability: {opp.probability:.0f}%")
        parts.append(f"  Status: {opp.status.value if hasattr(opp.status, 'value') else opp.status}")
        if opp.expected_close_date:
            parts.append(f"  Expected close: {opp.expected_close_date}")
    return "\n".join(parts)


def _sqlmodel_select_by_id(model, obj_id: str, workspace_id):
    """Build a select for `model` scoped to workspace + id (soft-delete safe)."""
    from sqlmodel import select
    return select(model).where(
        model.id == UUID(obj_id),
        model.workspace_id == workspace_id,
        model.deleted_at.is_(None),
    )


def _resume_from_ambiguity(pending: dict, picked_option: dict) -> str | None:
    """Rewrite the original user message so the picked contact's name replaces
    the ambiguous field. Returns the new message, or None if unsupported."""
    original = pending.get("original_message", "") or ""
    field = pending.get("field")
    if field != "who":
        return None
    picked_name = (picked_option.get("name") or "").strip()
    if not picked_name:
        return None
    # Replace anywhere after "com "/"with " up to a boundary
    # Keep it simple: rebuild by swapping the who token with picked_name.
    m = _SCHEDULE_MEETING_RE.search(original.strip())
    if not m:
        return None
    who_span = m.span("who")
    if who_span == (-1, -1):
        return None
    start, end = who_span
    return original[:start] + picked_name + original[end:]


# --- Pronoun resolution (cross-turn) -----------------------------------------
_PRONOUN_RE = re.compile(
    r"\b(?:ela|ele|dela|dele|a\s+ela|o\s+ele|her|him|she|he|it|its|"
    r"aquela|aquele|essa|esse|este|esta|this|that)\b",
    re.IGNORECASE,
)


def _extract_last_entity_name(conv_ctx: dict | None) -> str | None:
    """Look through last assistant turn's tool_calls for a mentioned entity name."""
    if not conv_ctx:
        return None
    for tc in (conv_ctx.get("last_tool_calls") or []):
        if not isinstance(tc, dict):
            continue
        # Result.name (e.g. create_contact returns {"result": {"name": "Alice Silva"}})
        result = tc.get("result") or {}
        if isinstance(result, dict) and result.get("name"):
            return str(result["name"])
        # Input.entity (note_on_entity)
        inp = tc.get("input") or {}
        if isinstance(inp, dict):
            if inp.get("entity"):
                return str(inp["entity"])
            if inp.get("name"):
                return str(inp["name"])
            # Compose first + last name
            if inp.get("first_name"):
                fn = str(inp["first_name"])
                ln = inp.get("last_name") or ""
                return f"{fn} {ln}".strip()
        # options[0].name (contact_choice/delete_choice — user hasn't picked yet)
        opts = tc.get("options") or []
        if opts and isinstance(opts, list) and isinstance(opts[0], dict) and opts[0].get("name"):
            return str(opts[0]["name"])
    return None


def _resolve_pronouns(message: str, conv_ctx: dict | None) -> str:
    """Replace pronouns (ela/ele/it/dela/dele) with the last mentioned entity."""
    if not _PRONOUN_RE.search(message):
        return message
    name = _extract_last_entity_name(conv_ctx)
    if not name:
        return message
    return _PRONOUN_RE.sub(name, message)


class LocalJarvis:
    def __init__(self, intents: list[Intent] | None = None):
        self.intents = intents or DEFAULT_INTENTS

    def handle(
        self,
        session: Session,
        workspace_id: UUID,
        user_id: UUID,
        message: str,
        registry: ToolRegistry | None = None,
        conversation_context: dict | None = None,
    ) -> IntentResult:
        message = (message or "").strip()
        if not message:
            return IntentResult.ok("(empty message)", intent="empty", confidence=1.0)

        # Pronoun resolution: replace ela/ele/dela/dele/it/etc. with the last
        # mentioned entity name from the conversation context.
        message = _resolve_pronouns(message, conversation_context)

        # 0) Ambiguity resumption — if last assistant turn asked "which one?" and
        # this message is just a number pick, resume the original intent with
        # the picked option substituted in.
        if conversation_context:
            pending = None
            recent_list = None
            for tc in (conversation_context.get("last_tool_calls") or []):
                if isinstance(tc, dict) and tc.get("name") == "ambiguity" and not pending:
                    pending = tc
                if isinstance(tc, dict) and tc.get("name") == "recent_list" and not recent_list:
                    recent_list = tc
            if pending:
                idx = _parse_pick_number(message)
                options = pending.get("options") or []
                if idx and 1 <= idx <= len(options):
                    picked = options[idx - 1]
                    kind = pending.get("kind")
                    # delete_choice: pick + execute the delete
                    if kind == "delete_choice":
                        from datetime import datetime, timezone
                        from app.models import Contact, Company, Opportunity, Lead
                        model_map = {
                            "contact": Contact, "company": Company,
                            "opportunity": Opportunity, "lead": Lead,
                        }
                        pick_kind = picked.get("kind")
                        model = model_map.get(pick_kind)
                        if model:
                            try:
                                obj = session.exec(
                                    _sqlmodel_select_by_id(model, picked.get("id"),
                                                           workspace_id)
                                ).first()
                            except Exception:
                                obj = None
                            if obj is not None:
                                obj.deleted_at = datetime.now(timezone.utc)
                                session.add(obj)
                                session.commit()
                                disp = picked.get("name", "?")
                                lang = _detect_lang(message)
                                return IntentResult.ok(
                                    f"🗑 {pick_kind.capitalize()} \"{disp}\" apagado." if lang == "pt"
                                    else f"🗑 {pick_kind.capitalize()} \"{disp}\" deleted.",
                                    intent=f"delete_{pick_kind}", confidence=0.94,
                                    tool_calls=[{"name": f"delete_{pick_kind}",
                                                 "input": {"id": picked.get("id")}}],
                                )
                    # contact_choice (schedule_meeting): rewrite + retry
                    rewritten = _resume_from_ambiguity(pending, picked)
                    if rewritten:
                        result = self._try_match(rewritten, session, workspace_id, user_id, conversation_context)
                        if result and result.handled:
                            return result
            # Reference the Nth item from a recent list: "a segunda", "the first",
            # "mostre #2", "o 3o". Directly return details of that item.
            if recent_list:
                idx = _pick_ordinal_from_message(message)
                items = recent_list.get("items") or []
                if idx and 1 <= idx <= len(items):
                    picked = items[idx - 1]
                    kind = recent_list.get("kind")
                    lang = _detect_lang(message)
                    if kind == "opportunity":
                        reply = _opportunity_details_reply(session, workspace_id, picked.get("id"), lang)
                        if reply is not None:
                            return IntentResult.ok(
                                reply, intent="opportunity_details", confidence=0.9,
                                tool_calls=[{"name": "opportunity_details", "input": {"id": picked.get("id")}}],
                            )
                    elif kind == "contact":
                        reply = _contact_details_reply(session, workspace_id, picked.get("id"), lang)
                        if reply is not None:
                            return IntentResult.ok(
                                reply, intent="contact_details", confidence=0.9,
                                tool_calls=[{"name": "contact_details", "input": {"id": picked.get("id")}}],
                            )

        # Try 1: raw message
        result = self._try_match(message, session, workspace_id, user_id, conversation_context)
        if result and result.handled:
            return result
        # Try 2: typo-corrected message
        corrected = _apply_typo_corrections(message)
        if corrected != message:
            result = self._try_match(corrected, session, workspace_id, user_id, conversation_context)
            if result and result.handled:
                # Signal correction in reply
                result.reply = f"(entendi \"{corrected}\") {result.reply}"
                return result
        # Fallback: suggest similar commands based on keyword overlap
        lang = _detect_lang(message)
        suggestions = _suggest_by_keyword(message, lang)
        if lang == "pt":
            body = "Não reconheci o comando. Sugiro uma das alternativas:\n" + \
                "\n".join(f"  • {s}" for s in suggestions) + \
                "\n\nDiga \"ajuda\" para o inventário completo."
        else:
            body = "Command not recognised. May I suggest one of the following:\n" + \
                "\n".join(f"  • {s}" for s in suggestions) + \
                "\n\nSay \"help\" for the full inventory."
        return IntentResult.escalate(body)

    def _try_match(self, message, session, workspace_id, user_id, conversation_context=None):
        snap = build_workspace_context(session, workspace_id, user_id)
        ctx = ToolContext(
            session=session, workspace_id=workspace_id, user_id=user_id,
            conversation_context=conversation_context,
        )
        for intent in self.intents:
            if intent.matches(message):
                result = intent.handler(intent, message, snap, ctx)
                if result.handled:
                    return result
        return None
