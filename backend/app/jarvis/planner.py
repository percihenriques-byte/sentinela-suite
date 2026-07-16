"""Very small agent-style planner for Jarvis.

Given a compound user request, splits it into steps and runs each through
the local intent engine, returning a plan (list of steps with results) that
the frontend renders as a Manus-like checklist.

Deliberately minimal: no LLM required. Splits on connectors like
"e depois", "and then", "; " or a leading numbered list. If a single-step
request slips through, we still wrap it in a 1-step plan so the UI has a
consistent shape.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from app.jarvis.local_engine import LocalJarvis, _detect_lang
from app.jarvis.tools import ToolContext


# Split points (case-insensitive). Order matters: longer/multi-word before short.
_SPLIT_PATTERNS = [
    r"\s+e\s+depois\s+",
    r"\s+e\s+em\s+seguida\s+",
    r"\s+and\s+then\s+",
    r"\s+then\s+",
    r"\s*;\s+",
    r"\s*,\s+depois\s+",
    r"\s*,\s+then\s+",
]
_SPLIT_RE = re.compile("|".join(_SPLIT_PATTERNS), re.IGNORECASE)

# Smart split on bare "e" / "and" WHEN followed by a command verb (Manus-like).
# Matches: "crie contato X E crie tarefa Y" (splits) but not "com José E Maria" (doesn't).
_ACTION_VERBS_PT = (
    r"(?:crie|criar|agende|marque|mova|apague|apagar|delete|delet|liste|listar|mostre?|"
    r"conclu(?:ir|a|iu|i)|encerrar|adicione|adicionar|popular|populem?|"
    r"envie?|enviar|escreva|escrever|gere|gerar|leia|abrir?|abra|nova|novo|salve?|salvar|"
    r"resuma|resumir|foca?|focar|remova|remover|excluir|encontr(?:e|ar)|"
    r"detalhes?|infos?|informa[çc][ãa]o|status|briefing)"
)
_ACTION_VERBS_EN = (
    r"(?:create|schedule|book|mark|move|delete|remove|list|show|complete|finish|add|"
    r"send|write|generate|read|open|save|summari[sz]e|focus|find|search|status|briefing)"
)
_SMART_SPLIT_RE = re.compile(
    rf"\s+(?:e|and)\s+(?={_ACTION_VERBS_PT}|{_ACTION_VERBS_EN})",
    re.IGNORECASE,
)

# Detect a numbered list: "1. do X 2. do Y" or "1) do X 2) do Y"
_NUMBERED = re.compile(r"(?:^|\s)(\d+)[\.\)]\s+")


@dataclass
class PlanStep:
    index: int
    text: str
    intent: str | None = None
    reply: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = True


@dataclass
class Plan:
    original: str
    steps: list[PlanStep]
    combined_reply: str


def _split_into_steps(text: str) -> list[str]:
    """Return the list of sub-requests. Never empty."""
    text = text.strip()
    if not text:
        return []
    # Numbered list wins if present
    if _NUMBERED.search(text):
        parts = _NUMBERED.split(text)
        # Split produces ['', '1', 'do X ', '2', 'do Y'] — take odd-indexed only
        picked = [parts[i + 1].strip() for i in range(1, len(parts), 2) if i + 1 < len(parts)]
        picked = [p for p in picked if p]
        if picked:
            return picked
    # Split on explicit connectors first (e depois / and then / ; etc.)
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p.strip()]
    if len(parts) > 1:
        return parts
    # Smart split on bare "e"/"and" when followed by a command verb
    smart = [p.strip() for p in _SMART_SPLIT_RE.split(text) if p.strip()]
    return smart or [text]


class AgentPlanner:
    def __init__(self, engine: LocalJarvis | None = None):
        self.engine = engine or LocalJarvis()

    def plan(self, text: str) -> list[str]:
        return _split_into_steps(text)

    def run(
        self,
        session: Session,
        workspace_id,
        user_id,
        text: str,
    ) -> Plan:
        steps_text = _split_into_steps(text)
        results: list[PlanStep] = []
        for i, step_text in enumerate(steps_text, 1):
            result = self.engine.handle(
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                message=step_text,
            )
            step = PlanStep(
                index=i,
                text=step_text,
                intent=result.intent if result.handled else None,
                reply=result.reply if result.handled else "",
                tool_calls=result.tool_calls or [],
                ok=result.handled,
            )
            results.append(step)

        # Combined reply: Manus-like format — plan header, then each step's result.
        if len(results) == 1 and results[0].ok:
            combined = results[0].reply
        else:
            lang = _detect_lang(text)
            done = sum(1 for s in results if s.ok)
            total = len(results)
            if lang == "pt":
                header = f"📋 **Plano executado** — {done}/{total} passos concluídos"
            else:
                header = f"📋 **Plan executed** — {done}/{total} steps completed"
            lines = [header, ""]
            for step in results:
                mark = "✅" if step.ok else "⚠️"
                title_label = "Passo" if lang == "pt" else "Step"
                lines.append(f"{mark} **{title_label} {step.index}:** _{step.text}_")
                if step.reply:
                    for ln in step.reply.split("\n"):
                        if ln.strip():
                            lines.append(f"   {ln}")
                elif not step.ok:
                    fallback = ("(não entendi este passo — reformule)"
                                if lang == "pt" else "(couldn't parse this step — try rewording)")
                    lines.append(f"   {fallback}")
                lines.append("")
            combined = "\n".join(lines).rstrip()

        return Plan(original=text, steps=results, combined_reply=combined)


def is_multi_step(text: str) -> bool:
    return len(_split_into_steps(text)) > 1
