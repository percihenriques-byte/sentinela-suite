"""Tests for tick 15: tag_entity intent, ExternalAccount + crypto, bulk delete."""
import os

os.environ.setdefault("FIELD_ENCRYPTION_KEY", "test-encryption-secret-value-please-change")


def _chat(client, message):
    resp = client.post("/api/v1/jarvis/chat", json={"message": message})
    assert resp.status_code == 200
    return resp.json()


def test_tag_entity_intent_creates_tag_and_link(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "last_name": "Byte"})
    body = _chat(auth_client, "tag Ada as VIP")
    assert body["fallback"] is False, body
    assert body["intent"] == "tag_entity"
    tags = auth_client.get("/api/v1/tags").json()
    assert any(t["name"] == "VIP" for t in tags["items"])


def test_tag_entity_missing_subject(auth_client):
    body = _chat(auth_client, "tag Nobody as VIP")
    assert body["intent"] == "tag_entity"
    assert "No" in body["reply"] or "Não" in body["reply"]


def test_crypto_roundtrip():
    from app.core.crypto import decrypt, encrypt
    ct = encrypt("hello secret")
    assert ct and ct != "hello secret"
    assert decrypt(ct) == "hello secret"


def test_crypto_wrong_ciphertext_returns_empty():
    from app.core.crypto import decrypt
    assert decrypt("not-a-valid-token") == ""


def test_external_account_connect_and_peek(auth_client):
    r = auth_client.post("/api/v1/integrations/connect", json={
        "provider": "google",
        "access_token": "ya29.super-secret",
        "account_label": "founder@example.com",
    })
    assert r.status_code == 201, r.text
    acc = r.json()
    assert acc["provider"] == "google"

    listed = auth_client.get("/api/v1/integrations").json()
    assert listed["total"] == 1

    peek = auth_client.get(f"/api/v1/integrations/{acc['id']}/token").json()
    assert peek["decryptable"] is True
    assert peek["length"] == len("ya29.super-secret")


def test_external_account_invalid_provider(auth_client):
    r = auth_client.post("/api/v1/integrations/connect", json={
        "provider": "myspace", "access_token": "x",
    })
    assert r.status_code == 400


def test_bulk_delete_contacts(auth_client):
    a = auth_client.post("/api/v1/contacts", json={"first_name": "A"}).json()
    b = auth_client.post("/api/v1/contacts", json={"first_name": "B"}).json()
    c = auth_client.post("/api/v1/contacts", json={"first_name": "C"}).json()
    r = auth_client.post("/api/v1/contacts/bulk-delete", json={"ids": [a["id"], b["id"]]}).json()
    assert r["deleted"] == 2
    remaining = auth_client.get("/api/v1/contacts").json()
    assert remaining["total"] == 1
    assert remaining["items"][0]["id"] == c["id"]
