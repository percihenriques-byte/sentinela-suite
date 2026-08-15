"""Modulo Seguranca — validacao de formato do identificador (endurecimento).

Antes de cifrar/consultar, o cadastro recusa (422) identificadores que jamais
poderiam ser o que o tipo diz ser: um repo tem de ser `dono/nome`, um dominio
tem de parecer dominio, um e-mail tem de ter arroba e host. Assim um repo
mal-formado nunca vira URL de tarball, nem um dominio lixo vira consulta DNS.
A checagem e lenient de proposito: recusa so o impossivel, sem impor politica.
"""


def _post(auth_client, tipo, identificador):
    return auth_client.post(
        "/api/v1/seguranca/ativos", json={"tipo": tipo, "identificador": identificador}
    )


# ---- repo: dono/nome ------------------------------------------------------

def test_repo_valido_passa(auth_client):
    assert _post(auth_client, "repo", "org/meu-repo").status_code == 201


def test_repo_sem_barra_recusado(auth_client):
    r = _post(auth_client, "repo", "soo-nome")
    assert r.status_code == 422
    assert "dono/nome" in r.text


def test_repo_com_url_recusado(auth_client):
    assert _post(auth_client, "repo", "https://github.com/org/r").status_code == 422


def test_repo_com_espaco_recusado(auth_client):
    assert _post(auth_client, "repo", "org / nome").status_code == 422


# ---- dominio / subdominio -------------------------------------------------

def test_dominio_valido_passa(auth_client):
    assert _post(auth_client, "dominio", "exemplo.com").status_code == 201


def test_subdominio_valido_passa(auth_client):
    assert _post(auth_client, "subdominio", "app.exemplo.com").status_code == 201


def test_dominio_sem_ponto_recusado(auth_client):
    r = _post(auth_client, "dominio", "localhost")
    assert r.status_code == 422
    assert "dominio" in r.text.lower()


def test_dominio_com_espaco_recusado(auth_client):
    assert _post(auth_client, "dominio", "exe mplo.com").status_code == 422


# ---- email ----------------------------------------------------------------

def test_email_valido_passa(auth_client):
    assert _post(auth_client, "email", "pessoa@exemplo.com").status_code == 201


def test_email_sem_arroba_recusado(auth_client):
    assert _post(auth_client, "email", "pessoa.exemplo.com").status_code == 422


def test_email_sem_host_recusado(auth_client):
    assert _post(auth_client, "email", "pessoa@localhost").status_code == 422


# ---- api_endpoint ---------------------------------------------------------

def test_api_endpoint_valido_passa(auth_client):
    assert _post(auth_client, "api_endpoint", "https://api.exemplo.com/v1").status_code == 201


def test_api_endpoint_sem_esquema_recusado(auth_client):
    assert _post(auth_client, "api_endpoint", "api.exemplo.com").status_code == 422


# ---- tipos livres seguem passando ----------------------------------------

def test_username_livre_passa(auth_client):
    assert _post(auth_client, "username", "joao_123").status_code == 201


def test_dispositivo_livre_passa(auth_client):
    assert _post(auth_client, "dispositivo", "Notebook da sala").status_code == 201
