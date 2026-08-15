"""Adapter GitHub secrets (ESPEC secao 10-11).

O que SAI da maquina: o nome dos SEUS repositorios, ao GitHub (para listar e
clonar). O conteudo e analisado LOCALMENTE por secintel_secrets. So repos
`verificado`. Aqui, `http` fornece o conteudo dos arquivos do repo
(`http(asset) -> list[(caminho, texto)]`), mantendo o clone/fetch fora do nucleo
testavel: o que importa e a deteccao + o loop de FP, cobertos pelo corpus.
"""
from __future__ import annotations

from app.models.secintel import SecClassificacao, SecNivelAutorizacao, SecTipoExposicao
from app.services import secintel_secrets

NOME = "github_secrets"
REQUER_NIVEL = SecNivelAutorizacao.verificado
TIPOS_ATIVO = {"repo"}


def consultar(assets, http):
    from app.services.secintel_fontes import AchadoBruto

    achados = []
    for a in assets:
        arquivos = http(a)  # [(caminho, texto)]
        for caminho, texto in arquivos:
            for hit in secintel_secrets.detectar(texto, contexto=caminho):
                tipo = (SecTipoExposicao.repositorio_com_secret
                        if hit.classificacao == SecClassificacao.confirmed
                        else hit.tipo_exposicao)
                achados.append(AchadoBruto(
                    asset_id=a.id,
                    tipo_exposicao=tipo,
                    classificacao=hit.classificacao,
                    confianca=hit.confianca,
                    indicador_mascarado=hit.indicador_mascarado,
                    evidencia_resumo=f"{a.identificador}: {hit.evidencia_resumo}",
                    fingerprint=secintel_secrets_fp(a.identificador, hit.fingerprint),
                    motivo_fp=hit.motivo_fp,
                ))
    return achados


def secintel_secrets_fp(repo: str, fp: str) -> str:
    from app.services import secintel_mascara as mascara
    return mascara.fingerprint(fp, "github", repo)
