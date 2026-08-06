"""Regras de negocio do modulo Sentinela (controle parental).

Responsabilidades:
  - manter a configuracao singleton (token de ingestao, sensibilidade, PIN);
  - registrar eventos vindos da extensao / do app PowerShell;
  - aplicar retencao (o equivalente ao teto de 2000 linhas do .jsonl);
  - resumir para o painel do responsavel.

Nao classifica conteudo: o veredito vem de quem observou (extensao ou app), que
usa o classificador unico do Sentinela.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlmodel import Session, col, delete, func, select

from app.core.crypto import decrypt, encrypt
from app.models import SentinelaConfig, SentinelaEvent

SENSIBILIDADES = ("baixa", "media", "alta")
MAX_BUSCA = 500
MAX_LOTE = 200


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """SQLite devolve datetime naive; normaliza para UTC para poder comparar."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- config


def get_config(session: Session) -> SentinelaConfig:
    """Configuracao singleton, criada na primeira leitura (idempotente)."""
    cfg = session.exec(select(SentinelaConfig).limit(1)).first()
    if cfg is None:
        cfg = SentinelaConfig(token_ingestao=novo_token())
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    elif not cfg.token_ingestao:
        cfg.token_ingestao = novo_token()
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    return cfg


def novo_token() -> str:
    return secrets.token_urlsafe(32)


def rotacionar_token(session: Session) -> SentinelaConfig:
    cfg = get_config(session)
    cfg.token_ingestao = novo_token()
    cfg.updated_at = _now()
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


def token_confere(session: Session, token: Optional[str]) -> bool:
    """Comparacao em tempo constante — token de ingestao e credencial."""
    if not token:
        return False
    cfg = get_config(session)
    return secrets.compare_digest(token, cfg.token_ingestao)


# --------------------------------------------------------------------------- eventos


def registrar_evento(
    session: Session,
    *,
    busca: str,
    origem: str = "desconhecida",
    dispositivo: str = "este-pc",
    tema: Optional[str] = None,
    confianca: float = 0.0,
    bloqueado: bool = False,
    sinais: Optional[Iterable[str]] = None,
    ocorrido_em: Optional[datetime] = None,
    commit: bool = True,
) -> SentinelaEvent:
    ev = SentinelaEvent(
        ocorrido_em=ocorrido_em or _now(),
        busca_enc=encrypt((busca or "")[:MAX_BUSCA]),
        origem=(origem or "desconhecida")[:60],
        dispositivo=(dispositivo or "este-pc")[:80],
        tema=(tema or None) if tema is None else tema[:80],
        confianca=max(0.0, min(1.0, float(confianca or 0.0))),
        bloqueado=bool(bloqueado),
        sinais=", ".join(sinais)[:300] if sinais else None,
    )
    session.add(ev)
    if commit:
        session.commit()
        session.refresh(ev)
    return ev


def aplicar_retencao(session: Session, retencao_dias: Optional[int] = None) -> int:
    """Apaga eventos mais velhos que a janela de retencao. Devolve quantos sairam."""
    if retencao_dias is None:
        retencao_dias = get_config(session).retencao_dias
    if retencao_dias <= 0:  # 0 = guardar para sempre
        return 0
    corte = _now() - timedelta(days=retencao_dias)
    alvo = session.exec(
        select(func.count()).select_from(SentinelaEvent).where(col(SentinelaEvent.ocorrido_em) < corte)
    ).one()
    if alvo:
        session.exec(delete(SentinelaEvent).where(col(SentinelaEvent.ocorrido_em) < corte))
        session.commit()
    return int(alvo)


def listar_eventos(
    session: Session,
    *,
    limite: int = 100,
    offset: int = 0,
    somente_bloqueados: bool = False,
    dispositivo: Optional[str] = None,
    desde: Optional[datetime] = None,
) -> tuple[list[SentinelaEvent], int]:
    stmt = select(SentinelaEvent)
    cont = select(func.count()).select_from(SentinelaEvent)
    if somente_bloqueados:
        stmt = stmt.where(col(SentinelaEvent.bloqueado).is_(True))
        cont = cont.where(col(SentinelaEvent.bloqueado).is_(True))
    if dispositivo:
        stmt = stmt.where(SentinelaEvent.dispositivo == dispositivo)
        cont = cont.where(SentinelaEvent.dispositivo == dispositivo)
    if desde:
        stmt = stmt.where(col(SentinelaEvent.ocorrido_em) >= desde)
        cont = cont.where(col(SentinelaEvent.ocorrido_em) >= desde)
    total = int(session.exec(cont).one())
    itens = session.exec(
        stmt.order_by(col(SentinelaEvent.ocorrido_em).desc()).offset(offset).limit(limite)
    ).all()
    return list(itens), total


def texto_do_evento(ev: SentinelaEvent) -> str:
    """Decifra a busca. Chave trocada => decrypt devolve "" (ja logado la)."""
    return decrypt(ev.busca_enc) or ""


def resumo(session: Session, dias: int = 7) -> dict:
    """Numeros do painel: totais, temas mais barrados e serie diaria."""
    desde = _now() - timedelta(days=dias)
    total = int(session.exec(select(func.count()).select_from(SentinelaEvent)).one())
    bloqueados = int(
        session.exec(
            select(func.count()).select_from(SentinelaEvent).where(col(SentinelaEvent.bloqueado).is_(True))
        ).one()
    )
    temas_raw = session.exec(
        select(SentinelaEvent.tema, func.count())
        .where(col(SentinelaEvent.bloqueado).is_(True), col(SentinelaEvent.tema).is_not(None))
        .group_by(SentinelaEvent.tema)
    ).all()
    temas = sorted(
        ({"tema": t, "vezes": int(n)} for t, n in temas_raw),
        key=lambda x: x["vezes"],
        reverse=True,
    )

    # Serie diaria montada em Python: o formato de data do SQLite nao e o mesmo
    # de outros bancos, e a janela e pequena (7-30 dias).
    recentes, _ = listar_eventos(session, limite=5000, desde=desde)
    por_dia: dict[str, dict[str, int]] = {}
    for i in range(dias - 1, -1, -1):
        chave = (_now() - timedelta(days=i)).date().isoformat()
        por_dia[chave] = {"total": 0, "bloqueados": 0}
    for ev in recentes:
        chave = _aware(ev.ocorrido_em).date().isoformat()
        alvo = por_dia.get(chave)
        if alvo is None:
            continue
        alvo["total"] += 1
        if ev.bloqueado:
            alvo["bloqueados"] += 1

    ultimo = session.exec(
        select(SentinelaEvent).order_by(col(SentinelaEvent.ocorrido_em).desc()).limit(1)
    ).first()
    # select() de uma coluna so devolve escalares (nao tuplas) via session.exec.
    dispositivos = (
        [d for d in session.exec(select(SentinelaEvent.dispositivo).distinct()).all() if d]
        if total
        else []
    )

    return {
        "total": total,
        "bloqueados": bloqueados,
        "liberados": total - bloqueados,
        "temas": temas,
        "por_dia": [{"dia": k, **v} for k, v in por_dia.items()],
        "dispositivos": sorted(dispositivos),
        "ultimo_evento": _aware(ultimo.ocorrido_em) if ultimo else None,
        "dias": dias,
    }
