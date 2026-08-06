"""Testes que fecham os achados da auditoria de seguranca.

Cada teste aqui existe porque uma auditoria independente encontrou o problema
no codigo real. Nome do achado no comentario de cada bloco, para que ninguem
"limpe" um destes sem entender o que estava errado.
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[4]
CRM = RAIZ / "apps" / "crm"


# ------------------------------------------------------- A1: chave de cifra


def test_a1_env_example_e_instalador_preveem_chave_de_cifra():
    """A1 — o instalador gerava APP_SECRET_KEY e esquecia FIELD_ENCRYPTION_KEY.

    Resultado: .env com chave vazia, `encrypt()` levantando RuntimeError, e a
    PRIMEIRA busca da crianca virando 500 — com o painel sem receber evento
    nenhum. O E2E nao pegava porque o ambiente de teste define a chave.
    """
    exemplo = (CRM / "backend" / ".env.example").read_text(encoding="utf-8")
    assert "FIELD_ENCRYPTION_KEY=" in exemplo

    instalador = (CRM / "INSTALAR.bat").read_text(encoding="utf-8")
    assert "FIELD_ENCRYPTION_KEY" in instalador, "instalador nao grava a chave de cifra"
    assert "Fernet.generate_key" in instalador, "instalador nao gera chave de verdade"


def test_a1_startup_sem_chave_falha_com_mensagem_clara(monkeypatch):
    """Sem a chave o app deve recusar SUBIR, nao falhar no primeiro evento."""
    from app.core import config as config_mod
    from app.main import _exigir_chave_de_cifra

    config_mod.get_settings.cache_clear()
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "")
    try:
        with pytest.raises(RuntimeError) as erro:
            _exigir_chave_de_cifra()
        mensagem = str(erro.value)
        assert "FIELD_ENCRYPTION_KEY" in mensagem
        assert "Fernet.generate_key" in mensagem, "erro deve dizer COMO gerar a chave"
    finally:
        config_mod.get_settings.cache_clear()


def test_a1_com_chave_a_ingestao_funciona_ponta_a_ponta(auth_client):
    token = auth_client.get("/api/v1/sentinela/config").json()["token_ingestao"]
    r = auth_client.post(
        "/api/v1/sentinela/eventos",
        json={"eventos": [{"busca": "jogo do tigrinho", "bloqueado": True, "tema": "Apostas"}]},
        headers={"X-Sentinela-Token": token},
    )
    assert r.status_code == 201, r.text
    itens = auth_client.get("/api/v1/sentinela/eventos").json()["items"]
    assert itens[0]["busca"] == "jogo do tigrinho"


# ------------------------------------------------------------ A2: bind de rede


def test_a2_launchers_nao_expoem_a_rede_por_padrao():
    """A2 — tudo subia em 0.0.0.0 "para o celular acessar", deixando o painel
    parental (com o historico decifrado de uma crianca) alcancavel por qualquer
    aparelho da Wi-Fi. Loopback e o padrao; LAN so com opt-in explicito."""
    alvos = [
        RAIZ / "INICIAR.bat",
        CRM / "INICIAR.bat",
        CRM / "backend" / "_run_server.cmd",
        CRM / "backend" / "desktop.py",
    ]
    for alvo in alvos:
        texto = alvo.read_text(encoding="utf-8", errors="replace")
        assert "SENTINELA_BIND_LAN" in texto, f"{alvo.name} sem opt-in documentado"
        linhas = texto.splitlines()
        for i, linha in enumerate(linhas):
            if "0.0.0.0" not in linha:
                continue
            # Toda mencao a 0.0.0.0 precisa estar sob o opt-in: ou na propria
            # linha, ou nas 3 anteriores (o `if` que abre o bloco), ou em
            # comentario/docstring.
            janela = " ".join(linhas[max(0, i - 3): i + 1]).lower()
            contexto = linha.strip().lower()
            assert (
                "sentinela_bind_lan" in janela
                or contexto.startswith("rem")
                or contexto.startswith("#")
                or contexto.startswith('"""')
                or "host_lan =" in contexto
            ), f"{alvo.name}: bind aberto sem opt-in -> {linha.strip()}"


def test_a2_desktop_usa_loopback_sem_variavel(monkeypatch):
    import importlib

    monkeypatch.delenv("SENTINELA_BIND_LAN", raising=False)
    desktop = importlib.import_module("desktop") if False else None  # pywebview nao instalado no CI
    # Sem importar o modulo (depende de pywebview), verifica a regra no fonte.
    fonte = (CRM / "backend" / "desktop.py").read_text(encoding="utf-8")
    assert 'os.environ.get("SENTINELA_BIND_LAN") == "1"' in fonte
    assert "host=bind_host()" in fonte
    assert desktop is None


# --------------------------------------------------------- A3: credencial demo


def test_a3_bootstrap_nao_cria_conta_demo_fora_de_dev(monkeypatch, capsys):
    """A3 — demo@visiquost.app/demo1234 era criada em TODA instalacao. Com o
    painel exposto (A2), era uma credencial publica para o historico de
    navegacao de uma crianca."""
    from app.core import config as config_mod

    config_mod.get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    try:
        import importlib
        import sys

        sys.path.insert(0, str(CRM / "backend"))
        bootstrap = importlib.import_module("scripts.bootstrap")
        importlib.reload(bootstrap)
        assert bootstrap.main() == 0
        saida = capsys.readouterr().out
        assert "NAO criada" in saida
    finally:
        config_mod.get_settings.cache_clear()


def test_a3_env_example_instala_como_producao():
    exemplo = (CRM / "backend" / ".env.example").read_text(encoding="utf-8")
    assert "APP_ENV=prod" in exemplo, "instalacao nao pode nascer em modo dev"


def test_a3_spa_sabe_se_e_primeiro_acesso(client):
    r = client.get("/api/v1/auth/estado-inicial")
    assert r.status_code == 200
    dados = r.json()
    assert dados["tem_usuarios"] is False
    assert dados["demo_disponivel"] is False


def test_a3_estado_inicial_reflete_conta_criada(auth_client):
    dados = auth_client.get("/api/v1/auth/estado-inicial").json()
    assert dados["tem_usuarios"] is True


# --------------------------------------------------------------- A4/A5: config


def test_a4_env_example_sem_resquicio_de_llm_na_nuvem():
    for caminho in [CRM / "backend" / ".env.example", CRM / ".env.example"]:
        texto = caminho.read_text(encoding="utf-8")
        assert "ANTHROPIC" not in texto.upper(), f"{caminho.name} anuncia API de nuvem"


def test_a5_cors_default_e_so_loopback():
    from app.core.config import CORS_PADRAO, Settings

    for origem in Settings().cors_origins:
        assert re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origem), origem
    assert set(CORS_PADRAO) == {"http://127.0.0.1:8000", "http://localhost:8000"}


def test_a5_cors_vazio_cai_no_default_loopback():
    from app.core.config import Settings

    s = Settings(CORS_ORIGINS="  , ,")
    assert all("localhost:8000" in o or "127.0.0.1:8000" in o for o in s.cors_origins)


# ------------------------------------------------------------- A6: lockout PIN


def _define_pin(cliente, pin="2026"):
    assert cliente.post("/api/v1/sentinela/config/pin", json={"pin": pin}).status_code == 200


def test_a6_pin_bloqueia_apos_sequencia_de_erros(auth_client):
    """A6 — nao havia contador nem espera: 10.000 combinacoes caiam em segundos.
    Registrar a tentativa nao e defesa contra a tentativa."""
    _define_pin(auth_client)
    for _ in range(5):
        r = auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "0000"})
        assert r.status_code == 200 and r.json()["ok"] is False

    bloqueado = auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "0000"})
    assert bloqueado.status_code == 429
    assert "Retry-After" in bloqueado.headers

    # e nem o PIN certo passa durante o bloqueio: nao existe atalho pelo acerto
    assert auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "2026"}).status_code == 429


def test_a6_bloqueio_expira_e_acerto_zera_o_contador(auth_client):
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import sentinela_service as svc

    _define_pin(auth_client)
    for _ in range(5):
        auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "0000"})
    assert auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "2026"}).status_code == 429

    # janela vencida
    with Session(engine) as s:
        cfg = svc.get_config(s)
        cfg.pin_bloqueado_ate = datetime.now(timezone.utc) - timedelta(seconds=1)
        s.add(cfg)
        s.commit()

    ok = auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "2026"})
    assert ok.status_code == 200 and ok.json()["ok"] is True

    with Session(engine) as s:
        assert svc.get_config(s).pin_falhas == 0


def test_a6_troca_de_pin_tambem_conta_para_o_lockout(auth_client):
    """Sem isso a rota de troca viraria o oraculo de forca bruta."""
    _define_pin(auth_client)
    for _ in range(5):
        r = auth_client.post("/api/v1/sentinela/config/pin", json={"pin": "1111", "pin_atual": "9999"})
        assert r.status_code == 403
    r = auth_client.post("/api/v1/sentinela/config/pin", json={"pin": "1111", "pin_atual": "9999"})
    assert r.status_code == 429


def test_a6_rota_de_pin_tem_limite_de_taxa():
    from app.core.middleware import default_rate_limits

    prefixos = [p for p, _ in default_rate_limits()]
    assert "/api/v1/sentinela/config/pin" in prefixos


# ------------------------------------------------- A8: serie diaria sem teto


def test_a8_serie_diaria_bate_com_os_totais_acima_do_teto_antigo(auth_client):
    """A8 — a serie carregava no maximo 5000 eventos em Python enquanto os
    cartoes usavam COUNT. Passando do teto, grafico e cartoes discordavam."""
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import sentinela_service as svc

    agora = datetime.now(timezone.utc)
    with Session(engine) as s:
        for i in range(5200):
            svc.registrar_evento(
                s,
                busca=f"busca {i}",
                bloqueado=(i % 4 == 0),
                ocorrido_em=agora - timedelta(minutes=i % 60),
                commit=False,
            )
        s.commit()

    r = auth_client.get("/api/v1/sentinela/resumo?dias=7").json()
    assert r["total"] == 5200
    assert sum(d["total"] for d in r["por_dia"]) == r["total"]
    assert sum(d["bloqueados"] for d in r["por_dia"]) == r["bloqueados"]


# --------------------------------------------- A11: retencao sem ingestao


def test_a11_retencao_roda_sem_precisar_de_ingestao(auth_client):
    """A11 — a purga so acontecia ao fim de POST /eventos. Instalacao ociosa
    (crianca de ferias, PC desligado) nunca purgava."""
    from sqlmodel import Session

    from app.db.session import engine
    from app.services import retencao_scheduler
    from app.services import sentinela_service as svc

    with Session(engine) as s:
        svc.registrar_evento(s, busca="antigo", ocorrido_em=datetime.now(timezone.utc) - timedelta(days=200))
        svc.registrar_evento(s, busca="recente")
    assert auth_client.get("/api/v1/sentinela/eventos").json()["total"] == 2

    assert retencao_scheduler.aplicar_agora() == 1
    restantes = auth_client.get("/api/v1/sentinela/eventos").json()
    assert restantes["total"] == 1
    assert restantes["items"][0]["busca"] == "recente"


# ------------------------------------- A12: uma validacao para as duas portas


def test_a12_import_e_ingestao_compartilham_a_validacao(auth_client):
    """A12 — o caminho vivo exigia busca nao-vazia; o import so checava
    truthiness e truncava por conta propria."""
    from app.services import sentinela_service as svc

    with pytest.raises(ValueError):
        svc.normalizar_evento(busca="   ")

    assert svc.normalizar_evento(busca="x" * 900)["busca"] == "x" * svc.MAX_BUSCA

    linhas = "\n".join([
        '{"busca":"tigrinho","bloqueado":true}',
        '{"busca":"   "}',
        '{"busca":""}',
        '{"nao":"tem busca"}',
    ])
    r = auth_client.post("/api/v1/sentinela/importar", json={"conteudo": linhas}).json()
    assert r == {"importados": 1, "ignorados": 3}


# ---------------------------------------------------------- A9: cores em token


def test_a9_css_do_app_nao_tem_cor_de_marca_cravada():
    css = (CRM / "frontend" / "assets" / "app.css").read_text(encoding="utf-8")
    hexes = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,6}\b", css)}
    permitidos = {"#000", "#fff"}  # preto/branco puros em sombra e contraste
    assert hexes <= permitidos, f"cores fora dos tokens: {sorted(hexes - permitidos)}"
