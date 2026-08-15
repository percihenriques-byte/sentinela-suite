"""Adapter Have I Been Pwned (ESPEC secao 10; correcao auditoria E1).

O que SAI da maquina: o e-mail monitorado, a API oficial do HIBP. Senhas NUNCA
saem por aqui — este adapter cobre a exposicao de E-MAIL em vazamentos.

A API v3 do HIBP EXIGE o header `hibp-api-key` (chave paga). Sem credencial, a
fonte nem liga (gate no runner) — nao adianta consultar e tomar 401. A chave
vem cifrada em SecFonte.credencial_enc e chega aqui como `credencial`.

Transporte "http_url": transporte(url, headers) -> resposta (.status_code, .json()).
"""
from __future__ import annotations

from app.models.secintel import SecClassificacao, SecNivelAutorizacao, SecTipoExposicao
from app.services import secintel_mascara as mascara

NOME = "hibp"
REQUER_NIVEL = SecNivelAutorizacao.declarado
TIPOS_ATIVO = {"email"}
TRANSPORTE = "http_url"
EXIGE_CREDENCIAL = True
_API = "https://haveibeenpwned.com/api/v3/breachedaccount/"


def consultar(assets, transporte, credencial):
    from app.services.secintel_fontes import AchadoBruto

    if not credencial:
        # o runner ja barra por EXIGE_CREDENCIAL, mas defesa em profundidade
        raise RuntimeError("HIBP exige chave de API (hibp-api-key) e nenhuma foi configurada")

    headers = {"hibp-api-key": credencial, "User-Agent": "Sentinela-Seguranca"}
    achados = []
    for a in assets:
        if a.tipo != "email":
            continue
        resp = transporte(_API + a.identificador + "?truncateResponse=true", headers)
        status = getattr(resp, "status_code", 200)
        if status == 404:
            continue  # nao aparece em vazamento
        if status == 401:
            raise RuntimeError("HIBP recusou a chave de API (401) — verifique a credencial")
        if status == 429:
            raise RuntimeError("HIBP limitou a taxa (429) — tente mais tarde")
        if status != 200:
            raise RuntimeError(f"HIBP respondeu {status}")
        vazamentos = resp.json() if callable(getattr(resp, "json", None)) else []
        nomes = [b.get("Name", "?") for b in vazamentos][:5]
        achados.append(AchadoBruto(
            asset_id=a.id,
            tipo_exposicao=SecTipoExposicao.email_em_vazamento,
            classificacao=SecClassificacao.confirmed,
            confianca=0.9,
            indicador_mascarado=mascara.mascarar_email(a.identificador),
            evidencia_resumo=f"e-mail em {len(vazamentos)} vazamento(s): {', '.join(nomes)}",
            fingerprint=mascara.fingerprint(a.identificador, "hibp"),
        ))
    return achados
