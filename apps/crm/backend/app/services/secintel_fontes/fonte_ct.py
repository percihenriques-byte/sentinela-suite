"""Adapter Certificate Transparency (crt.sh) — ESPEC secao 10.

O que SAI da maquina: o nome do dominio verificado, ao crt.sh. Detecta
subdominios/certificados que o responsavel talvez nao conheca (possivel phishing
ou exposicao). So dominios `verificado`.
"""
from __future__ import annotations

from app.models.secintel import SecClassificacao, SecNivelAutorizacao, SecTipoExposicao
from app.services import secintel_mascara as mascara

NOME = "ct"
REQUER_NIVEL = SecNivelAutorizacao.verificado
TIPOS_ATIVO = {"dominio", "subdominio"}
_API = "https://crt.sh/?q=%25.{dominio}&output=json"


def consultar(assets, http):
    from app.services.secintel_fontes import AchadoBruto

    achados = []
    for a in assets:
        resp = http(_API.format(dominio=a.identificador), {})
        status = getattr(resp, "status_code", 200)
        if status != 200:
            raise RuntimeError(f"crt.sh respondeu {status}")
        registros = resp.json() if callable(getattr(resp, "json", None)) else []
        nomes = sorted({r.get("name_value", "") for r in registros if r.get("name_value")})
        if not nomes:
            continue
        achados.append(AchadoBruto(
            asset_id=a.id,
            tipo_exposicao=SecTipoExposicao.documento_exposto,
            classificacao=SecClassificacao.possible,
            confianca=0.4,
            indicador_mascarado=a.identificador,
            evidencia_resumo=f"{len(nomes)} nome(s) em certificados publicos de {a.identificador}",
            fingerprint=mascara.fingerprint(a.identificador, "ct", str(len(nomes))),
        ))
    return achados
