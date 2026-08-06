"""Roda o corpus rotulado contra o motor JS — o que roda no navegador da crianca.

`Medir-Precisao.ps1` mede o classificador PowerShell. Mas quem protege a tela da
crianca e `extensao/classificador.js`. Enquanto so o PS era medido, um termo que
existisse apenas nele passava direto no navegador e o corpus marcava 100% sem
perceber — foi assim que `xingamentos pesados` e `como criar conta no` ficaram
de fora do JS sem ninguem notar.

Este script fecha o buraco: le o MESMO corpus do Medir-Precisao.ps1, carrega o
classificador.js num Chromium de verdade e compara veredito a veredito.

Uso (a partir da raiz do monorepo):
    apps/crm/backend/.venv/Scripts/python.exe apps/guardian/app/Testes/Testar-Paridade.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
APP = RAIZ / "apps" / "guardian" / "app"
CORPUS_PS = APP / "Testes" / "Medir-Precisao.ps1"
CLASSIFICADOR_JS = APP / "extensao" / "classificador.js"


def ler_corpus() -> list[tuple[str, bool]]:
    """Extrai os pares @('texto', $true/$false) do script de precisao."""
    texto = CORPUS_PS.read_text(encoding="utf-8", errors="replace")
    inicio = texto.index("$CORPUS = @(")
    # o corpus termina na linha que fecha o array
    corpo = texto[inicio:]
    casos = re.findall(r"@\(\s*'((?:[^']|'')*)'\s*,\s*\$(true|false)\s*\)", corpo)
    return [(t.replace("''", "'"), v == "true") for t, v in casos]


def main() -> int:
    from playwright.sync_api import sync_playwright

    corpus = ler_corpus()
    print(f"\n  Corpus lido de Medir-Precisao.ps1: {len(corpus)} casos")
    if len(corpus) < 300:
        print("  [FALHA] corpus menor que o esperado — o parser quebrou?")
        return 1

    js = CLASSIFICADOR_JS.read_text(encoding="utf-8", errors="replace")

    with sync_playwright() as pw:
        nav = pw.chromium.launch(headless=True)
        pag = nav.new_page()
        erros_js: list[str] = []
        pag.on("pageerror", lambda e: erros_js.append(str(e)))
        pag.set_content("<!doctype html><meta charset='utf-8'><body></body>")
        pag.add_script_tag(content=js)
        if erros_js:
            print(f"  [FALHA] classificador.js nao carrega: {erros_js[:2]}")
            nav.close()
            return 1
        if not pag.evaluate("() => !!(window.SentinelaIA && window.SentinelaIA.classify)"):
            print("  [FALHA] window.SentinelaIA.classify nao existe")
            nav.close()
            return 1

        vereditos = pag.evaluate(
            """(casos) => casos.map(c => {
                 try { return !!window.SentinelaIA.classify(c, {}).block; }
                 catch (e) { return null; }
               })""",
            [t for t, _ in corpus],
        )
        nav.close()

    falsos_pos = []   # bloqueou o que era legitimo
    falsos_neg = []   # deixou passar o que era improprio
    quebrados = []
    for (texto, esperado), obtido in zip(corpus, vereditos):
        if obtido is None:
            quebrados.append(texto)
        elif obtido and not esperado:
            falsos_pos.append(texto)
        elif esperado and not obtido:
            falsos_neg.append(texto)

    acertos = len(corpus) - len(falsos_pos) - len(falsos_neg) - len(quebrados)
    print(f"  MOTOR JS (o do navegador da crianca)")
    print(f"  acertos: {acertos}/{len(corpus)}  |  acuracia: {round(acertos / len(corpus) * 100)}%")
    print(f"  Falsos-POSITIVOS (bloqueou legitimo): {len(falsos_pos)}")
    for t in falsos_pos[:10]:
        print(f"     - {t}")
    print(f"  Falsos-NEGATIVOS (deixou passar): {len(falsos_neg)}")
    for t in falsos_neg[:10]:
        print(f"     - {t}")
    if quebrados:
        print(f"  ERROS de execucao: {len(quebrados)} -> {quebrados[:5]}")

    print("\n  " + "-" * 42)
    if falsos_pos or falsos_neg or quebrados:
        print("  RESULTADO: o motor do navegador NAO bate com o corpus\n")
        return 1
    print("  RESULTADO: motor do navegador bate 100% com o corpus\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
