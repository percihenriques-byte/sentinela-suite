"""Modulo Seguranca — M4: fontes opt-in + trava de consentimento + credencial.

Garante o principio central (ESPEC secao 0/10): NENHUM byte sai da maquina sem
consentimento explicito. O runner usa transportes sentinela que LEVANTAM se
chamados; se uma fonte desligada tentasse a rede, o teste explodiria.

Cobre tambem as correcoes da 6a auditoria: transporte por fonte (E2) e gate de
credencial da HIBP (E1).
"""
import uuid

from app.models.secintel import SecTipoExposicao


def _ws(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import Workspace

    with Session(engine) as s:
        return s.exec(select(Workspace)).first().id


class _RespFake:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _dar_chave(auth_client, nome, chave="chave-secreta-de-teste"):
    r = auth_client.put(f"/api/v1/seguranca/fontes/{nome}/credencial", json={"credencial": chave})
    assert r.status_code == 200, r.text
    return r.json()


def test_fonte_desligada_nunca_toca_a_rede(auth_client):
    auth_client.post("/api/v1/seguranca/ativos", json={
        "tipo": "email", "identificador": "alvo@example.com",
    })
    r = auth_client.post("/api/v1/seguranca/varreduras/exposicao")
    assert r.status_code == 200
    assert r.json() == []  # nada consultado, nada achado


def test_runner_barra_fonte_desligada(auth_client):
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "email", "identificador": "x@example.com"})
    with Session(engine) as s:
        # sem transportes -> sentinela que explode; fonte desligada nao a chama
        assert secintel_fontes.executar_exposicao(s, ws_id) == []


# ---- E1: gate de credencial da HIBP ----

def test_hibp_nao_liga_sem_chave(auth_client):
    r = auth_client.patch("/api/v1/seguranca/fontes/hibp", json={"habilitada": True})
    assert r.status_code == 422
    assert "chave" in r.text.lower()


def test_credencial_nunca_vaza_e_habilita_a_fonte(auth_client):
    chave = "AKIA-NAO-DEVE-VAZAR-1234"
    f = _dar_chave(auth_client, "hibp", chave)
    assert f["tem_credencial"] is True and f["exige_credencial"] is True
    # o valor nunca aparece na listagem
    corpo = auth_client.get("/api/v1/seguranca/fontes").text
    assert chave not in corpo
    # agora liga
    r = auth_client.patch("/api/v1/seguranca/fontes/hibp", json={"habilitada": True})
    assert r.status_code == 200 and r.json()["habilitada"] is True


def test_hibp_usa_a_chave_e_acha_vazamento(auth_client):
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    email = "vazado@example.com"
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "email", "identificador": email})
    _dar_chave(auth_client, "hibp", "chave-valida-123")
    auth_client.patch("/api/v1/seguranca/fontes/hibp", json={"habilitada": True})

    recebeu = {}

    def http_url(url, headers=None):
        recebeu["header"] = (headers or {}).get("hibp-api-key")
        assert email in url
        return _RespFake(200, [{"Name": "ExemploBreach"}])

    with Session(engine) as s:
        achados = secintel_fontes.executar_exposicao(s, ws_id, transportes={"http_url": http_url})
    assert len(achados) == 1
    assert achados[0].tipo_exposicao == SecTipoExposicao.email_em_vazamento
    assert recebeu["header"] == "chave-valida-123"  # a chave FOI enviada no header
    assert "vazado" not in achados[0].indicador_mascarado


def test_hibp_401_marca_estado_erro(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import SecFonte
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "email", "identificador": "e@example.com"})
    _dar_chave(auth_client, "hibp", "chave-ruim")
    auth_client.patch("/api/v1/seguranca/fontes/hibp", json={"habilitada": True})

    def http_401(url, headers=None):
        return _RespFake(401, None)

    with Session(engine) as s:
        secintel_fontes.executar_exposicao(s, ws_id, transportes={"http_url": http_401})
        fonte = s.exec(select(SecFonte).where(SecFonte.nome == "hibp")).one()
        assert fonte.estado.value == "erro" and "401" in (fonte.erro_msg or "")


# ---- E2: transporte por fonte + github ----

def test_github_usa_transporte_repo_files(auth_client):
    """A fonte github recebe o transporte 'repo_files' (nao um http de URL). O
    duble de contrato falha se o transporte errado for entregue."""
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    # repo precisa ser verificado; em M1 repo fica declarado, entao forcamos
    r = auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "repo", "identificador": "org/meurepo"})
    aid = r.json()["id"]
    from app.models import SecAsset
    from app.models.secintel import SecNivelAutorizacao
    with Session(engine) as s:
        a = s.get(SecAsset, uuid.UUID(aid))
        a.nivel_autorizacao = SecNivelAutorizacao.verificado
        s.add(a)
        s.commit()

    auth_client.patch("/api/v1/seguranca/fontes/github_secrets", json={"habilitada": True})

    segredo = "AKIA" + "QZ3K7RT9WP2N6VBX"

    def repo_files(asset, credencial=None):
        assert asset.identificador == "org/meurepo"
        return [("config.py", f"aws_key = {segredo}")]

    # se por engano o github recebesse 'http_url', quebraria (assinatura diferente)
    def http_url(url, headers=None):
        raise AssertionError("github nao deveria receber http_url")

    with Session(engine) as s:
        achados = secintel_fontes.executar_exposicao(
            s, ws_id, transportes={"http_url": http_url, "repo_files": repo_files})
    assert len(achados) == 1
    assert segredo not in achados[0].indicador_mascarado
    assert achados[0].indicador_mascarado.startswith("AKIA")


def test_github_repo_declarado_nao_e_consultado(auth_client):
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "repo", "identificador": "org/repo"})
    auth_client.patch("/api/v1/seguranca/fontes/github_secrets", json={"habilitada": True})

    chamado = {"n": 0}

    def repo_files(asset, credencial=None):
        chamado["n"] += 1
        return []

    with Session(engine) as s:
        secintel_fontes.executar_exposicao(s, ws_id, transportes={"repo_files": repo_files})
    assert chamado["n"] == 0, "repo apenas declarado nao deve ser consultado"


def test_fonte_local_nao_pode_ser_desligada(auth_client):
    r = auth_client.patch("/api/v1/seguranca/fontes/eventos_locais", json={"habilitada": False})
    assert r.status_code == 422
