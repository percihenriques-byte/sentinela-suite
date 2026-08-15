"""Scoring de risco do modulo Seguranca (ESPEC-SEGURANCA.md, secao 9).

Funcao PURA: sem I/O, sem banco, sem rede. So aritmetica sobre os fatores.

    score = round(100 * P * I * C * R) + bonus_correlacao   (limitado a 0..100)

    P  probabilidade      0.1 fraca | 0.5 media | 0.9 forte
    I  impacto do ativo    0..1 (tabela _IMPACTO)
    C  confianca da evidencia 0..1 (CONFIRMED=1.0, LIKELY=0.7, POSSIBLE=0.4)
    R  recencia            2^(-idade_dias/30), piso 0.25 (meia-vida 30 dias)
    bonus                  +10 por chave de correlacao distinta alem da 1a, teto +30

Bandas: 0-9 INFO | 10-29 LOW | 30-54 MEDIUM | 55-79 HIGH | 80-100 CRITICAL

Trava anti-alarmismo: CRITICAL so vale com evidencia CONFIRMADA e C >= 0.8.
Sem isso, rebaixa para HIGH. Incidentes de correlacao local (sem um achado
CONFIRMED por tras) nunca chegam a CRITICAL — por construcao.
"""
from __future__ import annotations

from app.models.secintel import SecClassificacao, SecSeveridade

# probabilidade por nivel de hit / origem
P_FORTE = 0.9
P_MEDIA = 0.5
P_FRACA = 0.1

# confianca por classificacao de achado
C_POR_CLASSIFICACAO = {
    SecClassificacao.confirmed: 1.0,
    SecClassificacao.likely: 0.7,
    SecClassificacao.possible: 0.4,
    SecClassificacao.false_positive: 0.0,
}

_IMPACTO = {
    # (peso, rotulos) — ver ESPEC secao 9
    1.0: {"credencial", "secret", "dispositivo_crianca", "conta_responsavel"},
    0.7: {"repo", "dominio", "subdominio", "api_endpoint"},
    0.4: {"username", "email_declarado", "conta_externa"},
}

_BANDAS = [
    (80, SecSeveridade.critical),
    (55, SecSeveridade.high),
    (30, SecSeveridade.medium),
    (10, SecSeveridade.low),
    (0, SecSeveridade.info),
]


def impacto_por_rotulo(rotulo: str) -> float:
    for peso, rotulos in _IMPACTO.items():
        if rotulo in rotulos:
            return peso
    return 0.4  # default conservador


def recencia(idade_dias: float) -> float:
    r = 2.0 ** (-max(0.0, idade_dias) / 30.0)
    return max(0.25, r)


def banda(score: int) -> SecSeveridade:
    for limite, sev in _BANDAS:
        if score >= limite:
            return sev
    return SecSeveridade.info


def calcular(
    p: float,
    impacto: float,
    confianca: float,
    idade_dias: float,
    chaves_extra: int = 0,
    confirmado: bool = False,
) -> tuple[int, SecSeveridade]:
    """Devolve (score 0..100, severidade). `chaves_extra` = numero de chaves de
    correlacao ALEM da primeira. `confirmado` libera a banda CRITICAL."""
    base = 100.0 * p * impacto * confianca * recencia(idade_dias)
    bonus = min(30, 10 * max(0, chaves_extra))
    score = int(round(min(100.0, base + bonus)))
    sev = banda(score)
    # trava anti-alarmismo: CRITICAL exige evidencia confirmada + confianca alta
    if sev == SecSeveridade.critical and not (confirmado and confianca >= 0.8):
        sev = SecSeveridade.high
    return score, sev
