"""Masking / redaction central do modulo Seguranca (ESPEC-SEGURANCA.md, secao 12).

Ponto UNICO por onde qualquer string sensivel passa antes de ser persistida,
exibida ou logada. Se um dia um valor de secret vazar num relatorio, o bug esta
aqui — e o teste de propriedade (test_secintel_privacidade) existe para pegar.

Regra de ouro: estas funcoes NUNCA devolvem o valor completo. Mostram o
suficiente para o humano reconhecer o item (prefixo/dominio + alguns finais) e
mascaram o miolo.
"""
from __future__ import annotations

import hashlib

_BULLET = "•"  # •


def _mask_meio(valor: str, inicio: int, fim: int, min_bullets: int = 4) -> str:
    """Mantem `inicio` chars da frente e `fim` do final; miolo vira bullets."""
    if not valor:
        return ""
    if len(valor) <= inicio + fim:
        # curto demais para mostrar pontas sem revelar: mascara quase tudo
        return valor[:1] + _BULLET * max(min_bullets, len(valor) - 1)
    n_bullets = max(min_bullets, len(valor) - inicio - fim)
    return valor[:inicio] + _BULLET * n_bullets + (valor[-fim:] if fim else "")


def mascarar_email(valor: str) -> str:
    """joao.silva@example.com -> jo•••••@example.com (dominio preservado)."""
    valor = (valor or "").strip()
    if "@" not in valor:
        return _mask_meio(valor, 2, 0)
    local, _, dominio = valor.partition("@")
    local_m = local[:2] + _BULLET * max(3, len(local) - 2) if len(local) > 2 else local[:1] + _BULLET * 3
    return f"{local_m}@{dominio}"


def mascarar_generico(valor: str) -> str:
    """Para tokens/segredos/identificadores sem forma conhecida."""
    return _mask_meio(valor, 2, 2)


def mascarar_secret(valor: str, prefixo_conhecido: str | None = None) -> str:
    """Segredo com prefixo identificador (ex.: sk_live_): mostra o prefixo e os
    4 ultimos, mascara o miolo. Ex.: sk_live_••••••••••••9F3A."""
    valor = valor or ""
    if prefixo_conhecido and valor.startswith(prefixo_conhecido):
        resto = valor[len(prefixo_conhecido):]
        fim = resto[-4:] if len(resto) > 8 else ""
        n = max(8, len(resto) - len(fim))
        return f"{prefixo_conhecido}{_BULLET * n}{fim}"
    fim = valor[-4:] if len(valor) > 12 else ""
    n = max(8, len(valor) - len(fim))
    return f"{_BULLET * n}{fim}"


def mascarar_por_tipo(tipo: str, valor: str) -> str:
    if tipo == "email":
        return mascarar_email(valor)
    if tipo in ("dominio", "subdominio", "repo", "api_endpoint"):
        return valor  # nomes de dominio/repo sao publicos por natureza; nao mascarar
    return mascarar_generico(valor)


def fingerprint(valor: str, *partes: str) -> str:
    """Fingerprint estavel (sha256 truncado a 16 hex) para dedupe — nunca o
    valor em si. Aceita partes de contexto (fonte, tipo, local)."""
    base = "|".join([valor, *partes])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
