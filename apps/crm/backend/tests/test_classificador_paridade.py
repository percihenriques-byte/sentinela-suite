"""Paridade entre os dois classificadores do Sentinela.

O classificador existe duas vezes: em PowerShell (`Sentinela-Classificador.ps1`,
usado pelo app Windows e medido pelo corpus de 373 casos) e em JavaScript
(`extensao/classificador.js`, que e o que roda no navegador da crianca).

Manter duas copias a mao ja custou caro: uma auditoria independente contou os
termos e achou 315 no PS contra 313 no JS — `xingamentos pesados` e
`como criar conta no` existiam so no lado que o corpus mede, e passavam direto
na tela da crianca. O corpus marcava 100% sem perceber, porque roda contra o PS.

Este teste e o alarme. Roda em qualquer maquina (so le texto, nao precisa de
PowerShell nem navegador), entao entra no CI e falha no push que dessincronizar.

A solucao definitiva e um `rules.json` unico gerando os dois arquivos. Enquanto
ela nao existe, isto aqui impede a divergencia de passar despercebida.
"""
import re
import unicodedata
from pathlib import Path

import pytest

GUARDIAN = Path(__file__).resolve().parents[4] / "apps" / "guardian" / "app"
PS = GUARDIAN / "Sentinela-Classificador.ps1"
JS = GUARDIAN / "extensao" / "classificador.js"


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def _peso(bruto: str) -> float:
    """`.5` e `0.5` sao o mesmo peso; `1` e `1.0` tambem."""
    return round(float(bruto), 4)


def categorias_ps() -> dict[str, dict[str, float]]:
    texto = PS.read_text(encoding="utf-8", errors="replace")
    fora = {}
    for bloco in re.findall(r"@\{\s*Nome='([^']+)'.*?Termos=@\{(.*?)\}\s*\}", texto, re.S):
        nome, corpo = bloco
        termos = {t: _peso(p) for t, p in re.findall(r"'([^']+)'\s*=\s*([\d.]+)", corpo)}
        fora[_sem_acento(nome)] = termos
    return fora


def categorias_js() -> dict[str, dict[str, float]]:
    texto = JS.read_text(encoding="utf-8", errors="replace")
    fora = {}
    for nome, corpo in re.findall(r"\{\s*nome:'([^']+)'.*?termos:\{(.*?)\}\s*\}", texto, re.S):
        termos = {t: _peso(p) for t, p in re.findall(r"'([^']+)'\s*:\s*([\d.]+)", corpo)}
        fora[_sem_acento(nome)] = termos
    return fora


def test_os_dois_classificadores_tem_as_mesmas_categorias():
    ps, js = categorias_ps(), categorias_js()
    assert ps, "nao consegui ler as categorias do PowerShell"
    assert js, "nao consegui ler as categorias do JavaScript"
    assert set(ps) == set(js), (
        f"categorias so no PS: {sorted(set(ps) - set(js))} | "
        f"so no JS: {sorted(set(js) - set(ps))}"
    )


@pytest.mark.parametrize("qual", ["termos", "pesos"])
def test_termos_e_pesos_batem_categoria_a_categoria(qual):
    ps, js = categorias_ps(), categorias_js()
    problemas = []
    for cat in sorted(set(ps) & set(js)):
        a, b = ps[cat], js[cat]
        if qual == "termos":
            if set(a) != set(b):
                problemas.append(
                    f"[{cat}] so no PS: {sorted(set(a) - set(b))} | so no JS: {sorted(set(b) - set(a))}"
                )
        else:
            divergentes = {t: (a[t], b[t]) for t in set(a) & set(b) if a[t] != b[t]}
            if divergentes:
                problemas.append(f"[{cat}] pesos diferentes: {divergentes}")
    assert not problemas, "classificadores dessincronizados:\n" + "\n".join(problemas)


def test_contagem_total_de_termos_e_identica():
    """Rede de seguranca grosseira: pega drift mesmo se o parser de categoria
    mudar de forma e os testes acima virarem no-op."""
    ps_bruto = re.findall(r"'([^']{2,})'\s*=\s*[\d.]+", PS.read_text(encoding="utf-8", errors="replace"))
    js_bruto = re.findall(r"'([^']{2,})'\s*:\s*[\d.]+", JS.read_text(encoding="utf-8", errors="replace"))
    assert len(set(ps_bruto)) == len(set(js_bruto)), (
        f"PS tem {len(set(ps_bruto))} termos, JS tem {len(set(js_bruto))}: "
        f"diferenca {sorted(set(ps_bruto) ^ set(js_bruto))}"
    )


def test_contexto_seguro_bate_entre_os_dois():
    """A lista de contexto seguro e o que evita bloquear 'reproducao humana' ou
    'aula de biologia'. Divergir aqui gera falso-positivo so no navegador."""
    ps_texto = PS.read_text(encoding="utf-8", errors="replace")
    js_texto = JS.read_text(encoding="utf-8", errors="replace")

    bloco_js = re.search(r"CTX_SEGURO\s*=\s*\[(.*?)\]", js_texto, re.S)
    assert bloco_js, "nao achei CTX_SEGURO no JS"
    ctx_js = {_sem_acento(t) for t in re.findall(r"'([^']+)'", bloco_js.group(1))}

    bloco_ps = re.search(r"CONTEXTO_SEGURO\s*=\s*@\((.*?)\)", ps_texto, re.S)
    assert bloco_ps, "nao achei CONTEXTO_SEGURO no PS"
    ctx_ps = {_sem_acento(t) for t in re.findall(r"'([^']+)'", bloco_ps.group(1))}

    assert ctx_ps == ctx_js, (
        f"contexto seguro so no PS: {sorted(ctx_ps - ctx_js)} | so no JS: {sorted(ctx_js - ctx_ps)}"
    )


def test_arquivos_avisam_que_sao_espelho():
    """Quem abrir um dos dois precisa saber que existe o outro."""
    for caminho in (PS, JS):
        cabecalho = caminho.read_text(encoding="utf-8", errors="replace")[:2500].lower()
        assert "espelho" in cabecalho or "paridade" in cabecalho, (
            f"{caminho.name} nao avisa que tem um espelho a manter"
        )
