"""Regression tests for the tick-18 review pass."""


def test_create_task_intent_accepts_english_article(auth_client):
    """Before fix: 'create a task: ...' failed to match because regex only
    accepted the Portuguese article 'uma', not English 'a' or 'new'."""
    for phrase in ("create a task: call John", "add a task: prep deck", "create new task: review PR"):
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": phrase}).json()
        assert r["intent"] == "create_task", f"failed for: {phrase}"
    tasks = auth_client.get("/api/v1/tasks").json()
    titles = {t["title"] for t in tasks["items"]}
    assert any("call John" in t for t in titles)
    assert any("prep deck" in t for t in titles)
    assert any("review PR" in t for t in titles)


def test_workflow_subject_model_map():
    """The subject-model dispatch table is what workflow conditions rely on."""
    from app.services.workflow_service import _SUBJECT_MODELS
    from app.models import Contact, Lead, Opportunity

    assert _SUBJECT_MODELS["contact"] is Contact
    assert _SUBJECT_MODELS["lead"] is Lead
    assert _SUBJECT_MODELS["opportunity"] is Opportunity
    assert _SUBJECT_MODELS.get("nothing") is None


def test_crypto_decrypt_logs_on_bad_token(caplog):
    """Invalid ciphertext should log a WARNING (not silently return '')."""
    import logging
    from app.core.crypto import decrypt

    with caplog.at_level(logging.WARNING, logger="jarvis.crypto"):
        out = decrypt("this-is-not-a-real-fernet-token")
    assert out == ""
    assert any("fernet_decrypt_failed" in r.message for r in caplog.records)


def test_crypto_decrypt_empty_is_silent(caplog):
    import logging
    from app.core.crypto import decrypt

    with caplog.at_level(logging.WARNING, logger="jarvis.crypto"):
        assert decrypt("") == ""
    assert not caplog.records  # empty input isn't a failure
