"""Modulo Seguranca — posse por rede (auditoria 7a rodada, F2/F3).

F2: github e ct exigem `verificado`; sem verificacao por rede, nenhum repo/
dominio era elegivel e as fontes varriam nada em silencio. Agora a posse e
comprovada por rede, SEMPRE dentro do consentimento (fonte desligada nunca
dispara rede), e o runner avisa "ativos aguardando posse" em vez do silencio.

F3: o gate de habilitacao (422 sem credencial) e reforcado por teste explicito.
"""
import uuid

from sqlmodel import Session, select

from app.db.session import engine
from app.models import SecAsset, SecFonte, Workspace
from app.models.secintel import SecNivelAutorizacao


def _ws(auth_client):
    with Session(engine) as s:
        return s.exec(select(Workspace)).first().id


def _dar_chave(auth_client, nome, chave="tok"):
    assert auth_client.put(f"/api/v1/seguranca/fontes/{nome}/credencial",
                           json={"credencial": chave}).status_code == 200


# ---- F2: posse de repo por token do GitHub ----

def test_repo_declarado_por_padrao(auth_client):
    r = auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "repo", "identificador": "org/r"})
    assert r.json()["nivel_autorizacao"] == "declarado"


def test_verificar_repo_sem_fonte_ligada_nao_toca_rede(auth_client):
    """Fonte github desligada: verificar posse NAO pode chamar rede."""
    aid = auth_client.post("/api/v1/seguranca/ativos",
                           json={"tipo": "repo", "identificador": "org/r"}).json()["id"]

    def bomba(*a, **k):
        raise AssertionError("rede chamada com a fonte desligada!")

    from app.services import secintel_service as svc
    ws_id = _ws(auth_client)
    with Session(engine) as s:
        from app.models import User
        user = s.exec(select(User)).first()
        asset, motivo = svc.verificar_posse(s, ws_id, user, uuid.UUID(aid),
                                            verificadores={"repo": bomba, "dominio": bomba})
        nivel = asset.nivel_autorizacao
    assert nivel == SecNivelAutorizacao.declarado
    assert "ligue a fonte" in motivo


def test_verificar_repo_com_token_dono_vira_verificado(auth_client):
    from app.services import secintel_service as svc

    ws_id = _ws(auth_client)
    aid = auth_client.post("/api/v1/seguranca/ativos",
                           json={"tipo": "repo", "identificador": "org/meu"}).json()["id"]
    _dar_chave(auth_client, "github_secrets", "tok-dono")
    auth_client.patch("/api/v1/seguranca/fontes/github_secrets", json={"habilitada": True})

    recebido = {}

    def verif_repo(repo, token):
        recebido["repo"], recebido["token"] = repo, token
        return True  # dono: permissao de escrita

    with Session(engine) as s:
        from app.models import User
        user = s.exec(select(User)).first()
        asset, motivo = svc.verificar_posse(s, ws_id, user, uuid.UUID(aid),
                                            verificadores={"repo": verif_repo, "dominio": None})
        nivel = asset.nivel_autorizacao
    assert nivel == SecNivelAutorizacao.verificado
    assert recebido["repo"] == "org/meu" and recebido["token"] == "tok-dono"
    assert "posse comprovada" in motivo


def test_verificar_repo_sem_permissao_fica_declarado(auth_client):
    from app.services import secintel_service as svc

    ws_id = _ws(auth_client)
    aid = auth_client.post("/api/v1/seguranca/ativos",
                           json={"tipo": "repo", "identificador": "org/alheio"}).json()["id"]
    _dar_chave(auth_client, "github_secrets", "tok")
    auth_client.patch("/api/v1/seguranca/fontes/github_secrets", json={"habilitada": True})
    with Session(engine) as s:
        from app.models import User
        user = s.exec(select(User)).first()
        asset, motivo = svc.verificar_posse(s, ws_id, user, uuid.UUID(aid),
                                            verificadores={"repo": lambda r, t: False, "dominio": None})
        nivel = asset.nivel_autorizacao
    assert nivel == SecNivelAutorizacao.declarado
    assert "nao tem permissao" in motivo


# ---- F2: posse de dominio por DNS TXT ----

def test_dominio_desafio_txt_aparece_no_ativo(auth_client):
    r = auth_client.post("/api/v1/seguranca/ativos",
                         json={"tipo": "dominio", "identificador": "exemplo.com"})
    assert r.status_code == 201
    ativos = auth_client.get("/api/v1/seguranca/ativos").json()
    dom = [a for a in ativos if a["tipo"] == "dominio"][0]
    assert dom["desafio_posse"].startswith("sentinela-verify=")


def test_verificar_dominio_com_txt_correto(auth_client):
    from app.services import secintel_service as svc

    ws_id = _ws(auth_client)
    aid = auth_client.post("/api/v1/seguranca/ativos",
                           json={"tipo": "dominio", "identificador": "meudominio.com"}).json()["id"]
    auth_client.patch("/api/v1/seguranca/fontes/ct", json={"habilitada": True})
    # o verificador confere que recebeu o token esperado
    token = svc.token_desafio_dominio(ws_id, "meudominio.com")

    def verif_dom(dominio, tok):
        return dominio == "meudominio.com" and tok == token

    with Session(engine) as s:
        from app.models import User
        user = s.exec(select(User)).first()
        asset, motivo = svc.verificar_posse(s, ws_id, user, uuid.UUID(aid),
                                            verificadores={"repo": None, "dominio": verif_dom})
        nivel = asset.nivel_autorizacao
    assert nivel == SecNivelAutorizacao.verificado


# ---- F2: runner avisa em vez de silencio ----

def test_runner_avisa_ativos_aguardando_posse(auth_client):
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "repo", "identificador": "org/r1"})
    _dar_chave(auth_client, "github_secrets", "tok")
    auth_client.patch("/api/v1/seguranca/fontes/github_secrets", json={"habilitada": True})

    with Session(engine) as s:
        # repo ainda declarado -> nenhum elegivel, mas nao pode ser silencio
        secintel_fontes.executar_exposicao(s, ws_id, transportes={"repo_files": lambda *a: []})
        fonte = s.exec(select(SecFonte).where(SecFonte.nome == "github_secrets")).one()
        assert fonte.estado.value == "erro"
        assert "aguardando verificacao de posse" in (fonte.erro_msg or "")


# ---- F3: gate de habilitacao (reforco) ----

def test_gate_422_sem_credencial(auth_client):
    r = auth_client.patch("/api/v1/seguranca/fontes/hibp", json={"habilitada": True})
    assert r.status_code == 422
    assert "chave de api" in r.text.lower()


def test_fonte_out_expoe_flags_de_credencial(auth_client):
    fontes = {f["nome"]: f for f in auth_client.get("/api/v1/seguranca/fontes").json()}
    assert fontes["hibp"]["exige_credencial"] is True
    assert fontes["hibp"]["tem_credencial"] is False
    assert fontes["ct"]["exige_credencial"] is False
