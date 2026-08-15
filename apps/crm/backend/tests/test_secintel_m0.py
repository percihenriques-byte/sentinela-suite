"""Modulo Seguranca — M0: modelos, papel responsavel e auditoria base.

Cobre o alicerce do ESPEC-SEGURANCA.md: as rotas `/seguranca` existem e sao
EXCLUSIVAS do papel responsavel (owner/admin); as fontes nascem desligadas
(exceto a local) com descricao de egresso; a auditoria grava e lista; e o
seed de fontes e idempotente sem nunca sobrescrever consentimento.
"""
import uuid

import pytest


def _registrar(client, nome="Resp"):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "correcthorse-battery",
        "full_name": nome,
        "workspace_name": f"WS {nome}",
    })
    assert resp.status_code == 201, resp.text
    return email, resp.json()["access_token"]


def _headers(token, workspace_id=None):
    h = {"Authorization": f"Bearer {token}"}
    if workspace_id:
        h["X-Workspace-Id"] = str(workspace_id)
    return h


def _workspace_do_owner(client, token):
    r = client.get("/api/v1/workspaces", headers=_headers(token))
    assert r.status_code == 200, r.text
    corpo = r.json()
    itens = corpo if isinstance(corpo, list) else corpo.get("items", corpo.get("data", []))
    return itens[0]["id"]


def test_sem_login_nao_entra(client):
    assert client.get("/api/v1/seguranca/fontes").status_code == 401
    assert client.get("/api/v1/seguranca/auditoria").status_code == 401


def test_owner_e_responsavel_e_acessa(auth_client):
    r = auth_client.get("/api/v1/seguranca/fontes")
    assert r.status_code == 200, r.text
    r = auth_client.get("/api/v1/seguranca/auditoria")
    assert r.status_code == 200, r.text


def test_membro_comum_recebe_403(client):
    """Papel responsavel = owner/admin. Membro comum do CRM nao ve seguranca."""
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import User, WorkspaceMember, WorkspaceRole

    email_owner, token_owner = _registrar(client, "Owner")
    ws_id = _workspace_do_owner(client, token_owner)

    email_membro, token_membro = _registrar(client, "Membro")
    with Session(engine) as s:
        membro = s.exec(select(User).where(User.email == email_membro)).one()
        s.add(WorkspaceMember(
            workspace_id=uuid.UUID(ws_id), user_id=membro.id, role=WorkspaceRole.member,
        ))
        s.commit()

    for rota in ("/api/v1/seguranca/fontes", "/api/v1/seguranca/auditoria"):
        r = client.get(rota, headers=_headers(token_membro, ws_id))
        assert r.status_code == 403, f"{rota}: membro comum deveria receber 403, veio {r.status_code}"

    # o proprio owner segue entrando no mesmo workspace
    r = client.get("/api/v1/seguranca/fontes", headers=_headers(token_owner, ws_id))
    assert r.status_code == 200


def test_fontes_nascem_desligadas_exceto_local(auth_client):
    fontes = {f["nome"]: f for f in auth_client.get("/api/v1/seguranca/fontes").json()}
    assert set(fontes) == {"eventos_locais", "hibp", "github_secrets", "ct"}
    assert fontes["eventos_locais"]["habilitada"] is True
    for nome in ("hibp", "github_secrets", "ct"):
        assert fontes[nome]["habilitada"] is False, f"{nome} deveria nascer DESLIGADA"
    # contrato com o usuario: toda fonte explica o que sai da maquina
    for f in fontes.values():
        assert len(f["descricao_egresso"]) > 20


def test_seed_de_fontes_e_idempotente_e_preserva_consentimento(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import SecFonte
    from app.services import secintel_service as svc

    auth_client.get("/api/v1/seguranca/fontes")  # primeiro seed
    with Session(engine) as s:
        hibp = s.exec(select(SecFonte).where(SecFonte.nome == "hibp")).one()
        hibp.habilitada = True  # simula consentimento dado
        s.add(hibp)
        s.commit()
        svc.garantir_fontes(s)  # segundo seed nao pode desfazer nem duplicar
        linhas = list(s.exec(select(SecFonte).where(SecFonte.nome == "hibp")))
        assert len(linhas) == 1
        assert linhas[0].habilitada is True


def test_auditoria_grava_e_lista(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import User, Workspace
    from app.services import secintel_service as svc

    with Session(engine) as s:
        user = s.exec(select(User)).first()
        ws = s.exec(select(Workspace)).first()
        svc.registrar_auditoria(s, ws.id, user.id, "fonte_habilitada", {"fonte": "hibp"})

    r = auth_client.get("/api/v1/seguranca/auditoria")
    assert r.status_code == 200
    acoes = [linha["acao"] for linha in r.json()]
    assert "fonte_habilitada" in acoes


def test_modelos_roundtrip_sem_segredo_em_claro(client):
    """SecAsset guarda cifrado+hash+mascarado; o valor em claro nao aparece."""
    from sqlmodel import Session, select

    from app.core import crypto
    from app.db.session import engine
    from app.models import SecAsset, Workspace
    from app.models.secintel import SecAssetTipo

    import hashlib

    _registrar(client, "Dono")
    valor = "familia@example.com"
    with Session(engine) as s:
        ws = s.exec(select(Workspace)).first()
        s.add(SecAsset(
            workspace_id=ws.id,
            tipo=SecAssetTipo.email,
            identificador_enc=crypto.encrypt(valor),
            identificador_hash=hashlib.sha256(valor.encode()).hexdigest(),
            identificador_mascarado="fa••••@example.com",
        ))
        s.commit()
        linha = s.exec(select(SecAsset)).one()
        assert valor not in linha.identificador_enc
        assert valor not in linha.identificador_mascarado
        assert crypto.decrypt(linha.identificador_enc) == valor
