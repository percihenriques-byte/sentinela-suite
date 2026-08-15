"""Modulo Seguranca — M6: auto-auditoria executavel de privacidade (Fase 12).

Se qualquer valor com FORMATO de secret aparecer completo numa resposta da API
de /seguranca ou num log gerado pelo modulo, ESTA suite falha. E a rede de
seguranca que transforma a promessa "nenhum segredo em claro" (ESPEC secao 12)
em algo verificado, nao so declarado.
"""
import logging
import re
import uuid

from app.core.logging import RedactSecretsFilter, _SECRET_LOG_RX

# padrao agregado de "isto parece um secret completo"
_SECRET = re.compile(
    r"AKIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{36,}"
    r"|sk_live_[A-Za-z0-9]{20,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)


def _ws(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import Workspace

    with Session(engine) as s:
        return s.exec(select(Workspace)).first().id


def _semear_achado_com_secret(auth_client):
    """Cria um achado a partir de um texto que CONTEM um secret real de formato.
    O pipeline tem de guardar so o mascarado; o valor completo nao pode vazar."""
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import secintel_secrets
    from app.services.secintel_fontes import _upsert_achado, AchadoBruto
    from app.models.secintel import SecClassificacao, SecTipoExposicao

    ws_id = _ws(auth_client)
    segredo = "AKIA" + "QZ3K7RT9WP2N6VBX"
    hits = secintel_secrets.detectar(f"aws_key = {segredo}", "config.py")
    assert hits
    h = hits[0]
    with Session(engine) as s:
        _upsert_achado(s, ws_id, "github_secrets", AchadoBruto(
            asset_id=None, tipo_exposicao=SecTipoExposicao.repositorio_com_secret,
            classificacao=h.classificacao, confianca=h.confianca,
            indicador_mascarado=h.indicador_mascarado, evidencia_resumo=h.evidencia_resumo,
            fingerprint=h.fingerprint,
        ))
    return segredo


def test_nenhum_secret_completo_em_respostas_da_api(auth_client):
    segredo = _semear_achado_com_secret(auth_client)

    # tambem gera eventos/incidentes e ativos, para varrer o maximo de respostas
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "email", "identificador": "x@example.com"})

    rotas = [
        "/api/v1/seguranca/visao-geral",
        "/api/v1/seguranca/ativos",
        "/api/v1/seguranca/achados",
        "/api/v1/seguranca/incidentes",
        "/api/v1/seguranca/fontes",
        "/api/v1/seguranca/auditoria",
    ]
    for rota in rotas:
        corpo = auth_client.get(rota).text
        assert not _SECRET.search(corpo), f"secret vazou em {rota}"
        assert segredo not in corpo, f"valor completo vazou em {rota}"


def test_filtro_de_log_redige_secret():
    f = RedactSecretsFilter()
    segredo = "AKIA" + "QZ3K7RT9WP2N6VBX"
    rec = logging.LogRecord("x", logging.INFO, __file__, 1,
                            "erro processando chave %s agora", (segredo,), None)
    assert f.filter(rec) is True
    msg = rec.getMessage()
    assert segredo not in msg
    assert "[REDIGIDO]" in msg


def test_filtro_de_log_nao_estraga_mensagem_comum():
    f = RedactSecretsFilter()
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "login ok user=%s", ("ana@x.com",), None)
    f.filter(rec)
    assert rec.getMessage() == "login ok user=ana@x.com"


def test_regex_de_log_cobre_os_prefixos_de_alto_sinal():
    for exemplo in ["AKIA" + "QZ3K7RT9WP2N6VBX", "ghp_" + "A" * 36, "sk_live_" + "b" * 24]:
        assert _SECRET_LOG_RX.search(exemplo)
