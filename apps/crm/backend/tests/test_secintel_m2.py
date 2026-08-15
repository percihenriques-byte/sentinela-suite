"""Modulo Seguranca — M2: eventos locais, regras R1-R8, correlacao, incidentes.

Sem rede. Cobre a escada EVENTO -> INDICADOR -> SUSPEITA -> INCIDENTE e a
sequencia de referencia da Fase 5 (ESPEC secao 8): muitas falhas de login +
login OK de IP novo + troca de credencial -> 1 incidente HIGH com linha do
tempo. Dedupe: reincidencia atualiza, nunca duplica.
"""
from datetime import datetime, timedelta, timezone

from app.models.secintel import SecEvento, SecEventoOrigem
from app.services import secintel_regras as regras


def _ev(tipo, ts, ip=None, usuario=None, sessao=None):
    return SecEvento(
        workspace_id=None, origem=SecEventoOrigem.painel_auth, tipo=tipo,
        ts=ts, ip=ip, usuario=usuario, sessao=sessao,
    )


def _agora():
    return datetime.now(timezone.utc)


# ---- regras puras ----

def test_r1_brute_force_dispara_com_5_falhas():
    base = _agora()
    evs = [_ev("login_falha", base + timedelta(seconds=i * 10), ip="1.2.3.4") for i in range(5)]
    hits = regras.r1_brute_force(evs)
    assert len(hits) == 1 and hits[0].cenario == "brute_force"


def test_r1_nao_dispara_com_4_falhas():
    base = _agora()
    evs = [_ev("login_falha", base + timedelta(seconds=i * 10), ip="1.2.3.4") for i in range(4)]
    assert regras.r1_brute_force(evs) == []


def test_r1_respeita_janela_de_10min():
    base = _agora()
    # 5 falhas espalhadas por 20 min nao sao rajada
    evs = [_ev("login_falha", base + timedelta(minutes=i * 5), ip="1.2.3.4") for i in range(5)]
    assert regras.r1_brute_force(evs) == []


def test_r3_pin_probing():
    base = _agora()
    evs = [_ev("pin_falha", base + timedelta(seconds=i * 30)) for i in range(3)]
    assert len(regras.r3_pin_probing(evs)) == 1


def test_sequencia_de_referencia_gera_incidente_high():
    """Fase 5: falhas + login OK de IP novo + troca de credencial."""
    base = _agora()
    evs = [_ev("login_falha", base + timedelta(seconds=i * 10), ip="9.9.9.9", usuario="mae@x.com")
           for i in range(5)]
    evs.append(_ev("login_ok", base + timedelta(minutes=2), ip="5.5.5.5", usuario="mae@x.com"))
    evs.append(_ev("troca_senha", base + timedelta(minutes=3), usuario="mae@x.com"))
    hits = regras.avaliar(evs)
    incidentes = [h for h in hits if h.nivel == "incidente"]
    assert len(incidentes) == 1
    h = incidentes[0]
    assert h.cenario == "account_takeover" and h.severidade == "HIGH"


# ---- fluxo com banco / correlacao ----

def _inserir_eventos(engine, workspace_id, specs):
    """specs: lista de (tipo, offset_seg, ip, usuario). Insere com ts controlado."""
    from sqlmodel import Session

    base = _agora()
    with Session(engine) as s:
        for tipo, off, ip, usuario in specs:
            s.add(SecEvento(
                workspace_id=workspace_id, origem=SecEventoOrigem.painel_auth,
                tipo=tipo, ts=base + timedelta(seconds=off), ip=ip, usuario=usuario,
            ))
        s.commit()


def _ws_id(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import Workspace

    with Session(engine) as s:
        return s.exec(select(Workspace)).first().id


def test_correlacao_cria_incidente_e_linha_do_tempo(auth_client):
    from app.db.session import engine

    ws_id = _ws_id(auth_client)
    specs = [("login_falha", i * 10, "9.9.9.9", "mae@x.com") for i in range(5)]
    specs += [("login_ok", 200, "5.5.5.5", "mae@x.com"), ("troca_senha", 300, None, "mae@x.com")]
    _inserir_eventos(engine, ws_id, specs)

    r = auth_client.post("/api/v1/seguranca/varreduras/correlacao")
    assert r.status_code == 200, r.text
    incs = r.json()
    assert len(incs) == 1
    inc = incs[0]
    assert inc["cenario"] == "account_takeover" and inc["severidade"] == "HIGH"

    det = auth_client.get(f"/api/v1/seguranca/incidentes/{inc['id']}").json()
    assert len(det["itens"]) >= 2   # linha do tempo com nota + eventos
    assert len(det["recomendacoes"]) >= 3
    assert any(rec["bloco"] == "contencao" for rec in det["recomendacoes"])


def test_correlacao_nao_duplica_incidente(auth_client):
    from app.db.session import engine

    ws_id = _ws_id(auth_client)
    specs = [("login_falha", i * 10, "9.9.9.9", "pai@x.com") for i in range(5)]
    specs += [("login_ok", 200, "5.5.5.5", "pai@x.com"), ("troca_senha", 300, None, "pai@x.com")]
    _inserir_eventos(engine, ws_id, specs)

    auth_client.post("/api/v1/seguranca/varreduras/correlacao")
    auth_client.post("/api/v1/seguranca/varreduras/correlacao")
    incs = auth_client.get("/api/v1/seguranca/incidentes").json()
    do_cenario = [i for i in incs if i["cenario"] == "account_takeover"]
    assert len(do_cenario) == 1, "reincidencia deve atualizar, nao duplicar"
    # correcao pos-revisao: sem evento NOVO entre os ciclos, ocorrencias NAO
    # incrementa (o mesmo conjunto de eventos nao e reincidencia)
    assert do_cenario[0]["ocorrencias"] == 1


def test_transicao_de_estado_valida_e_invalida(auth_client):
    from app.db.session import engine

    ws_id = _ws_id(auth_client)
    specs = [("login_falha", i * 10, "9.9.9.9", "av@x.com") for i in range(5)]
    specs += [("login_ok", 200, "5.5.5.5", "av@x.com"), ("troca_senha", 300, None, "av@x.com")]
    _inserir_eventos(engine, ws_id, specs)
    inc = auth_client.post("/api/v1/seguranca/varreduras/correlacao").json()[0]
    iid = inc["id"]

    # detectado -> triagem: ok
    assert auth_client.patch(f"/api/v1/seguranca/incidentes/{iid}/estado",
                             json={"estado": "triagem"}).status_code == 200
    # triagem -> recuperado: pula degrau -> 422
    assert auth_client.patch(f"/api/v1/seguranca/incidentes/{iid}/estado",
                             json={"estado": "recuperado"}).status_code == 422
    # triagem -> contido: ok
    assert auth_client.patch(f"/api/v1/seguranca/incidentes/{iid}/estado",
                             json={"estado": "contido"}).status_code == 200


def test_marcar_recomendacao(auth_client):
    from app.db.session import engine

    ws_id = _ws_id(auth_client)
    specs = [("login_falha", i * 10, "9.9.9.9", "ti@x.com") for i in range(5)]
    specs += [("login_ok", 200, "5.5.5.5", "ti@x.com"), ("troca_senha", 300, None, "ti@x.com")]
    _inserir_eventos(engine, ws_id, specs)
    iid = auth_client.post("/api/v1/seguranca/varreduras/correlacao").json()[0]["id"]

    r = auth_client.patch(f"/api/v1/seguranca/incidentes/{iid}/recomendacoes/0", json={"feito": True})
    assert r.status_code == 200
    assert r.json()["recomendacoes"][0]["feito"] is True


def test_evento_e_minimizado_por_allowlist(auth_client):
    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import SecEvento as EvModel
    from app.services import secintel_service as svc

    ws_id = _ws_id(auth_client)
    with Session(engine) as s:
        svc.registrar_evento(
            s, ws_id, SecEventoOrigem.painel_auth, "login_falha",
            ip="1.1.1.1", usuario="x@x.com",
            atributos={"user_agent_familia": "Chrome", "senha_digitada": "NAO_DEVE_GUARDAR"},
        )
        ev = s.exec(select(EvModel).where(EvModel.tipo == "login_falha")).first()
        assert "senha_digitada" not in (ev.atributos or "")
        assert "NAO_DEVE_GUARDAR" not in (ev.atributos or "")
        assert "user_agent_familia" in (ev.atributos or "")
