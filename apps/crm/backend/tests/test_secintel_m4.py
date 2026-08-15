"""Modulo Seguranca — M4: fontes opt-in + trava de consentimento.

Garante o principio central (ESPEC secao 0/10): NENHUM byte sai da maquina sem
consentimento explicito. O runner de fontes usa um `http` sentinela que LEVANTA
se chamado; se uma fonte desligada tentasse a rede, o teste explodiria.
"""
import uuid

import pytest

from app.models.secintel import SecClassificacao, SecNivelAutorizacao, SecTipoExposicao


def _ws(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import Workspace

    with Session(engine) as s:
        return s.exec(select(Workspace)).first().id


def _email_login(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import User

    with Session(engine) as s:
        return s.exec(select(User)).first().email


class _RespFake:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_fonte_desligada_nunca_toca_a_rede(auth_client):
    """Sem consentimento, POST /varreduras/exposicao nao chama fonte alguma e
    devolve vazio. (O runner usa o http sentinela; se chamasse, levantaria.)"""
    # cadastra um e-mail (ativo elegivel para hibp), mas NAO liga a fonte
    auth_client.post("/api/v1/seguranca/ativos", json={
        "tipo": "email", "identificador": "alvo@example.com",
    })
    r = auth_client.post("/api/v1/seguranca/varreduras/exposicao")
    assert r.status_code == 200
    assert r.json() == []  # nada consultado, nada achado


def test_runner_barra_fonte_desligada_mesmo_com_ativo(auth_client):
    """Chamada direta ao runner com o http sentinela: fonte desligada nao pode
    disparar a excecao de rede."""
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    auth_client.post("/api/v1/seguranca/ativos", json={
        "tipo": "email", "identificador": "x@example.com",
    })
    with Session(engine) as s:
        # http sentinela (default) levanta se chamado — nao deve ser chamado
        achados = secintel_fontes.executar_exposicao(s, ws_id)
        assert achados == []


def test_ligar_hibp_registra_consentimento_e_encontra_vazamento(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import SecFonte
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    email = "vazado@example.com"
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "email", "identificador": email})

    # liga a fonte (consentimento) via API
    r = auth_client.patch("/api/v1/seguranca/fontes/hibp", json={"habilitada": True})
    assert r.status_code == 200 and r.json()["habilitada"] is True

    with Session(engine) as s:
        fonte = s.exec(select(SecFonte).where(SecFonte.nome == "hibp")).one()
        assert fonte.consentida_em is not None and fonte.consentida_por is not None

        # agora COM consentimento, injeta um http fake (a rede real nao roda em teste)
        def http_fake(url, headers=None):
            assert email in url  # so o e-mail consentido sai
            return _RespFake(200, [{"Name": "ExemploBreach"}])

        achados = secintel_fontes.executar_exposicao(s, ws_id, http=http_fake)
        assert len(achados) == 1
        a = achados[0]
        assert a.tipo_exposicao == SecTipoExposicao.email_em_vazamento
        # e-mail mascarado, dominio preservado; valor local nunca completo
        assert "vazado" not in a.indicador_mascarado
        assert "@example.com" in a.indicador_mascarado

    # auditoria registrou o consentimento
    acoes = [l["acao"] for l in auth_client.get("/api/v1/seguranca/auditoria").json()]
    assert "fonte_habilitada" in acoes


def test_fonte_local_nao_pode_ser_desligada(auth_client):
    r = auth_client.patch("/api/v1/seguranca/fontes/eventos_locais", json={"habilitada": False})
    assert r.status_code == 422


def test_github_secrets_exige_repo_verificado(auth_client):
    """github_secrets requer nivel `verificado`; um repo `declarado` nao entra
    na consulta — protege contra varrer repo que nao e comprovadamente seu."""
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "repo", "identificador": "org/repo"})
    auth_client.patch("/api/v1/seguranca/fontes/github_secrets", json={"habilitada": True})

    chamado = {"n": 0}

    def http_fake(asset):
        chamado["n"] += 1
        return [("app.py", "x=1")]

    with Session(engine) as s:
        secintel_fontes.executar_exposicao(s, ws_id, http=http_fake)
    assert chamado["n"] == 0, "repo apenas declarado nao deveria ser consultado"


def test_exposicao_via_api_com_fonte_ligada_gera_achado_mascarado(auth_client):
    """Fim a fim pela API: liga hibp, roda exposicao (com http fake via runner),
    achado aparece em /achados mascarado."""
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import SecFonte
    from app.services import secintel_fontes

    ws_id = _ws(auth_client)
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "email", "identificador": "leak@example.com"})
    auth_client.patch("/api/v1/seguranca/fontes/hibp", json={"habilitada": True})

    with Session(engine) as s:
        def http_fake(url, headers=None):
            return _RespFake(200, [{"Name": "B1"}, {"Name": "B2"}])
        secintel_fontes.executar_exposicao(s, ws_id, http=http_fake)

    achados = auth_client.get("/api/v1/seguranca/achados").json()
    assert len(achados) == 1
    assert "leak" not in achados[0]["indicador_mascarado"]
