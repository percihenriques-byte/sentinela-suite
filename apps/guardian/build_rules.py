#!/usr/bin/env python3
"""Gerador determinista do classificador do Sentinela.

Le a fonte unica de verdade (apps/guardian/rules.json) e regenera os DOIS
motores a partir dela:

    apps/guardian/app/extensao/classificador.js   (motor do navegador da crianca)
    apps/guardian/app/Sentinela-Classificador.ps1  (motor do app Windows / corpus)

A logica de cada motor vive no seu template em apps/guardian/build/*.tmpl; os
DADOS (categorias, termos, pesos, contexto seguro, mapas de normalizacao e
limiar) vem exclusivamente do rules.json. Assim a regra existe uma so vez: os
dois arquivos gerados nunca mais divergem, porque nascem do mesmo lugar.

Uso:
    python apps/guardian/build_rules.py            # regenera os dois arquivos
    python apps/guardian/build_rules.py --check    # falha se algo esta fora de sincronia

O --check nao escreve nada: gera em memoria e compara com o que esta em disco.
E o que o CI e o Verificar-Tudo.ps1 rodam para pegar edicao manual ou drift.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent            # apps/guardian
RULES = BASE / "rules.json"
TMPL = BASE / "gerador"
JS_OUT = BASE / "app" / "extensao" / "classificador.js"
PS_OUT = BASE / "app" / "Sentinela-Classificador.ps1"


# --------------------------------------------------------------------------
# formatacao de valores (preserva 1:1 o que cada linguagem ja usava)
# --------------------------------------------------------------------------
def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _js_peso(w: float) -> str:
    # JS usa 1, .5, .35 (sem zero a esquerda)
    if float(w).is_integer():
        return str(int(w))
    return ("%g" % w).lstrip("0")


def _ps_peso(w: float) -> str:
    # PS usa 1.0, 0.5, 0.35
    if float(w).is_integer():
        return "%d.0" % int(w)
    return "%g" % w


def _classe_regex(chaves) -> str:
    # monta uma classe de caractere [..] de regex, escapando o que e especial dentro dela
    out = []
    for k in chaves:
        out.append("\\" + k if k in "\\]^-" else k)
    return "[" + "".join(out) + "]"


# --------------------------------------------------------------------------
# blocos de dados por linguagem
# --------------------------------------------------------------------------
def _js_blocos(regras: dict, sha: str) -> dict:
    homo = regras["normalizacao"]["homoglifos"]
    leet = regras["normalizacao"]["leet"]

    homo_obj = "{" + ",".join(f"'{k}':'{v}'" for k, v in homo.items()) + "}"
    leet_obj = "{ " + ",".join(f"'{k}':'{v}'" for k, v in leet.items()) + " }"

    cats = []
    for c in regras["categorias"]:
        termos = ",".join(f"'{t}':{_js_peso(p)}" for t, p in c["termos"].items())
        cats.append(
            f"{{ nome:'{c['nome']}', padrao:{str(c['padrao']).lower()}, "
            f"semReducao:{str(c['semReducao']).lower()}, termos:{{{termos}}}}}"
        )
    cats_js = "[\n" + ",\n".join("    " + linha for linha in cats) + "\n  ]"

    ctx_js = "[" + ",".join(f"'{c}'" for c in regras["contextoSeguro"]) + "]"

    header = f"""/*
  classificador.js — ARQUIVO GERADO A PARTIR DE rules.json — NÃO EDITE À MÃO.

  Gerado por apps/guardian/build_rules.py a partir de apps/guardian/rules.json,
  a fonte unica de verdade. Para mudar termos, pesos, contexto seguro ou os
  mapas de normalizacao, edite o rules.json e rode:
      python apps/guardian/build_rules.py

  Este e o motor que roda no NAVEGADOR da crianca; e o espelho do
  Sentinela-Classificador.ps1 — os dois nascem do mesmo rules.json, entao nao
  divergem mais. A paridade segue checada por
  apps/crm/backend/tests/test_classificador_paridade.py e a sincronia com o
  rules.json por apps/crm/backend/tests/test_classificador_sincronia.py.

  API publica (inalterada): window.SentinelaIA.classify(texto, config),
  .classifyPagina(texto, config, limiar) e .temas.

  rules.json sha256: {sha}
*/"""

    return {
        "HEADER": header,
        "HOMO": homo_obj,
        "HOMO_CLASS": _classe_regex(homo.keys()),
        "LEET": leet_obj,
        "LEET_CLASS": _classe_regex(leet.keys()),
        "CATS": cats_js,
        "CTX": ctx_js,
    }


def _ps_blocos(regras: dict, sha: str) -> dict:
    homo = regras["normalizacao"]["homoglifos"]
    leet = regras["normalizacao"]["leet"]

    homo_ps = "@{ " + "; ".join(f"([char]0x{ord(k):04X})='{v}'" for k, v in homo.items()) + " }"
    leet_ps = "@{ " + "; ".join(f"'{k}'='{v}'" for k, v in leet.items()) + " }"

    cats = []
    for c in regras["categorias"]:
        nome = _sem_acento(c["nome"])                      # PS e ASCII (lido como ANSI)
        termos = ";".join(f"'{t}'={_ps_peso(p)}" for t, p in c["termos"].items())
        padrao = "$true" if c["padrao"] else "$false"
        semred = "$true" if c["semReducao"] else "$false"
        cats.append(
            f"    @{{ Nome='{nome}'; Padrao={padrao}; SemReducao={semred}; Termos=@{{\n"
            f"        {termos} }} }}"
        )
    cats_ps = "@(\n" + ",\n".join(cats) + "\n)"

    ctx_ps = "@(\n" + ",\n".join(f"    '{c}'" for c in regras["contextoSeguro"]) + "\n)"

    header = f"""<#
    Sentinela-Classificador.ps1
    ARQUIVO GERADO A PARTIR DE rules.json - NAO EDITE A MAO.

    Gerado por apps/guardian/build_rules.py a partir de apps/guardian/rules.json,
    a fonte unica de verdade. Para mudar termos, pesos, contexto seguro ou os
    mapas de normalizacao, edite o rules.json e rode:
        python apps/guardian/build_rules.py

    Este arquivo e medido pelo corpus de 373 casos e usado pelo app Windows; e o
    espelho de extensao/classificador.js - os dois nascem do mesmo rules.json,
    entao nao divergem mais. A paridade segue checada por
    apps/crm/backend/tests/test_classificador_paridade.py e a sincronia com o
    rules.json por apps/crm/backend/tests/test_classificador_sincronia.py.

    A API publica (funcoes) nao muda: Get-ClassificacaoConteudo,
    Get-ClassificacaoPagina, Test-ConteudoImproprio, Get-TemasDisponiveis.

    rules.json sha256: {sha}
#>"""

    return {
        "HEADER": header,
        "HOMO": homo_ps,
        "LEET": leet_ps,
        "CATS": cats_ps,
        "CTX": ctx_ps,
        "LIMIAR": _ps_peso(regras["limiarPadrao"]),
    }


def _aplicar(template: str, blocos: dict, rotulo: str) -> str:
    txt = template
    for token, valor in blocos.items():
        marca = "{{" + token + "}}"
        if marca not in txt:
            raise RuntimeError(f"{rotulo}: token {marca} ausente no template")
        txt = txt.replace(marca, valor)
    # nenhum token pode sobrar
    import re
    sobra = re.findall(r"\{\{\w+\}\}", txt)
    if sobra:
        raise RuntimeError(f"{rotulo}: tokens nao resolvidos: {sobra}")
    return txt


# --------------------------------------------------------------------------
# API do gerador
# --------------------------------------------------------------------------
def hash_regras() -> str:
    return hashlib.sha256(RULES.read_bytes()).hexdigest()


def gerar() -> dict:
    """Gera o conteudo dos dois arquivos EM MEMORIA. Retorna {Path: str}."""
    regras = json.loads(RULES.read_text(encoding="utf-8"))
    sha = hash_regras()
    js_tmpl = (TMPL / "classificador.js.tmpl").read_text(encoding="utf-8")
    ps_tmpl = (TMPL / "Sentinela-Classificador.ps1.tmpl").read_text(encoding="utf-8")
    return {
        JS_OUT: _aplicar(js_tmpl, _js_blocos(regras, sha), "JS"),
        PS_OUT: _aplicar(ps_tmpl, _ps_blocos(regras, sha), "PS"),
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    checar = "--check" in argv
    gerado = gerar()
    fora = []
    for caminho, conteudo in gerado.items():
        atual = caminho.read_text(encoding="utf-8") if caminho.exists() else None
        if checar:
            if atual != conteudo:
                fora.append(caminho)
        else:
            if atual != conteudo:
                caminho.write_text(conteudo, encoding="utf-8")
                print(f"  gerado: {caminho.relative_to(BASE.parent.parent)}")
            else:
                print(f"  ok (sem mudanca): {caminho.relative_to(BASE.parent.parent)}")

    if checar:
        if fora:
            print("  [FORA DE SINCRONIA] estes arquivos nao batem com rules.json:")
            for c in fora:
                print(f"     - {c}")
            print("  Rode: python apps/guardian/build_rules.py")
            return 1
        print(f"  OK: classificador.js e Sentinela-Classificador.ps1 em sincronia com rules.json")
        print(f"      sha256(rules.json) = {hash_regras()}")
        return 0
    print(f"  sha256(rules.json) = {hash_regras()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
