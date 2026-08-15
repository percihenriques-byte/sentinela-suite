"""Regras de deteccao e correlacao do modulo Seguranca (ESPEC secao 7-8).

Puro e testavel: recebe uma lista de eventos (SecEvento) de uma janela e
devolve "hits". Nao toca banco nem rede. A escada e EVENTO -> INDICADOR ->
SUSPEITA -> INCIDENTE, e nenhuma regra pula degrau sem evidencia.

Tipos de evento normalizados (produzidos por secintel_service.registrar_evento):
    login_falha, login_ok, pin_falha, token_invalido, troca_senha, troca_pin,
    rotacao_token, sessao_iniciada, token_criado
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Iterable


@dataclass
class Hit:
    cenario: str            # chave do threat model (ESPEC secao 13)
    nivel: str              # indicador | suspeita | incidente
    severidade: str         # INFO..CRITICAL (base; o score refina no M3)
    titulo: str
    resumo: str
    usuario: str | None     # entra no fingerprint do incidente
    chaves: set = field(default_factory=set)   # chaves de correlacao distintas
    evento_ids: list = field(default_factory=list)


def _janela(eventos, tipo, segundos):
    """Agrupa eventos de um tipo por bucket temporal deslizante simples:
    devolve, para cada evento-ancora, os eventos do mesmo tipo dentro de
    `segundos` antes dele. Usado pelas contagens de rajada."""
    ev = sorted([e for e in eventos if e.tipo == tipo], key=lambda e: e.ts)
    return ev


def _rajada(eventos, tipo, chave_fn, minimo, segundos):
    """Encontra uma rajada: >= `minimo` eventos de `tipo` compartilhando o valor
    de `chave_fn`, dentro de uma janela de `segundos`. Devolve (chave, [ev])."""
    ev = _janela(eventos, tipo, segundos)
    por_chave: dict = {}
    for e in ev:
        por_chave.setdefault(chave_fn(e), []).append(e)
    achados = []
    janela = timedelta(seconds=segundos)
    for chave, lst in por_chave.items():
        if chave is None:
            continue
        lst.sort(key=lambda e: e.ts)
        i = 0
        for j in range(len(lst)):
            while lst[j].ts - lst[i].ts > janela:
                i += 1
            if j - i + 1 >= minimo:
                achados.append((chave, lst[i : j + 1]))
                break
    return achados


# ---- regras individuais ---------------------------------------------------

def r1_brute_force(eventos) -> list[Hit]:
    hits = []
    for ip, lst in _rajada(eventos, "login_falha", lambda e: e.ip, 5, 600):
        hits.append(Hit(
            "brute_force", "indicador", "MEDIUM",
            "Tentativas repetidas de login",
            f"{len(lst)} falhas de login do mesmo IP em ate 10 min.",
            usuario=lst[-1].usuario, chaves={f"ip:{ip}"},
            evento_ids=[e.id for e in lst],
        ))
    return hits


def r2_spray(eventos) -> list[Hit]:
    hits = []
    for usuario, lst in _rajada(eventos, "login_falha", lambda e: e.usuario, 5, 600):
        ips = {e.ip for e in lst if e.ip}
        if len(ips) >= 3:
            hits.append(Hit(
                "brute_force", "indicador", "MEDIUM",
                "Falhas de login de varios IPs",
                f"{len(lst)} falhas para o mesmo usuario de {len(ips)} IPs distintos.",
                usuario=usuario, chaves={f"user:{usuario}"} | {f"ip:{ip}" for ip in ips},
                evento_ids=[e.id for e in lst],
            ))
    return hits


def r3_pin_probing(eventos) -> list[Hit]:
    hits = []
    for _, lst in _rajada(eventos, "pin_falha", lambda e: "pin", 3, 900):
        hits.append(Hit(
            "brute_force", "indicador", "MEDIUM",
            "Tentativas repetidas de PIN",
            f"{len(lst)} erros de PIN em ate 15 min.",
            usuario=None, chaves={"pin"}, evento_ids=[e.id for e in lst],
        ))
    return hits


def r4_ingest_probing(eventos) -> list[Hit]:
    hits = []
    for ip, lst in _rajada(eventos, "token_invalido", lambda e: e.ip or "sem-ip", 5, 600):
        hits.append(Hit(
            "brute_force", "indicador", "MEDIUM",
            "Sondagem do token de ingestao",
            f"{len(lst)} usos de token invalido em ate 10 min.",
            usuario=None, chaves={f"ip:{ip}"}, evento_ids=[e.id for e in lst],
        ))
    return hits


def r7_sessao_anomala(eventos) -> list[Hit]:
    """Sessoes simultaneas do mesmo usuario a partir de IPs distintos numa
    janela curta (10 min)."""
    hits = []
    inicios = sorted([e for e in eventos if e.tipo == "sessao_iniciada"], key=lambda e: e.ts)
    por_user: dict = {}
    for e in inicios:
        por_user.setdefault(e.usuario, []).append(e)
    for usuario, lst in por_user.items():
        if not usuario:
            continue
        for j in range(len(lst)):
            vizinhos = [e for e in lst if 0 <= (lst[j].ts - e.ts).total_seconds() <= 600]
            ips = {e.ip for e in vizinhos if e.ip}
            if len(ips) >= 2:
                hits.append(Hit(
                    "session_hijacking", "indicador", "MEDIUM",
                    "Sessoes simultaneas de IPs distintos",
                    f"Sessoes do mesmo usuario de {len(ips)} IPs em 10 min.",
                    usuario=usuario, chaves={f"user:{usuario}"} | {f"ip:{ip}" for ip in ips},
                    evento_ids=[e.id for e in vizinhos],
                ))
                break
    return hits


def r8_token_inesperado(eventos) -> list[Hit]:
    """Criacao de token sem uma sessao ativa recente do mesmo usuario (30 min)."""
    hits = []
    sessoes = [e for e in eventos if e.tipo == "sessao_iniciada"]
    for e in [e for e in eventos if e.tipo == "token_criado"]:
        recente = any(
            s.usuario == e.usuario and 0 <= (e.ts - s.ts).total_seconds() <= 1800
            for s in sessoes
        )
        if not recente:
            hits.append(Hit(
                "api_key_exposure", "suspeita", "MEDIUM",
                "Token criado fora de sessao ativa",
                "Um token foi criado sem sessao ativa recente do usuario.",
                usuario=e.usuario, chaves={f"user:{e.usuario}"}, evento_ids=[e.id],
            ))
    return hits


# ---- regras compostas (correlacao) ----------------------------------------

def _ultimo_ts(eventos, ids):
    ids = set(ids)
    ts = [e.ts for e in eventos if e.id in ids]
    return max(ts) if ts else None


def r5_r6_takeover(eventos, base_hits: list[Hit]) -> list[Hit]:
    """R5: rajada de falhas (R1|R2) seguida de login_ok de IP inedito -> SUSPEITA.
    R6: R5 + troca de credencial (senha|PIN|rotacao de token) -> INCIDENTE HIGH."""
    hits: list[Hit] = []
    rajadas = [h for h in base_hits if h.cenario == "brute_force"
               and h.titulo != "Tentativas repetidas de PIN"]
    if not rajadas:
        return hits

    logins_ok = sorted([e for e in eventos if e.tipo == "login_ok"], key=lambda e: e.ts)
    trocas = [e for e in eventos if e.tipo in ("troca_senha", "troca_pin", "rotacao_token")]

    for raj in rajadas:
        t_raj = _ultimo_ts(eventos, raj.evento_ids)
        ips_falha = {c.split("ip:")[1] for c in raj.chaves if c.startswith("ip:")}
        # login_ok posterior de IP que nao estava nas falhas
        ok = next(
            (e for e in logins_ok
             if t_raj and e.ts >= t_raj and e.ip and e.ip not in ips_falha
             and (raj.usuario is None or e.usuario == raj.usuario)),
            None,
        )
        if not ok:
            continue
        chaves = set(raj.chaves) | {f"ip:{ok.ip}"} | ({f"user:{ok.usuario}"} if ok.usuario else set())
        eids = list(raj.evento_ids) + [ok.id]

        # R6: houve troca de credencial depois do login_ok?
        troca = next((e for e in trocas if e.ts >= ok.ts
                      and (e.usuario is None or ok.usuario is None or e.usuario == ok.usuario)), None)
        if troca:
            hits.append(Hit(
                "account_takeover", "incidente", "HIGH",
                "Possivel invasao de conta",
                "Muitas falhas de login, depois um acesso bem-sucedido de IP "
                "novo e, na sequencia, troca de credencial — sinal forte de "
                "conta comprometida.",
                usuario=ok.usuario, chaves=chaves | {"troca_credencial"},
                evento_ids=eids + [troca.id],
            ))
        else:
            hits.append(Hit(
                "account_takeover", "suspeita", "MEDIUM",
                "Acesso suspeito apos falhas de login",
                "Acesso bem-sucedido de um IP novo logo apos uma rajada de "
                "falhas de login.",
                usuario=ok.usuario, chaves=chaves, evento_ids=eids,
            ))
    return hits


REGRAS_INDIVIDUAIS = [
    r1_brute_force, r2_spray, r3_pin_probing, r4_ingest_probing,
    r7_sessao_anomala, r8_token_inesperado,
]


def avaliar(eventos: Iterable) -> list[Hit]:
    """Roda todas as regras sobre a janela de eventos e devolve os hits,
    incluindo as regras compostas de correlacao."""
    eventos = list(eventos)
    base: list[Hit] = []
    for regra in REGRAS_INDIVIDUAIS:
        base.extend(regra(eventos))
    compostas = r5_r6_takeover(eventos, base)
    return base + compostas
