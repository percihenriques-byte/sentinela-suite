"""Email + message templates — ready-to-use with placeholders.

Purely local: no email is sent from here. Renders text and hands it back to
the UI, which can put it in a mailto: link or the clipboard. Placeholders
supported: {{first_name}}, {{last_name}}, {{company}}, {{email}}.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.models import Contact, Company


router = APIRouter(prefix="/email-templates", tags=["email-templates"])


TEMPLATES = {
    "cold_intro_pt": {
        "name": "Apresentação fria (PT)",
        "lang": "pt",
        "subject": "Oi {{first_name}}, uma ideia rápida para {{company}}",
        "body": """Oi {{first_name}},

Vi que {{company}} está crescendo forte e queria compartilhar uma ideia rápida que pode ajudar times como o seu a ganhar 20-30% de eficiência.

Faz sentido uma call de 15 min essa semana?

Abraços,""",
    },
    "cold_intro_en": {
        "name": "Cold intro (EN)",
        "lang": "en",
        "subject": "Hi {{first_name}} — a quick idea for {{company}}",
        "body": """Hi {{first_name}},

I noticed {{company}} is growing fast and wanted to share a quick idea that could help teams like yours gain 20-30% in efficiency.

Would a 15-min call this week make sense?

Best,""",
    },
    "follow_up_pt": {
        "name": "Follow-up (PT)",
        "lang": "pt",
        "subject": "Re: nossa conversa",
        "body": """Oi {{first_name}},

Passando para saber se você teve chance de olhar o material que enviei semana passada. Alguma dúvida?

Se preferir, podemos agendar 10 min pra alinhar rápido.

Abraço,""",
    },
    "follow_up_en": {
        "name": "Follow-up (EN)",
        "lang": "en",
        "subject": "Re: our chat",
        "body": """Hi {{first_name}},

Checking in to see if you had a chance to review the material I sent last week. Any questions?

Happy to hop on a quick 10-min call if that's easier.

Best,""",
    },
    "meeting_recap_pt": {
        "name": "Resumo de reunião (PT)",
        "lang": "pt",
        "subject": "Resumo — nossa reunião de hoje",
        "body": """Oi {{first_name}},

Obrigado pelo tempo hoje! Alinhamos:
• Ponto 1
• Ponto 2
• Próximo passo

Qualquer dúvida é só me chamar.

Abraço,""",
    },
    "proposal_sent_pt": {
        "name": "Proposta enviada (PT)",
        "lang": "pt",
        "subject": "Proposta — {{company}}",
        "body": """Oi {{first_name}},

Segue em anexo a proposta comercial que discutimos. Principais pontos:
• Escopo
• Investimento
• Prazo

Qualquer ajuste que precisar, me avise. Ficarei feliz em conversar.

Abraço,""",
    },
    "thank_you_pt": {
        "name": "Agradecimento pós-fechamento (PT)",
        "lang": "pt",
        "subject": "Obrigado, {{first_name}}!",
        "body": """{{first_name}},

Só quero deixar registrado o quanto estamos animados de trabalhar com você e a {{company}}. Vamos entregar tudo o que combinamos.

Já já falo com você.

Abraço,""",
    },
}


def _render(template: dict, ctx: dict) -> dict:
    def sub(text: str) -> str:
        for k, v in ctx.items():
            text = text.replace("{{" + k + "}}", v or "")
        return text
    return {
        "subject": sub(template["subject"]),
        "body": sub(template["body"]),
        "lang": template["lang"],
    }


@router.get("")
def list_templates() -> dict:
    return {"templates": [{"key": k, "name": v["name"], "lang": v["lang"]} for k, v in TEMPLATES.items()]}


@router.get("/{key}/render")
def render_template(
    key: str,
    session: SessionDep,
    _user: CurrentUser,
    ws: CurrentWorkspace,
    contact_id: Annotated[UUID | None, Query()] = None,
    first_name: Annotated[str | None, Query()] = None,
    company: Annotated[str | None, Query()] = None,
) -> dict:
    tpl = TEMPLATES.get(key)
    if not tpl:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template not found")
    ctx = {"first_name": "", "last_name": "", "company": company or "", "email": ""}
    if contact_id:
        c = session.exec(select(Contact).where(
            Contact.workspace_id == ws.id, Contact.id == contact_id, Contact.deleted_at.is_(None),
        )).first()
        if c:
            ctx["first_name"] = c.first_name or ""
            ctx["last_name"] = c.last_name or ""
            ctx["email"] = c.email or ""
            if c.company_id and not company:
                co = session.exec(select(Company).where(
                    Company.workspace_id == ws.id, Company.id == c.company_id,
                )).first()
                if co:
                    ctx["company"] = co.name
    if first_name:
        ctx["first_name"] = first_name
    return {"key": key, "rendered": _render(tpl, ctx), "context": ctx}
