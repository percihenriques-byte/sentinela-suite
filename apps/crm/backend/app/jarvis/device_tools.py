"""Local-only device tools for Jarvis.

**No external HTTP requests.** Everything reads/writes the local filesystem
in the user's work directory. If the user wants calendar/contacts/etc., they
export from their existing app as .ics/.csv/.vcf and drop the file in
~/Documents/VisiQuost.

Removed (2026-07-12) per user rule "não pode usar APIs":
- search_web (DuckDuckGo scrape)
- browse_url (arbitrary URL fetch)
- Google Calendar API paths in read_calendar / create_calendar_event
- LinkedIn UGC API in post_social
- OAuth flows

Kept:
- Local .ics calendar reading
- Local file scanning + read
- CSV/vCard contact import
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.jarvis.tools import ToolContext


# ---------------- Work directory ----------------

def _get_work_dir() -> Path | None:
    """Return the working directory. Auto-creates ~/Documents/VisiQuost by default.

    Never allow arbitrary filesystem access — always resolve inside this dir.
    """
    envv = os.environ.get("VISIQUOST_WORK_DIR") or os.environ.get("JARVIS_WORK_DIR")
    if envv:
        p = Path(envv).expanduser()
        return p if p.is_dir() else None
    docs = Path.home() / "Documents"
    if not docs.is_dir():
        docs = Path.home()
    default = docs / "VisiQuost"
    try:
        default.mkdir(parents=True, exist_ok=True)
        return default
    except Exception:
        return None


# ---------------- Local calendar (.ics) ----------------

def _parse_ics_local(days: int, max_results: int) -> dict[str, Any] | None:
    workdir = _get_work_dir()
    if not workdir:
        return None
    ics_files = list(workdir.glob("*.ics"))
    if not ics_files:
        return None
    from datetime import datetime, timezone, timedelta
    import re as _re
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    events = []
    for f in ics_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for block in _re.split(r"BEGIN:VEVENT", text)[1:]:
            block = block.split("END:VEVENT", 1)[0]
            def _get(field):
                m = _re.search(rf"^{field}[^:]*:(.+)$", block, _re.MULTILINE)
                return m.group(1).strip() if m else None
            start_raw = _get("DTSTART") or ""
            end_raw = _get("DTEND") or ""
            summary = _get("SUMMARY") or "(sem título)"
            location = _get("LOCATION")
            try:
                if "T" in start_raw:
                    dt = datetime.strptime(start_raw.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
                    dt = dt.replace(tzinfo=timezone.utc)
                elif len(start_raw) >= 8:
                    dt = datetime.strptime(start_raw[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
                else:
                    continue
                if now <= dt <= end:
                    events.append({
                        "summary": summary,
                        "start": dt.isoformat(),
                        "end": end_raw,
                        "location": location,
                        "source": f.name,
                    })
            except Exception:
                continue
    events.sort(key=lambda e: e["start"])
    return {
        "status": "ok",
        "provider": "local_ics",
        "source": "local_ics",
        "range_days": days,
        "count": len(events),
        "events": events[:max_results],
        "files_scanned": [f.name for f in ics_files],
    }


def _read_calendar(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read events strictly from local .ics files in the work dir."""
    days = int(args.get("days") or 7)
    days = max(1, min(days, 90))
    max_results = int(args.get("max_results") or 10)
    max_results = max(1, min(max_results, 50))
    local = _parse_ics_local(days, max_results)
    if local is not None and local.get("count", 0) > 0:
        return local
    workdir = _get_work_dir()
    workdir_str = str(workdir) if workdir else "~/Documents/VisiQuost"
    return {
        "status": "no_events",
        "message": (
            f"Nenhum evento local encontrado. Exporte sua agenda como .ics "
            f"e salve em {workdir_str} — o VisiQuost lê automaticamente."
        ),
        "hint": {"kind": "drop_ics_file", "workdir": workdir_str},
    }


# ---------------- Local files ----------------

def _read_local_file(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read a file from the work dir and return cleaned text.

    Supported natively: .txt .md .csv .ics .vcf .html .json .log
    PDF via pypdf if installed.
    """
    root = _get_work_dir()
    if root is None:
        return {"error": "no_workdir"}
    name = (args.get("filename") or args.get("name") or "").strip()
    if not name:
        return {"error": "missing_filename"}
    target = (root / name).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return {"error": "path_escape"}
    if not target.is_file():
        matches = [p for p in root.rglob("*") if p.is_file() and p.name.lower() == name.lower()]
        if matches:
            target = matches[0]
        else:
            return {"error": "not_found", "name": name}
    ext = target.suffix.lower()
    NATIVE = {".txt", ".md", ".csv", ".ics", ".vcf", ".html", ".htm", ".json", ".log"}
    if ext in NATIVE:
        try:
            text = target.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return {"error": "read_failed", "message": str(e)}
        if ext in {".html", ".htm"}:
            import re as _re
            text = _re.sub(r"<[^>]+>", " ", text)
            text = _re.sub(r"\s+", " ", text).strip()
        return {
            "status": "ok", "name": target.name, "path": str(target.relative_to(root)),
            "text": text[:5000], "truncated": len(text) > 5000, "size": target.stat().st_size,
            "ext": ext,
        }
    if ext == ".pdf":
        try:
            import pypdf
        except Exception:
            return {"error": "pdf_needs_dep", "message": "PDF reading needs `pip install pypdf`."}
        try:
            reader = pypdf.PdfReader(str(target))
            pages = [p.extract_text() or "" for p in reader.pages[:20]]
            text = "\n".join(pages)
            return {
                "status": "ok", "name": target.name, "text": text[:5000],
                "truncated": len(text) > 5000, "size": target.stat().st_size,
                "ext": ext, "pages_read": min(20, len(reader.pages)),
            }
        except Exception as e:
            return {"error": "pdf_read_failed", "message": str(e)}
    return {"error": "unsupported_ext", "ext": ext}


# ---------------- vCard + CSV auto-import ----------------

def _parse_vcf(text: str) -> list[dict[str, Any]]:
    import re as _re
    contacts = []
    for block in _re.split(r"BEGIN:VCARD", text, flags=_re.IGNORECASE)[1:]:
        block = block.split("END:VCARD", 1)[0]
        c = {}
        m = _re.search(r"^FN[^:]*:(.+)$", block, _re.MULTILINE)
        if m:
            full = m.group(1).strip()
            parts = full.split(" ", 1)
            c["first_name"] = parts[0]
            c["last_name"] = parts[1] if len(parts) > 1 else ""
        else:
            m2 = _re.search(r"^N[^:]*:([^\n]+)$", block, _re.MULTILINE)
            if m2:
                p = m2.group(1).split(";")
                if len(p) >= 2:
                    c["first_name"] = (p[1] or "").strip() or (p[0] or "").strip()
                    c["last_name"] = (p[0] or "").strip() if len(p) > 1 else ""
        m = _re.search(r"^EMAIL[^:]*:(.+)$", block, _re.MULTILINE | _re.IGNORECASE)
        if m: c["email"] = m.group(1).strip()
        m = _re.search(r"^TEL[^:]*:(.+)$", block, _re.MULTILINE | _re.IGNORECASE)
        if m: c["phone"] = m.group(1).strip()
        m = _re.search(r"^TITLE[^:]*:(.+)$", block, _re.MULTILINE | _re.IGNORECASE)
        if m: c["job_title"] = m.group(1).strip()
        m = _re.search(r"^ORG[^:]*:(.+)$", block, _re.MULTILINE | _re.IGNORECASE)
        if m: c["department"] = m.group(1).strip().split(";")[0]
        if c.get("first_name"):
            contacts.append(c)
    return contacts


def _auto_import_contacts(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    root = _get_work_dir()
    if root is None:
        return {"status": "no_workdir"}
    confirm = bool(args.get("confirm", False))
    limit = int(args.get("limit") or 200)

    all_new: list[dict[str, Any]] = []
    sources = []
    for f in root.glob("*.vcf"):
        try:
            parsed = _parse_vcf(f.read_text(encoding="utf-8", errors="ignore"))
            for c in parsed:
                c["_source"] = f.name
            all_new.extend(parsed)
            sources.append({"file": f.name, "count": len(parsed), "type": "vcf"})
        except Exception:
            continue
    for f in root.glob("*.csv"):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").lstrip("﻿")
            lines = text.split("\n")
            if len(lines) < 2:
                continue
            header = [h.strip().lower().replace(" ", "_") for h in lines[0].split(",")]
            alias = {
                "given_name": "first_name", "first": "first_name",
                "family_name": "last_name", "last": "last_name", "surname": "last_name",
                "name": "first_name",
                "e-mail": "email", "e_mail_address": "email", "email_address": "email",
                "phone_number": "phone", "mobile": "phone",
                "organization_name": "department", "company": "department",
                "job": "job_title", "position": "job_title",
            }
            cols = [alias.get(h, h) for h in header]
            count = 0
            for line in lines[1:]:
                if not line.strip():
                    continue
                vals = [v.strip().strip('"') for v in line.split(",")]
                if not any(vals):
                    continue
                c = {}
                for i, col in enumerate(cols):
                    if i < len(vals) and vals[i] and col in {"first_name", "last_name", "email", "phone", "job_title", "department"}:
                        c[col] = vals[i]
                if not c.get("first_name") and "name" in header:
                    idx = header.index("name")
                    if idx < len(vals) and vals[idx]:
                        parts = vals[idx].split(" ", 1)
                        c["first_name"] = parts[0]
                        c["last_name"] = parts[1] if len(parts) > 1 else ""
                if c.get("first_name"):
                    c["_source"] = f.name
                    all_new.append(c)
                    count += 1
            sources.append({"file": f.name, "count": count, "type": "csv"})
        except Exception:
            continue

    from sqlmodel import select
    from app.models import Contact
    existing_emails = {c.email.lower() for c in ctx.session.exec(
        select(Contact).where(Contact.workspace_id == ctx.workspace_id, Contact.deleted_at.is_(None), Contact.email.is_not(None))
    ).all() if c.email}
    unique = []
    seen = set()
    for c in all_new:
        e = (c.get("email") or "").lower()
        key = e or f"{c.get('first_name', '').lower()}|{c.get('last_name', '').lower()}"
        if key in seen or (e and e in existing_emails):
            continue
        seen.add(key)
        unique.append(c)
    to_import = unique[:limit]

    if not confirm:
        return {
            "status": "preview",
            "sources": sources,
            "would_import": len(to_import),
            "skipped_dupes": len(all_new) - len(to_import),
            "sample": [{k: v for k, v in c.items() if k != "_source"} for c in to_import[:5]],
        }

    created = 0
    for c in to_import:
        obj = Contact(
            workspace_id=ctx.workspace_id,
            owner_user_id=ctx.user_id,
            first_name=c.get("first_name") or "?",
            last_name=c.get("last_name") or None,
            email=c.get("email") or None,
            phone=c.get("phone") or None,
            job_title=c.get("job_title") or None,
            department=c.get("department") or None,
        )
        ctx.session.add(obj)
        created += 1
    if created:
        ctx.session.commit()
    return {"status": "ok", "created": created, "sources": sources}


def _scan_work_dir(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    root = _get_work_dir()
    if root is None:
        return {"status": "not_configured", "message": "Diretório de trabalho não disponível."}
    categories = {
        "calendars": [".ics"],
        "contacts": [".csv", ".vcf"],
        "docs": [".pdf", ".docx", ".doc", ".txt", ".md"],
        "spreadsheets": [".xlsx", ".xls"],
        "images": [".png", ".jpg", ".jpeg", ".gif"],
    }
    found: dict[str, list[dict[str, Any]]] = {k: [] for k in categories}
    other = []
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue
        try:
            size = entry.stat().st_size
        except Exception:
            size = 0
        ext = entry.suffix.lower()
        item = {"name": entry.name, "path": str(entry.relative_to(root)), "size": size}
        placed = False
        for cat, exts in categories.items():
            if ext in exts:
                found[cat].append(item)
                placed = True
                break
        if not placed:
            other.append(item)
    return {
        "status": "ok", "root": str(root),
        "counts": {k: len(v) for k, v in found.items()},
        "categories": found,
        "other": other[:20],
    }


def _list_files(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    root = _get_work_dir()
    if root is None:
        return {"status": "not_configured", "message": "Diretório de trabalho não configurado."}
    sub = (args.get("subdir") or "").strip().lstrip("/\\")
    target = (root / sub).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        return {"error": "path_escape"}
    if not target.is_dir():
        return {"error": "not_a_directory", "path": str(target)}
    items = []
    for entry in sorted(target.iterdir()):
        items.append({
            "name": entry.name,
            "is_dir": entry.is_dir(),
            "size": entry.stat().st_size if entry.is_file() else None,
        })
    return {"root": str(root), "path": str(target), "items": items[:100]}


def _generate_marketing_copy(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Template-based copy generator. Zero API, purely local strings."""
    import random
    topic = (args.get("topic") or args.get("about") or "").strip()
    platform = (args.get("platform") or "linkedin").lower()
    lang = (args.get("lang") or "pt").lower()
    if not topic:
        return {"error": "missing_topic"}
    templates = {
        ("pt", "linkedin"): [
            "🚀 {topic} — o próximo passo para times que querem escalar sem perder o toque humano.\n\nPor que agora? Porque velocidade sem propósito é ruído.\n\nO que você acha? 👇\n\n#growth #vendas #{tag}",
            "Uma verdade sobre {topic} que ninguém fala:\n\nA maioria trata como projeto. Poucos tratam como cultura.\n\nA diferença está no resultado depois de 6 meses.\n\n#leadership #vendas #{tag}",
            "3 lições que aprendi trabalhando com {topic}:\n\n1️⃣ Comece pequeno, meça tudo\n2️⃣ Ouça o cliente antes do dashboard\n3️⃣ Consistência bate genialidade\n\nO que você adicionaria? 💡\n\n#{tag} #estrategia",
        ],
        ("en", "linkedin"): [
            "🚀 {topic} — the next step for teams that want to scale without losing the human touch.\n\nThoughts? 👇\n\n#growth #sales #{tag}",
            "One truth about {topic} nobody talks about:\n\nMost treat it as a project. Few treat it as a culture.\n\n#leadership #sales #{tag}",
            "3 lessons I learned with {topic}:\n1️⃣ Start small\n2️⃣ Listen to customers\n3️⃣ Consistency wins\n\n#{tag}",
        ],
        ("pt", "twitter"): [
            "{topic} não é sobre a ferramenta.\nÉ sobre a decisão de mudar como você trabalha. ⚡",
            "Menos reunião, mais {topic}. 🧵",
        ],
        ("en", "twitter"): [
            "{topic} isn't about the tool.\nIt's about changing how you work. ⚡",
            "Less meetings, more {topic}. 🧵",
        ],
    }
    key = (lang if lang in ("pt", "en") else "pt", platform if platform in ("linkedin", "twitter") else "linkedin")
    picks = templates.get(key, templates[("pt", "linkedin")])
    tag = topic.split()[0].strip("#").lower().replace(",", "")
    body = random.Random(hash((topic, platform))).choice(picks).format(topic=topic, tag=tag)
    return {
        "status": "ok",
        "platform": platform, "lang": lang, "topic": topic,
        "content": body,
        "char_count": len(body),
    }


def _enrich_company(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Removed: this used to scrape company websites via HTTP. Now returns a
    'not supported' hint so any UI that still calls it degrades gracefully."""
    return {
        "status": "disabled",
        "message": "Enriquecimento web foi desabilitado (regra: sem APIs externas). Edite os dados da empresa manualmente.",
    }


# ---------------- Registration ----------------

DEVICE_TOOLS = [
    ("read_calendar", _read_calendar, "Ler eventos de arquivos .ics locais na pasta de trabalho."),
    ("read_local_file", _read_local_file, "Ler o conteúdo de um arquivo no diretório de trabalho."),
    ("auto_import_contacts", _auto_import_contacts, "Detectar CSVs/vCards na pasta e importar contatos (preview antes)."),
    ("scan_work_dir", _scan_work_dir, "Categorizar arquivos no diretório de trabalho."),
    ("list_files", _list_files, "Listar arquivos no diretório de trabalho."),
    ("generate_marketing_copy", _generate_marketing_copy, "Gerar copy de marketing por template (offline)."),
    ("enrich_company", _enrich_company, "[Desabilitado] Antes fazia scrape, agora só retorna aviso."),
]


def register_device_tools(registry) -> None:
    from app.jarvis.tools import ToolSpec
    for name, handler, desc in DEVICE_TOOLS:
        registry.register(ToolSpec(
            name=name,
            description=desc,
            input_schema={"type": "object", "properties": {}, "additionalProperties": True},
            handler=handler,
        ))
