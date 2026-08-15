"""Structured logging with per-request IDs.

Uses stdlib `logging` + a contextvar so any log call in the request chain gets
the request_id automatically. No external deps. JSON output when APP_ENV != dev
so the logs are ingestable by ELK/Loki/Datadog; human-readable in dev.
"""
import json
import logging
import re
import sys
import time
from contextvars import ContextVar
from typing import Any

from app.core.config import get_settings

# Sanitizacao de secrets no log (ESPEC-SEGURANCA.md secao 12): o modulo Seguranca
# protege inclusive contra o proprio descuido — se um segredo cair numa mensagem
# de log, este filtro o redige antes de sair. Cobre os mesmos prefixos de alto
# sinal dos detectores.
_SECRET_LOG_RX = re.compile(
    r"(AKIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{36,}"
    r"|sk_live_[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s:/@]+@[^\s/]+)"
)


class RedactSecretsFilter(logging.Filter):
    """Redige padroes de secret de QUALQUER mensagem de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        if _SECRET_LOG_RX.search(msg):
            record.msg = _SECRET_LOG_RX.sub("[REDIGIDO]", msg)
            record.args = None
        return True

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
workspace_id_var: ContextVar[str] = ContextVar("workspace_id", default="-")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.workspace_id = workspace_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "user_id": getattr(record, "user_id", "-"),
            "workspace_id": getattr(record, "workspace_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return (
            f"{time.strftime('%H:%M:%S', time.localtime(record.created))} "
            f"[{record.levelname:<5}] req={getattr(record, 'request_id', '-')[:8]} "
            f"user={getattr(record, 'user_id', '-')[:8]} "
            f"{record.name}: {record.getMessage()}"
        )


_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True
    settings = get_settings()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    handler.addFilter(RedactSecretsFilter())
    handler.setFormatter(JsonFormatter() if settings.app_env != "dev" else HumanFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # Quiet down noisy libraries.
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
