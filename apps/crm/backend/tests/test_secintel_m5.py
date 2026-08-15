"""Modulo Seguranca — M5: monitoramento continuo (schedulers), dedupe, higiene.

Testa os passos sincronos dos laços isoladamente (o agendamento em si segue o
padrao ja coberto de retencao_scheduler). Confirma: correlacao periodica nao
duplica; exposicao periodica nao toca fonte desligada; higiene aplica retencoes.
"""
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.db.session import engine
from app.models import SecEvento, SecIncidente, Workspace
from app.models.secintel import (
    SecEventoOrigem,
    SecIncidenteEstado,
)
from app.services import secintel_scheduler as sched
from app.services import secintel_service as svc


def _ws(auth_client):
    with Session(engine) as s:
        return s.exec(select(Workspace)).first().id


def _seq_takeover(ws_id, usuario="alvo@x.com"):
    base = datetime.now(timezone.utc)
    with Session(engine) as s:
        for i in range(5):
            s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                            tipo="login_falha", ts=base + timedelta(seconds=i * 5),
                            ip="9.9.9.9", usuario=usuario))
        s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                        tipo="login_ok", ts=base + timedelta(minutes=1), ip="7.7.7.7", usuario=usuario))
        s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                        tipo="troca_senha", ts=base + timedelta(minutes=2), usuario=usuario))
        s.commit()


def test_ciclo_correlacao_agora_cria_e_nao_duplica(auth_client):
    ws_id = _ws(auth_client)
    _seq_takeover(ws_id)

    n1 = sched.ciclo_correlacao_agora()
    n2 = sched.ciclo_correlacao_agora()
    assert n1 >= 1 and n2 >= 1

    with Session(engine) as s:
        incs = list(s.exec(select(SecIncidente).where(
            SecIncidente.workspace_id == ws_id,
            SecIncidente.cenario == "account_takeover",
            SecIncidente.deleted_at.is_(None),
        )))
    assert len(incs) == 1  # dois ciclos, um so incidente
    # correcao pos-revisao: mesmo conjunto de eventos nos dois ciclos ->
    # ocorrencias fica em 1 (nada de reincidencia fantasma a cada 5 min)
    assert incs[0].ocorrencias == 1


def test_ciclo_exposicao_agora_nao_toca_fonte_desligada(auth_client):
    """Nenhuma fonte ligada: o ciclo monta os transportes reais, mas nunca os
    chama (o runner barra fontes desligadas). Passamos transportes que EXPLODEM
    para provar que nao sao chamados."""
    ws_id = _ws(auth_client)
    auth_client.post("/api/v1/seguranca/ativos", json={"tipo": "email", "identificador": "a@b.com"})

    def bomba(*a, **k):
        raise AssertionError("rede chamada sem fonte habilitada!")

    total = sched.ciclo_exposicao_agora(transportes={"http_url": bomba, "repo_files": bomba})
    assert total == 0


def test_ciclo_higiene_purga_evento_velho(auth_client):
    ws_id = _ws(auth_client)
    velho = datetime.now(timezone.utc) - timedelta(days=40)
    with Session(engine) as s:
        s.add(SecEvento(workspace_id=ws_id, origem=SecEventoOrigem.painel_auth,
                        tipo="login_falha", ts=velho, ip="1.1.1.1", usuario="x@x.com"))
        s.commit()

    contadores = sched.ciclo_higiene_agora()
    assert contadores["eventos"] >= 1

    with Session(engine) as s:
        vivos = list(s.exec(select(SecEvento).where(
            SecEvento.workspace_id == ws_id, SecEvento.deleted_at.is_(None),
        )))
    assert all(e.ts.replace(tzinfo=timezone.utc) >= datetime.now(timezone.utc) - timedelta(days=30)
               for e in vivos)


def test_ciclo_higiene_fecha_incidente_recuperado_antigo(auth_client):
    ws_id = _ws(auth_client)
    _seq_takeover(ws_id, usuario="rec@x.com")
    sched.ciclo_correlacao_agora()
    with Session(engine) as s:
        inc = s.exec(select(SecIncidente).where(SecIncidente.workspace_id == ws_id)).first()
        inc.estado = SecIncidenteEstado.recuperado
        inc.ultimo_visto = datetime.now(timezone.utc) - timedelta(days=45)
        s.add(inc)
        s.commit()
        iid = inc.id

    contadores = sched.ciclo_higiene_agora()
    assert contadores["fechados"] >= 1
    with Session(engine) as s:
        assert s.get(SecIncidente, iid).estado == SecIncidenteEstado.fechado
