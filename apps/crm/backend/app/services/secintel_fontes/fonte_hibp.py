"""Adapter Have I Been Pwned (ESPEC secao 10).

O que SAI da maquina: o e-mail monitorado, a API oficial do HIBP. Senhas NUNCA
saem — a checagem de senha usa k-anonymity (so os 5 primeiros chars do hash
SHA-1). Este adapter cobre a exposicao de E-MAIL em vazamentos; a senha entra
por um fluxo proprio de range, fora daqui.

`http(url, headers)` -> objeto com .status_code e .json()/.text. Injetado pelo
runner (default: sentinela que levanta se chamado sem consentimento).
"""
from __future__ import annotations

from app.models.secintel import SecClassificacao, SecNivelAutorizacao, SecTipoExposicao
from app.services import secintel_mascara as mascara

NOME = "hibp"
REQUER_NIVEL = SecNivelAutorizacao.declarado
TIPOS_ATIVO = {"email"}
_API = "https://haveibeenpwned.com/api/v3/breachedaccount/"


def consultar(assets, http):
    from app.services.secintel_fontes import AchadoBruto

    achados = []
    for a in assets:
        if a.tipo != "email":
            continue
        resp = http(_API + a.identificador, {"User-Agent": "Sentinela-Seguranca"})
        status = getattr(resp, "status_code", 200)
        if status == 404:
            continue  # nao aparece em vazamento
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
