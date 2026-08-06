"""Modulo Sentinela: ingestao, painel, PIN, retencao e import legado."""
from datetime import datetime, timedelta, timezone


def _token(auth_client) -> str:
    r = auth_client.get("/api/v1/sentinela/config")
    assert r.status_code == 200, r.text
    return r.json()["token_ingestao"]


def _ingerir(client, token, **campos):
    evento = {"busca": "teste", "origem": "google", "bloqueado": False}
    evento.update(campos)
    return client.post(
        "/api/v1/sentinela/eventos",
        json={"eventos": [evento]},
        headers={"X-Sentinela-Token": token},
    )


# --------------------------------------------------------------- ingestao


def test_ingestao_exige_token(auth_client):
    r = auth_client.post("/api/v1/sentinela/eventos", json={"eventos": [{"busca": "x"}]})
    assert r.status_code == 401


def test_ingestao_recusa_token_errado(auth_client):
    r = _ingerir(auth_client, "token-de-mentira")
    assert r.status_code == 401


def test_ingestao_aceita_token_valido_e_aparece_no_painel(auth_client):
    token = _token(auth_client)
    r = _ingerir(auth_client, token, busca="filhotes de golden", bloqueado=False)
    assert r.status_code == 201, r.text
    assert r.json()["registrados"] == 1

    lista = auth_client.get("/api/v1/sentinela/eventos").json()
    assert lista["total"] == 1
    assert lista["items"][0]["busca"] == "filhotes de golden"
    assert lista["items"][0]["origem"] == "google"


def test_busca_fica_cifrada_no_banco(auth_client):
    from sqlmodel import Session, select
    from app.db.session import engine
    from app.models import SentinelaEvent

    token = _token(auth_client)
    _ingerir(auth_client, token, busca="segredo-do-registro")
    with Session(engine) as s:
        ev = s.exec(select(SentinelaEvent)).first()
    assert ev is not None
    assert "segredo-do-registro" not in ev.busca_enc


def test_lote_registra_todos(auth_client):
    token = _token(auth_client)
    r = auth_client.post(
        "/api/v1/sentinela/eventos",
        json={"eventos": [{"busca": f"busca {i}"} for i in range(5)]},
        headers={"X-Sentinela-Token": token},
    )
    assert r.status_code == 201
    assert r.json()["registrados"] == 5
    assert auth_client.get("/api/v1/sentinela/eventos").json()["total"] == 5


def test_lote_vazio_e_rejeitado(auth_client):
    token = _token(auth_client)
    r = auth_client.post(
        "/api/v1/sentinela/eventos", json={"eventos": []}, headers={"X-Sentinela-Token": token}
    )
    assert r.status_code == 422


def test_confianca_e_limitada_entre_0_e_1(auth_client):
    token = _token(auth_client)
    _ingerir(auth_client, token, busca="fora de escala", confianca=9.5)
    item = auth_client.get("/api/v1/sentinela/eventos").json()["items"][0]
    assert item["confianca"] == 1.0


def test_rotacionar_token_invalida_o_anterior(auth_client):
    antigo = _token(auth_client)
    novo = auth_client.post("/api/v1/sentinela/token/rotacionar").json()["token_ingestao"]
    assert novo != antigo
    assert _ingerir(auth_client, antigo).status_code == 401
    assert _ingerir(auth_client, novo).status_code == 201


# --------------------------------------------------------------- painel


def test_painel_exige_login(client):
    assert client.get("/api/v1/sentinela/eventos").status_code == 401
    assert client.get("/api/v1/sentinela/resumo").status_code == 401
    assert client.get("/api/v1/sentinela/config").status_code == 401


def test_filtro_somente_bloqueados(auth_client):
    token = _token(auth_client)
    _ingerir(auth_client, token, busca="livre", bloqueado=False)
    _ingerir(auth_client, token, busca="barrada", bloqueado=True, tema="Conteudo adulto")
    todos = auth_client.get("/api/v1/sentinela/eventos").json()
    barrados = auth_client.get("/api/v1/sentinela/eventos?somente_bloqueados=true").json()
    assert todos["total"] == 2
    assert barrados["total"] == 1
    assert barrados["items"][0]["busca"] == "barrada"


def test_filtro_por_dispositivo(auth_client):
    token = _token(auth_client)
    _ingerir(auth_client, token, busca="a", dispositivo="pc-sala")
    _ingerir(auth_client, token, busca="b", dispositivo="tablet")
    r = auth_client.get("/api/v1/sentinela/eventos?dispositivo=tablet").json()
    assert r["total"] == 1
    assert r["items"][0]["busca"] == "b"


def test_paginacao(auth_client):
    token = _token(auth_client)
    for i in range(7):
        _ingerir(auth_client, token, busca=f"b{i}")
    p = auth_client.get("/api/v1/sentinela/eventos?limite=3&offset=3").json()
    assert p["total"] == 7
    assert len(p["items"]) == 3
    assert p["offset"] == 3


def test_resumo_conta_temas_e_serie_diaria(auth_client):
    token = _token(auth_client)
    _ingerir(auth_client, token, busca="ok", bloqueado=False)
    _ingerir(auth_client, token, busca="ruim 1", bloqueado=True, tema="Apostas")
    _ingerir(auth_client, token, busca="ruim 2", bloqueado=True, tema="Apostas")
    _ingerir(auth_client, token, busca="ruim 3", bloqueado=True, tema="Drogas")

    r = auth_client.get("/api/v1/sentinela/resumo?dias=7").json()
    assert r["total"] == 4
    assert r["bloqueados"] == 3
    assert r["liberados"] == 1
    assert r["temas"][0] == {"tema": "Apostas", "vezes": 2}
    assert len(r["por_dia"]) == 7
    assert r["por_dia"][-1]["total"] == 4  # tudo aconteceu hoje
    assert r["ultimo_evento"] is not None


def test_resumo_vazio_nao_quebra(auth_client):
    r = auth_client.get("/api/v1/sentinela/resumo").json()
    assert r["total"] == 0 and r["temas"] == [] and r["ultimo_evento"] is None


# --------------------------------------------------------------- config e PIN


def test_config_default_e_edicao(auth_client):
    cfg = auth_client.get("/api/v1/sentinela/config").json()
    assert cfg["ativo"] is True
    assert cfg["sensibilidade"] == "media"
    assert cfg["pin_definido"] is False

    r = auth_client.patch("/api/v1/sentinela/config", json={"sensibilidade": "alta", "ativo": False})
    assert r.status_code == 200
    assert r.json()["sensibilidade"] == "alta"
    assert r.json()["ativo"] is False


def test_sensibilidade_invalida_rejeitada(auth_client):
    r = auth_client.patch("/api/v1/sentinela/config", json={"sensibilidade": "turbo"})
    assert r.status_code == 400


def test_pin_define_verifica_e_exige_atual_para_trocar(auth_client):
    assert auth_client.post("/api/v1/sentinela/config/pin", json={"pin": "2026"}).status_code == 200
    assert auth_client.get("/api/v1/sentinela/config").json()["pin_definido"] is True
    assert auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "2026"}).json()["ok"] is True
    assert auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "0000"}).json()["ok"] is False

    # trocar sem o PIN atual e barrado
    assert auth_client.post("/api/v1/sentinela/config/pin", json={"pin": "1234"}).status_code == 403
    assert auth_client.post(
        "/api/v1/sentinela/config/pin", json={"pin": "1234", "pin_atual": "2026"}
    ).status_code == 200
    assert auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "1234"}).json()["ok"] is True


def test_pin_nao_numerico_rejeitado(auth_client):
    assert auth_client.post("/api/v1/sentinela/config/pin", json={"pin": "abcd"}).status_code == 400


def test_pin_errado_vira_evento_de_supervisao(auth_client):
    auth_client.post("/api/v1/sentinela/config/pin", json={"pin": "2026"})
    auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "9999"})
    eventos = auth_client.get("/api/v1/sentinela/eventos?somente_bloqueados=true").json()
    assert eventos["total"] == 1
    assert eventos["items"][0]["tema"] == "Burlar protecao"
    assert eventos["items"][0]["origem"] == "painel"


def test_verificar_pin_sem_pin_definido(auth_client):
    assert auth_client.post("/api/v1/sentinela/config/pin/verificar", json={"pin": "0000"}).status_code == 400


# --------------------------------------------------------------- import legado


def test_importa_jsonl_do_app_powershell(auth_client):
    linhas = "\n".join([
        '{"hora":"2026-08-01T10:00:00Z","busca":"tigrinho","origem":"extensao","tema":"Apostas","confianca":1.0,"bloqueado":true}',
        '{"hora":"2026-08-01T10:05:00Z","busca":"dever de casa","origem":"extensao","tema":null,"confianca":0,"bloqueado":false}',
        "linha quebrada {",
        "",
        '{"sem":"busca"}',
    ])
    r = auth_client.post("/api/v1/sentinela/importar", json={"conteudo": linhas})
    assert r.status_code == 200, r.text
    assert r.json() == {"importados": 2, "ignorados": 2}

    itens = auth_client.get("/api/v1/sentinela/eventos").json()["items"]
    assert {i["busca"] for i in itens} == {"tigrinho", "dever de casa"}


def test_importar_sem_conteudo_falha(auth_client):
    assert auth_client.post("/api/v1/sentinela/importar", json={}).status_code == 400


# --------------------------------------------------------------- retencao


def test_retencao_apaga_eventos_antigos(auth_client):
    from sqlmodel import Session
    from app.db.session import engine
    from app.services import sentinela_service as svc

    token = _token(auth_client)
    _ingerir(auth_client, token, busca="recente")
    with Session(engine) as s:
        svc.registrar_evento(
            s, busca="antigo", ocorrido_em=datetime.now(timezone.utc) - timedelta(days=200)
        )
    assert auth_client.get("/api/v1/sentinela/eventos").json()["total"] == 2

    # a proxima ingestao aplica a janela de retencao (90 dias por padrao)
    r = _ingerir(auth_client, token, busca="gatilho")
    assert r.json()["expirados"] == 1
    restantes = {i["busca"] for i in auth_client.get("/api/v1/sentinela/eventos").json()["items"]}
    assert restantes == {"recente", "gatilho"}


def test_retencao_zero_guarda_para_sempre(auth_client):
    from sqlmodel import Session
    from app.db.session import engine
    from app.services import sentinela_service as svc

    auth_client.patch("/api/v1/sentinela/config", json={"retencao_dias": 0})
    with Session(engine) as s:
        svc.registrar_evento(
            s, busca="ancestral", ocorrido_em=datetime.now(timezone.utc) - timedelta(days=5000)
        )
    token = _token(auth_client)
    assert _ingerir(auth_client, token, busca="novo").json()["expirados"] == 0
    assert auth_client.get("/api/v1/sentinela/eventos").json()["total"] == 2
