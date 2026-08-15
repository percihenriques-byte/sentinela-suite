"""Adapter GitHub secrets (ESPEC secao 10-11; correcao auditoria E2).

O que SAI da maquina: o nome dos SEUS repositorios, ao GitHub (para listar e
ler o conteudo). O conteudo e analisado LOCALMENTE por secintel_secrets. So
repos `verificado`.

Transporte "repo_files": transporte(asset) -> list[(caminho, texto)]. O provedor
real (secintel_scheduler._repo_files_github) usa a API tarball do GitHub, com
token opcional cifrado para repos privados, limite de tamanho por arquivo e
allowlist de extensoes de texto. Aqui fica so a deteccao, coberta pelo corpus.
"""
from __future__ import annotations

from app.models.secintel import SecClassificacao, SecNivelAutorizacao, SecTipoExposicao
from app.services import secintel_secrets

NOME = "github_secrets"
REQUER_NIVEL = SecNivelAutorizacao.verificado
TIPOS_ATIVO = {"repo"}
TRANSPORTE = "repo_files"
EXIGE_CREDENCIAL = False  # token opcional (repo publico dispensa)


def consultar(assets, transporte, credencial=None):
    from app.services.secintel_fontes import AchadoBruto
    from app.services import secintel_mascara as mascara

    achados = []
    for a in assets:
        arquivos = transporte(a, credencial)  # [(caminho, texto)]
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
                    fingerprint=mascara.fingerprint(hit.fingerprint, "github", a.identificador),
                    motivo_fp=hit.motivo_fp,
                ))
    return achados
