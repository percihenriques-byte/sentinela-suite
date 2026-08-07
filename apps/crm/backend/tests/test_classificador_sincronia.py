"""Sincronia entre rules.json (fonte unica) e os dois motores gerados.

O test_classificador_paridade.py garante que PS e JS concordam ENTRE SI. Este
aqui garante o passo seguinte da defesa: que os dois foram de fato GERADOS a
partir do rules.json e nao editados a mao depois.

Como funciona: importa o gerador (apps/guardian/build_rules.py), regenera os
dois arquivos EM MEMORIA e compara com o que esta em disco. Se alguem editar
classificador.js ou Sentinela-Classificador.ps1 a mao (sem mexer no rules.json),
a regeneracao nao reproduz a edicao e este teste falha. Se alguem mexer no
rules.json e esquecer de rodar o gerador, o conteudo em disco fica velho e este
teste tambem falha. Roda em qualquer maquina (so le texto, nao precisa de
PowerShell nem navegador), entao entra no CI.
"""
import hashlib
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[4]
GUARDIAN = RAIZ / "apps" / "guardian"
RULES = GUARDIAN / "rules.json"
BUILD = GUARDIAN / "build_rules.py"
JS = GUARDIAN / "app" / "extensao" / "classificador.js"
PS = GUARDIAN / "app" / "Sentinela-Classificador.ps1"


def _carregar_gerador():
    spec = importlib.util.spec_from_file_location("build_rules", BUILD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gerador_e_rules_existem():
    for caminho in (RULES, BUILD, JS, PS):
        assert caminho.exists(), f"faltando: {caminho}"


def test_arquivos_gerados_batem_com_rules_json():
    """Regenera em memoria e compara byte a byte com o disco."""
    gerador = _carregar_gerador()
    gerado = gerador.gerar()  # {Path: conteudo}
    fora = []
    for caminho, conteudo in gerado.items():
        if caminho.read_text(encoding="utf-8") != conteudo:
            fora.append(caminho.name)
    assert not fora, (
        "arquivos fora de sincronia com rules.json: " + ", ".join(fora)
        + " -- rode: python apps/guardian/build_rules.py"
    )


def test_hash_embutido_bate_com_rules_json():
    """O sha256 do rules.json impresso no cabecalho de cada motor tem de ser o
    do rules.json atual. Pega drift mesmo sem rodar o gerador."""
    sha = hashlib.sha256(RULES.read_bytes()).hexdigest()
    for caminho in (JS, PS):
        texto = caminho.read_text(encoding="utf-8")
        assert sha in texto, (
            f"{caminho.name} nao traz o sha256 atual do rules.json ({sha[:12]}...): "
            "gerado a partir de um rules.json diferente ou editado a mao"
        )


@pytest.mark.parametrize("caminho", [JS, PS])
def test_cabecalho_avisa_que_e_gerado(caminho):
    """Quem abrir um arquivo gerado precisa ser avisado de que nao deve edita-lo."""
    cabecalho = caminho.read_text(encoding="utf-8")[:1200].upper()
    assert "ARQUIVO GERADO" in cabecalho and "NAO EDITE" in _sem_acento(cabecalho), (
        f"{caminho.name} nao avisa que e gerado a partir do rules.json"
    )


def _sem_acento(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
