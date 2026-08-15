"""Modulo Seguranca — M3: scoring, visao geral, achados e loop de FP.

Cobre ESPEC secao 9 (bandas, trava anti-alarmismo, decaimento, teto de
correlacao) e a Fase 8 (falso-positivo exige motivo, e auditado, nao vira
incidente).
"""
import uuid

from app.models.secintel import SecClassificacao, SecSeveridade
from app.services import secintel_score as sc


# ---- scoring puro ----

def test_bandas():
    assert sc.banda(0) == SecSeveridade.info
    assert sc.banda(9) == SecSeveridade.info
    assert sc.banda(10) == SecSeveridade.low
    assert sc.banda(30) == SecSeveridade.medium
    assert sc.banda(55) == SecSeveridade.high
    assert sc.banda(80) == SecSeveridade.critical


def test_critical_exige_confirmado_e_confianca_alta():
    # base alta o suficiente para CRITICAL, mas nao confirmado -> rebaixa a HIGH
    score, sev = sc.calcular(p=0.9, impacto=1.0, confianca=1.0, idade_dias=0, confirmado=False)
    assert score >= 80 and sev == SecSeveridade.high
    # confirmado + confianca alta -> CRITICAL liberado
    score2, sev2 = sc.calcular(p=0.9, impacto=1.0, confianca=1.0, idade_dias=0, confirmado=True)
    assert score2 >= 80 and sev2 == SecSeveridade.critical
    # confirmado mas confianca baixa nao chega a 80 mesmo
    score3, sev3 = sc.calcular(p=0.9, impacto=1.0, confianca=0.7, idade_dias=0, confirmado=True)
    assert sev3 != SecSeveridade.critical


def test_decaimento_por_recencia():
    novo, _ = sc.calcular(p=0.9, impacto=1.0, confianca=1.0, idade_dias=0, confirmado=True)
    velho, _ = sc.calcular(p=0.9, impacto=1.0, confianca=1.0, idade_dias=90, confirmado=True)
    assert velho < novo
    assert sc.recencia(1000) == 0.25  # piso


def test_teto_de_correlacao():
    sem, _ = sc.calcular(p=0.5, impacto=0.7, confianca=0.7, idade_dias=0, chaves_extra=0)
    com, _ = sc.calcular(p=0.5, impacto=0.7, confianca=0.7, idade_dias=0, chaves_extra=10)
    # bonus limitado a +30
    assert 0 < (com - sem) <= 30


# ---- visao geral + achados via API ----

def _ws(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import Workspace

    with Session(engine) as s:
        return s.exec(select(Workspace)).first().id


def _inserir_achado(engine, ws_id, **kw):
    from sqlmodel import Session

    from app.models import SecAchado
    from app.models.secintel import (
        SecAchadoStatus,
        SecSeveridade,
        SecTipoExposicao,
    )
    from app.services import secintel_mascara as mascara

    defaults = dict(
        workspace_id=ws_id, fonte="github_secrets",
        tipo_exposicao=SecTipoExposicao.api_key,
        classificacao=SecClassificacao.confirmed, confianca=1.0,
        severidade=SecSeveridade.high, indicador_mascarado="sk_live_••••1234",
        evidencia_resumo="repo x, commit y", fingerprint=mascara.fingerprint(str(uuid.uuid4())),
        status=SecAchadoStatus.novo,
    )
    defaults.update(kw)
    with Session(engine) as s:
        a = SecAchado(**defaults)
        s.add(a)
        s.commit()
        s.refresh(a)
        return a.id


def test_visao_geral_agrega(auth_client):
    from app.db.session import engine

    ws_id = _ws(auth_client)
    _inserir_achado(engine, ws_id)
    vg = auth_client.get("/api/v1/seguranca/visao-geral").json()
    assert vg["achados_ativos"] == 1
    assert vg["score"] > 0
    assert "eventos_locais" in vg["fontes_ligadas"]
    assert "hibp" in vg["fontes_desligadas"]


def test_falso_positivo_exige_motivo_e_e_auditado(auth_client):
    from app.db.session import engine

    ws_id = _ws(auth_client)
    aid = _inserir_achado(engine, ws_id)

    # sem motivo -> 422
    r = auth_client.patch(f"/api/v1/seguranca/achados/{aid}/falso-positivo", json={"motivo": ""})
    assert r.status_code == 422

    # com motivo -> vira FP, confianca zerada
    r = auth_client.patch(f"/api/v1/seguranca/achados/{aid}/falso-positivo",
                          json={"motivo": "chave de exemplo em doc"})
    assert r.status_code == 200
    assert r.json()["status"] == "falso_positivo"
    assert r.json()["confianca"] == 0.0

    # auditado
    acoes = [l["acao"] for l in auth_client.get("/api/v1/seguranca/auditoria").json()]
    assert "achado_falso_positivo" in acoes

    # FP some da visao geral (nao conta como ativo)
    assert auth_client.get("/api/v1/seguranca/visao-geral").json()["achados_ativos"] == 0


def test_incidente_local_nunca_e_critical(auth_client):
    """Trava por construcao: correlacao local (sem achado CONFIRMED) para em HIGH."""
    from datetime import datetime, timedelta, timezone

    from sqlmodel import Session

    from app.db.session import engine
    from app.models import SecEvento
    from app.models.secintel import SecEventoOrigem

    ws_id = _ws(auth_client)
    base = datetime.now(timezone.utc)
    with Session(engine) as s:
        for i in range(5):
            s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                            tipo="login_falha", ts=base + timedelta(seconds=i * 5),
                            ip="9.9.9.9", usuario="alvo@x.com"))
        s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                        tipo="login_ok", ts=base + timedelta(minutes=1), ip="7.7.7.7", usuario="alvo@x.com"))
        s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                        tipo="troca_senha", ts=base + timedelta(minutes=2), usuario="alvo@x.com"))
        s.commit()
    incs = auth_client.post("/api/v1/seguranca/varreduras/correlacao").json()
    assert incs and all(i["severidade"] != "CRITICAL" for i in incs)
