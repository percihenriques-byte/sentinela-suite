"""Regression tests for the tick-20 review pass."""


def test_cors_origins_empty_env_falls_back_to_default(monkeypatch):
    """CORS_ORIGINS=`` (or ` , , `) previously became [] which silently broke
    all cross-origin requests.

    O default mudou de `localhost:3000` (porta de dev que nao existe neste
    produto) para as origens loopback do proprio app — ver A5 na auditoria e
    test_a5_cors_default_e_so_loopback."""
    from app.core.config import CORS_PADRAO, Settings

    padrao = list(CORS_PADRAO)

    monkeypatch.setenv("CORS_ORIGINS", "")
    s = Settings()
    assert s.cors_origins == padrao

    monkeypatch.setenv("CORS_ORIGINS", " , , ,")
    s = Settings()
    assert s.cors_origins == padrao

    # Real value still parses.
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com, https://b.com")
    s = Settings()
    assert s.cors_origins == ["https://a.com", "https://b.com"]


def test_workflow_template_accepts_whitespace_around_key():
    """`{{ subject_id }}` (with spaces) was rendering verbatim in step outputs."""
    from app.services.workflow_service import _substitute

    ctx = {"subject_id": "abc-123", "kind": "created"}
    assert _substitute("hi {{subject_id}}", ctx) == "hi abc-123"
    assert _substitute("hi {{ subject_id }}", ctx) == "hi abc-123"
    assert _substitute("{{ subject_id }} did {{kind}}", ctx) == "abc-123 did created"
    # Unknown keys are left as-is so the author notices the typo.
    assert _substitute("hi {{ oops }}", ctx) == "hi {{ oops }}"


def test_rate_limit_bucket_uses_none_sentinel():
    """Regression: sentinel used to be 0.0, ambiguous with a real early-boot
    monotonic value."""
    from app.core.middleware import RateLimitMiddleware, TokenBucketConfig

    m = RateLimitMiddleware.__new__(RateLimitMiddleware)  # skip Starlette init
    from collections import defaultdict
    from threading import Lock
    from app.core.middleware import _Bucket

    m._rules = []
    m._buckets = defaultdict(lambda: _Bucket(0.0, None))
    m._lock = Lock()

    cfg = TokenBucketConfig(capacity=3, refill_per_sec=1.0)
    # First call primes the bucket to capacity minus one.
    allowed, _ = m._consume(("ip", "/x"), cfg)
    assert allowed is True
    # Bucket state should now have a real timestamp, not None.
    b = m._buckets[("ip", "/x")]
    assert b.updated_at is not None
    assert b.tokens == pytest_approx(2.0)


def pytest_approx(x, rel=1e-3):
    class _Approx:
        def __eq__(self, other): return abs(other - x) <= rel
    return _Approx()


def test_workspace_export_uses_aware_utc(auth_client):
    """utcnow() is deprecated in 3.12; export must use tz-aware datetime."""
    body = auth_client.get("/api/v1/workspaces/current/export").json()
    ts = body["exported_at"]
    # tz-aware ISO strings end with an offset like +00:00 or Z.
    assert ts.endswith("+00:00") or ts.endswith("Z")
