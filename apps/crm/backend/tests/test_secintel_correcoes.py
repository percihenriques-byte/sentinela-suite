"""Modulo Seguranca — correcoes da revisao pos-implementacao (caca aos bugs).

Cobre os 4 achados da revisao:
  1. reincidencia so com evento NOVO (sem inflacao pelo laco de 5 min);
  2. recencia real no score dos achados da visao geral;
  3. achado resolvido que reaparece REABRE (FP nao reabre);
  4. marcar recomendacao audita.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.db.session import engine
from app.models import SecAchado, SecEvento, SecIncidente, Workspace
from app.models.secintel import (
    SecAchadoStatus,
    SecClassificacao,
    SecEventoOrigem,
    SecSeveridade,
    SecTipoExposicao,
)


def _ws(auth_client):
    with Session(engine) as s:
        return s.exec(select(Workspace)).first().id


def _seq_takeover(ws_id, usuario, base=None):
    base = base or datetime.now(timezone.utc)
    with Session(engine) as s:
        for i in range(5):
            s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                            tipo="login_falha", ts=base + timedelta(seconds=i * 5),
                            ip="9.9.9.9", usuario=usuario))
        s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                        tipo="login_ok", ts=base + timedelta(minutes=1), ip="7.7.7.7", usuario=usuario))
        s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                        tipo="troca_senha", ts=base + timedelta(minutes=2), usuario=usuario))
        s.commit()
    return base


# ---- 1. reincidencia so com evento novo ----

def test_reincidencia_exige_evento_novo(auth_client):
    ws_id = _ws(auth_client)
    base = _seq_takeover(ws_id, "um@x.com")

    # 3 ciclos seguidos sobre os MESMOS eventos
    for _ in range(3):
        auth_client.post("/api/v1/seguranca/varreduras/correlacao")
    inc = [i for i in auth_client.get("/api/v1/seguranca/incidentes").json()
           if i["cenario"] == "account_takeover"][0]
    assert inc["ocorrencias"] == 1, "sem evento novo nao ha reincidencia"
    itens_antes = len(auth_client.get(f"/api/v1/seguranca/incidentes/{inc['id']}").json()["itens"])

    # agora chega uma SEGUNDA ONDA do ataque (rajada nova de outro IP + acesso
    # + troca) -> eventos novos de verdade, ai sim reincide
    _seq_takeover_2a_onda(ws_id, "um@x.com", base + timedelta(minutes=40))
    auth_client.post("/api/v1/seguranca/varreduras/correlacao")
    det = auth_client.get(f"/api/v1/seguranca/incidentes/{inc['id']}").json()
    assert det["ocorrencias"] == 2
    assert len(det["itens"]) > itens_antes  # eventos novos entraram na linha do tempo


def _seq_takeover_2a_onda(ws_id, usuario, base):
    with Session(engine) as s:
        for i in range(5):
            s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                            tipo="login_falha", ts=base + timedelta(seconds=i * 5),
                            ip="8.8.8.8", usuario=usuario))
        s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                        tipo="login_ok", ts=base + timedelta(minutes=1), ip="6.6.6.6", usuario=usuario))
        s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                        tipo="troca_senha", ts=base + timedelta(minutes=2), usuario=usuario))
        s.commit()


# ---- 2. recencia real na visao geral ----

def _inserir_achado(ws_id, dias_atras=0, fp=None):
    from app.services import secintel_mascara as mascara

    with Session(engine) as s:
        a = SecAchado(
            workspace_id=ws_id, fonte="github_secrets",
            tipo_exposicao=SecTipoExposicao.api_key,
            classificacao=SecClassificacao.confirmed, confianca=1.0,
            severidade=SecSeveridade.high, indicador_mascarado="AKIA••••1234",
            evidencia_resumo="repo x", fingerprint=fp or mascara.fingerprint(str(uuid.uuid4())),
            status=SecAchadoStatus.novo,
            descoberto_em=datetime.now(timezone.utc) - timedelta(days=dias_atras),
        )
        s.add(a)
        s.commit()
        s.refresh(a)
        return a.id


def test_score_da_visao_geral_decai_com_a_idade(auth_client):
    ws_id = _ws(auth_client)
    _inserir_achado(ws_id, dias_atras=120)
    score_velho = auth_client.get("/api/v1/seguranca/visao-geral").json()["score"]
    _inserir_achado(ws_id, dias_atras=0)
    score_novo = auth_client.get("/api/v1/seguranca/visao-geral").json()["score"]
    assert score_novo > score_velho, "achado fresco deve pesar mais que o antigo"


# ---- 3. resolvido reaparece -> reabre; FP nao reabre ----

def _reencontrar(ws_id, fingerprint):
    from app.services.secintel_fontes import AchadoBruto, _upsert_achado

    with Session(engine) as s:
        return _upsert_achado(s, ws_id, "github_secrets", AchadoBruto(
            asset_id=None, tipo_exposicao=SecTipoExposicao.api_key,
            classificacao=SecClassificacao.confirmed, confianca=1.0,
            indicador_mascarado="AKIA••••1234", evidencia_resumo="repo x, de novo",
            fingerprint=fingerprint,
        )).status


def test_resolvido_que_reaparece_reabre(auth_client):
    from app.services import secintel_mascara as mascara

    ws_id = _ws(auth_client)
    fp = mascara.fingerprint("reaparece")
    aid = _inserir_achado(ws_id, fp=fp)
    auth_client.patch(f"/api/v1/seguranca/achados/{aid}/resolver")

    status = _reencontrar(ws_id, fp)
    assert status == SecAchadoStatus.novo, "exposicao que reaparece nao esta resolvida"
    corpo = auth_client.get("/api/v1/seguranca/achados").json()
    o = [a for a in corpo if a["id"] == str(aid)][0]
    assert "REAPARECEU" in o["evidencia_resumo"]


def test_falso_positivo_nao_reabre(auth_client):
    from app.services import secintel_mascara as mascara

    ws_id = _ws(auth_client)
    fp = mascara.fingerprint("fp-fica")
    aid = _inserir_achado(ws_id, fp=fp)
    auth_client.patch(f"/api/v1/seguranca/achados/{aid}/falso-positivo",
                      json={"motivo": "exemplo em doc"})
    status = _reencontrar(ws_id, fp)
    assert status == SecAchadoStatus.falso_positivo, "decisao humana de FP prevalece"


# ---- 4. marcar recomendacao audita ----

def test_marcar_recomendacao_audita(auth_client):
    ws_id = _ws(auth_client)
    _seq_takeover(ws_id, "aud@x.com")
    inc = auth_client.post("/api/v1/seguranca/varreduras/correlacao").json()[0]
    auth_client.patch(f"/api/v1/seguranca/incidentes/{inc['id']}/recomendacoes/0",
                      json={"feito": True})
    acoes = [l["acao"] for l in auth_client.get("/api/v1/seguranca/auditoria").json()]
    assert "recomendacao_marcada" in acoes
