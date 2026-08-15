"""Modulo Seguranca — corpus rotulado de deteccao de secrets (ESPEC secao 11,15).

No espirito do corpus do classificador: fixtures com secrets de FORMATO real
(construidos por concatenacao, para nao virarem literais que disparam scanners
de secret no repo) + armadilhas de falso positivo. Meta: 100% no corpus.

Rotulos: CONFIRMED / LIKELY / POSSIBLE / FALSE_POSITIVE.
"""
import pytest

from app.models.secintel import SecClassificacao
from app.services import secintel_secrets as secrets

C = SecClassificacao

# valores de formato real, montados por partes (nunca um literal unico)
_AWS = "AKIA" + "QZ3K7RT9WP2N6VBX"             # 4 + 16 chars, sem marca de exemplo
_AWS_EX = "AKIA" + "IOSFODNN7EXAMPLE"           # chave de EXEMPLO documentada (deve virar FP)
_GH = "ghp_" + "A" * 36
_STRIPE = "sk_live_" + "b" * 24
_SLACK = "xoxb-" + "1234567890" + "-abcdEFGH"
_PRIV = "-----BEGIN RSA PRIVATE KEY-----"
_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "a" * 20 + "." + "b" * 20
_CONN = "postgres://usuario:senhaforte123@db.interno:5432/prod"

# (texto, contexto, classificacao_esperada, deve_detectar)
CORPUS = [
    # ---- CONFIRMED ----
    (f"aws_key = {_AWS}", "config.py", C.confirmed, True),
    (f"token: {_GH}", "deploy.sh", C.confirmed, True),
    (f"STRIPE={_STRIPE}", ".env", C.confirmed, True),
    (f"slack_hook {_SLACK}", "notify.py", C.confirmed, True),
    (f"{_PRIV}\nMIIE...", "id_rsa", C.confirmed, True),
    # ---- LIKELY ----
    (f"Authorization: Bearer {_JWT}", "client.js", C.likely, True),
    (f"DATABASE_URL={_CONN}", "settings.py", C.likely, True),
    # ---- POSSIBLE (generico por entropia) ----
    ('client_secret = "Zx9Q2mLp7Vt3Wk8Nb1Rc4Yd6Fg0Hj5"', "app.py", C.possible, True),
    # ---- FALSE_POSITIVE: marcas de exemplo ----
    (f"aws_key = {_AWS}  # EXAMPLE, nao usar", "config.py", C.false_positive, True),
    (f"aws_key = {_AWS_EX}", "config.py", C.false_positive, True),  # chave de exemplo conhecida
    ('api_key = "CHANGEME_Zx9Q2mLp7Vt3Wk8Nb1Rc4Yd"', "app.py", C.false_positive, True),
    (f"STRIPE={_STRIPE}", "docs/exemplo.md", C.false_positive, True),
    (f"token: {_GH}", "tests/fixtures/creds.txt", C.false_positive, True),
    # ---- FALSE_POSITIVE: nao e secret nenhum ----
    ("mensagem = 'ola, tudo bem com voce hoje amigo?'", "app.py", None, False),
    ("url = 'https://example.com/pagina/publica'", "app.py", None, False),
    ("hash_lockfile = 'e3b0c44298fc1c149afbf4c8996fb924'", "poetry.lock", None, False),
    ("versao = '1.2.3-alpha.build.20260101'", "setup.py", None, False),
]


@pytest.mark.parametrize("texto,contexto,esperado,deve", CORPUS,
                         ids=[f"caso-{i}" for i in range(len(CORPUS))])
def test_corpus_de_secrets(texto, contexto, esperado, deve):
    achados = secrets.detectar(texto, contexto=contexto)
    if not deve:
        # nada legitimo aqui: nenhum achado ATIVO (FP tolerado, mas nao ativo)
        ativos = [a for a in achados if a.classificacao != C.false_positive]
        assert ativos == [], f"falso positivo em {contexto!r}: {[a.tipo_exposicao for a in ativos]}"
        return
    assert achados, f"nao detectou nada em {contexto!r}"
    classes = {a.classificacao for a in achados}
    assert esperado in classes, f"esperava {esperado} em {contexto!r}, veio {classes}"


def test_valor_completo_nunca_no_achado():
    """Propriedade: o valor bruto do secret nunca aparece no resultado."""
    achados = secrets.detectar(f"key={_AWS}", "config.py")
    assert achados
    for a in achados:
        assert _AWS not in a.indicador_mascarado
        assert _AWS not in a.evidencia_resumo
        assert _AWS not in (a.motivo_fp or "")
        # mas o prefixo identificador aparece, para o humano reconhecer
        assert a.indicador_mascarado.startswith("AKIA")


def test_corpus_100_por_cento():
    """Rede de seguranca agregada: todo o corpus classifica certo."""
    erros = []
    for i, (texto, contexto, esperado, deve) in enumerate(CORPUS):
        achados = secrets.detectar(texto, contexto=contexto)
        if not deve:
            if [a for a in achados if a.classificacao != C.false_positive]:
                erros.append(i)
        else:
            if esperado not in {a.classificacao for a in achados}:
                erros.append(i)
    assert not erros, f"casos errados no corpus: {erros}"
