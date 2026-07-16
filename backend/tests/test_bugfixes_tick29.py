"""Regression tests for the tick-29 review pass — SQL LIKE wildcard leak."""


def test_search_query_treats_underscore_literally(auth_client):
    """Before fix: '_' in a search query matched any single character, so
    `?q=Alic_` returned Alice, Alicf, and any 4-letter word starting with
    Alic. Now escaped."""
    for name in ("Alice", "Alicf", "Alic_"):
        auth_client.post("/api/v1/contacts", json={"first_name": name})

    r = auth_client.get("/api/v1/contacts?q=Alic_").json()
    names = {c["first_name"] for c in r["items"]}
    assert names == {"Alic_"}, names


def test_search_query_treats_percent_literally(auth_client):
    """Before fix: '?q=%' returned every row in the table."""
    for name in ("Alice", "Bob", "Carl"):
        auth_client.post("/api/v1/contacts", json={"first_name": name})

    r = auth_client.get("/api/v1/contacts?q=%").json()
    assert r["total"] == 0, r

    # ...but a literal '%' still matches a literal '%'
    auth_client.post("/api/v1/contacts", json={"first_name": "50%off"})
    r = auth_client.get("/api/v1/contacts?q=%").json()
    assert r["total"] == 1


def test_search_regular_query_still_works(auth_client):
    """Sanity: normal fuzzy substrings still match."""
    for name in ("Alice", "Alicf", "Alic_"):
        auth_client.post("/api/v1/contacts", json={"first_name": name})

    r = auth_client.get("/api/v1/contacts?q=Alic").json()
    assert r["total"] == 3


def test_companies_search_underscore_escaped(auth_client):
    for name in ("Acme_", "Acmex"):
        auth_client.post("/api/v1/companies", json={"name": name})
    r = auth_client.get("/api/v1/companies?q=Acme_").json()
    names = {c["name"] for c in r["items"]}
    assert names == {"Acme_"}


def test_jarvis_search_everywhere_respects_escape(auth_client):
    """The `search_everywhere` tool routes through the same ilike path."""
    for name in ("Wonder_", "Wonderx", "Wondery"):
        auth_client.post("/api/v1/companies", json={"name": name})
    body = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "search everywhere for Wonder_",
    }).json()
    assert body["intent"] == "search_everywhere"
    tool_result = next(tc["result"] for tc in body["tool_calls"] if tc["name"] == "search_everywhere")
    companies = tool_result["results"]["companies"]
    assert len(companies) == 1
    assert companies[0]["name"] == "Wonder_"
