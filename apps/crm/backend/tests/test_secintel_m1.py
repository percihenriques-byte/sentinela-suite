"""Modulo Seguranca — M1: ativos + verificacao de posse.

Cobre ESPEC-SEGURANCA.md secao 2: cadastro de ativos com identificador nunca
em claro, verificacao de posse sem rede (so o e-mail de login e auto-verificado
em M1), dedupe idempotente, e as rotas exclusivas do responsavel.
"""
import uuid


def _mask(client):
    """auth_client ja registrou; devolve o e-mail do usuario logado."""
    # o e-mail esta no token; pegamos via /auth/me se existir, senao do banco
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import User

    with Session(engine) as s:
        return s.exec(select(User)).first().email


def test_crud_de_ativos(auth_client):
    # cria
    r = auth_client.post("/api/v1/seguranca/ativos", json={
        "tipo": "dominio", "identificador": "minhacasa.example.com",
    })
    assert r.status_code == 201, r.text
    asset = r.json()
    assert asset["identificador_mascarado"]  # nunca vazio
    assert asset["nivel_autorizacao"] == "declarado"  # dominio nao auto-verifica em M1
    aid = asset["id"]

    # lista
    r = auth_client.get("/api/v1/seguranca/ativos")
    assert r.status_code == 200
    assert any(a["id"] == aid for a in r.json())

    # edita titular
    r = auth_client.patch(f"/api/v1/seguranca/ativos/{aid}", json={"titular": "crianca"})
    assert r.status_code == 200 and r.json()["titular"] == "crianca"

    # arquiva -> some da lista padrao, aparece com incluir_arquivados
    assert auth_client.delete(f"/api/v1/seguranca/ativos/{aid}").status_code == 204
    assert all(a["id"] != aid for a in auth_client.get("/api/v1/seguranca/ativos").json())
    arq = auth_client.get("/api/v1/seguranca/ativos?incluir_arquivados=true").json()
    assert any(a["id"] == aid for a in arq)


def test_email_de_login_e_auto_verificado(auth_client):
    email = _mask(auth_client)
    r = auth_client.post("/api/v1/seguranca/ativos", json={
        "tipo": "email", "identificador": email,
    })
    assert r.status_code == 201, r.text
    assert r.json()["nivel_autorizacao"] == "verificado"
    assert r.json()["verificado_em"] is not None
    # dominio no e-mail preservado no mascarado; local mascarado
    assert "@" in r.json()["identificador_mascarado"]


def test_email_de_terceiro_fica_declarado(auth_client):
    r = auth_client.post("/api/v1/seguranca/ativos", json={
        "tipo": "email", "identificador": "outra.pessoa@example.com",
    })
    assert r.status_code == 201
    assert r.json()["nivel_autorizacao"] == "declarado"


def test_identificador_nunca_em_claro_na_api(auth_client):
    valor = "segredo.familia@example.com"
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "email", "identificador": valor})
    corpo = auth_client.get("/api/v1/seguranca/ativos").text
    # o valor completo do local-part nunca aparece; o dominio (publico) pode
    assert "segredo.familia" not in corpo


def test_dedupe_idempotente(auth_client):
    p = {"tipo": "username", "identificador": "joaozinho"}
    a1 = auth_client.post("/api/v1/seguranca/ativos", json=p).json()
    a2 = auth_client.post("/api/v1/seguranca/ativos", json=p).json()
    assert a1["id"] == a2["id"]
    ids = [a["id"] for a in auth_client.get("/api/v1/seguranca/ativos").json()]
    assert ids.count(a1["id"]) == 1


def test_verificar_posse_registra_ultima_verificacao(auth_client):
    aid = auth_client.post("/api/v1/seguranca/ativos", json={
        "tipo": "username", "identificador": "fulano",
    }).json()["id"]
    r = auth_client.post(f"/api/v1/seguranca/ativos/{aid}/verificar")
    assert r.status_code == 200
    assert r.json()["ultima_verificacao"] is not None
    assert "motivo" in r.json()  # a verificacao sempre explica o resultado


def test_ativos_exigem_responsavel(client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import User, Workspace, WorkspaceMember, WorkspaceRole

    def reg(nome):
        email = f"u-{uuid.uuid4().hex[:8]}@example.com"
        t = client.post("/api/v1/auth/register", json={
            "email": email, "password": "correcthorse-battery",
            "full_name": nome, "workspace_name": f"WS {nome}",
        }).json()["access_token"]
        return email, t

    _, owner = reg("Owner")
    r = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {owner}"})
    ws_id = (r.json() if isinstance(r.json(), list) else r.json()["items"])[0]["id"]

    email_m, membro = reg("Membro")
    with Session(engine) as s:
        m = s.exec(select(User).where(User.email == email_m)).one()
        s.add(WorkspaceMember(workspace_id=uuid.UUID(ws_id), user_id=m.id, role=WorkspaceRole.member))
        s.commit()

    h = {"Authorization": f"Bearer {membro}", "X-Workspace-Id": ws_id}
    assert client.get("/api/v1/seguranca/ativos", headers=h).status_code == 403
    assert client.post("/api/v1/seguranca/ativos", headers=h,
                       json={"tipo": "email", "identificador": "x@y.com"}).status_code == 403
