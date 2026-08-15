"""Deteccao de secrets (ESPEC-SEGURANCA.md secao 11) — regex de prefixo
conhecido + entropia, com loop de falso-positivo embutido.

PURO: recebe texto (+ contexto opcional) e devolve achados JA mascarados, com
classificacao e fingerprint. NUNCA devolve o valor completo. O valor bruto so
existe dentro desta funcao, o tempo de calcular mascara e fingerprint.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.models.secintel import SecClassificacao, SecTipoExposicao
from app.services import secintel_mascara as mascara


@dataclass
class SecretHit:
    tipo_exposicao: SecTipoExposicao
    classificacao: SecClassificacao
    confianca: float
    indicador_mascarado: str
    fingerprint: str
    evidencia_resumo: str
    motivo_fp: str | None = None


# (nome, regex, tipo, classificacao_base, prefixo_para_mascara)
_DETECTORES = [
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}"), SecTipoExposicao.api_key,
     SecClassificacao.confirmed, "AKIA"),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), SecTipoExposicao.token,
     SecClassificacao.confirmed, None),
    ("stripe", re.compile(r"sk_live_[A-Za-z0-9]{20,}"), SecTipoExposicao.api_key,
     SecClassificacao.confirmed, "sk_live_"),
    ("slack", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), SecTipoExposicao.token,
     SecClassificacao.confirmed, None),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), SecTipoExposicao.private_key,
     SecClassificacao.confirmed, None),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}"),
     SecTipoExposicao.token, SecClassificacao.likely, None),
    ("connection_string",
     re.compile(r"[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s:/@]+@[^\s/]+"),
     SecTipoExposicao.connection_string, SecClassificacao.likely, None),
]

# atribuicao "NOME = VALOR" com nome sugestivo, para o detector generico
_GENERICO = re.compile(
    r"""(?ix)
    \b(?P<nome>[A-Za-z0-9_]*(?:secret|token|senha|password|passwd|api[_-]?key|
        access[_-]?key|private[_-]?key|client[_-]?secret)[A-Za-z0-9_]*)
    \s*[:=]\s*
    ['"]?(?P<valor>[^\s'"]{20,})['"]?
    """,
)

# sinais de que NAO e um secret real (loop de falso-positivo, ESPEC Fase 8).
# Fronteira de LETRA: digito, `_` e `-` contam como separador, entao "CHANGEME_x"
# casa, mas "testing" nao casa "test" (letra depois).
_MARCAS_FP = re.compile(
    r"(?i)(?<![a-z])(?:example|exemplo|sample|dummy|placeholder|changeme|your|"
    r"xxx+|teste?|fake|redacted|donotuse|nao.?usar)(?![a-z])"
)
_ANGULAR_FP = re.compile(r"<[^>]+>")


def _tem_marca_fp(s: str) -> bool:
    return bool(_MARCAS_FP.search(s) or _ANGULAR_FP.search(s))
_CAMINHOS_FP = (".md", ".rst", ".txt.example", ".sample")
_PASTAS_FP = ("/docs/", "docs/", "/tests/", "tests/", "/fixtures/", "fixtures/", "/example")


def _entropia(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _e_falso_positivo(valor: str, contexto: str, vizinhanca: str = "") -> str | None:
    """Devolve o motivo se parecer FP, senao None. Olha o valor, o caminho do
    arquivo E a vizinhanca do match (comentarios como '# EXAMPLE, nao usar')."""
    if _tem_marca_fp(valor):
        return "valor parece exemplo/placeholder"
    ctx = (contexto or "").lower()
    if any(ctx.endswith(ext) for ext in _CAMINHOS_FP):
        return "arquivo de documentacao/exemplo"
    if any(p in ctx for p in _PASTAS_FP):
        return "caminho de docs/testes/exemplos"
    if _tem_marca_fp(ctx):
        return "contexto de exemplo/teste"
    if vizinhanca and _tem_marca_fp(vizinhanca):
        return "marcado como exemplo/teste na vizinhanca"
    return None


def detectar(texto: str, contexto: str = "") -> list[SecretHit]:
    """Varre `texto`. `contexto` e o caminho/arquivo (usado no loop de FP e no
    resumo de evidencia). Devolve achados mascarados e classificados."""
    achados: list[SecretHit] = []
    vistos: set[str] = set()

    def _add(valor, tipo, classe, prefixo, base_conf, vizinhanca=""):
        valor = valor.strip().strip("'\"")
        fp = mascara.fingerprint(valor, tipo.value)
        if fp in vistos:
            return
        vistos.add(fp)
        motivo = _e_falso_positivo(valor, contexto, vizinhanca)
        classificacao = classe
        confianca = base_conf
        if motivo:
            classificacao = SecClassificacao.false_positive
            confianca = 0.0
        achados.append(SecretHit(
            tipo_exposicao=tipo,
            classificacao=classificacao,
            confianca=confianca,
            indicador_mascarado=mascara.mascarar_secret(valor, prefixo),
            fingerprint=fp,
            evidencia_resumo=(f"em {contexto}" if contexto else "no conteudo analisado"),
            motivo_fp=motivo,
        ))

    conf_base = {
        SecClassificacao.confirmed: 0.95,
        SecClassificacao.likely: 0.7,
        SecClassificacao.possible: 0.4,
    }

    def _viz(m):
        return texto[max(0, m.start() - 40): m.end() + 40]

    for _nome, rx, tipo, classe, prefixo in _DETECTORES:
        for m in rx.finditer(texto):
            _add(m.group(0), tipo, classe, prefixo, conf_base[classe], vizinhanca=_viz(m))

    # generico por entropia (so o que os detectores acima nao pegaram)
    for m in _GENERICO.finditer(texto):
        valor = m.group("valor").strip().strip("'\"")
        if _entropia(valor) < 4.0 or len(valor) < 20:
            continue
        _add(valor, SecTipoExposicao.secret_generico, SecClassificacao.possible, None,
             conf_base[SecClassificacao.possible], vizinhanca=_viz(m))

    return achados
