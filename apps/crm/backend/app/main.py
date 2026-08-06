import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RateLimitMiddleware, RequestIdMiddleware, default_rate_limits
from app.db.session import init_db
from app.api.routes_health import router as health_router
from app.api.routes_auth import router as auth_router
from app.api.routes_companies import router as companies_router
from app.api.routes_contacts import router as contacts_router
from app.api.routes_leads import router as leads_router
from app.api.routes_opportunities import router as opportunities_router
from app.api.routes_pipelines import router as pipelines_router
from app.api.routes_tasks import router as tasks_router
from app.api.routes_meetings import router as meetings_router
from app.api.routes_notes import router as notes_router
from app.api.routes_jarvis import router as jarvis_router
from app.api.routes_workspace_io import router as workspace_io_router
from app.api.routes_workspaces import router as workspaces_router
from app.api.routes_activities import router as activities_router
from app.api.routes_lead_scoring import router as lead_scoring_router
from app.api.routes_workflows import router as workflows_router
from app.api.routes_tags import router as tags_router
from app.api.routes_external_accounts import router as integrations_router
from app.api.routes_restore import router as restore_router
from app.api.routes_email_templates import router as email_templates_router
from app.api.routes_files import router as files_router
from app.api.routes_sentinela import router as sentinela_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.backup_scheduler import run_backup_scheduler

    configure_logging()
    init_db()
    stop_event = asyncio.Event()
    backup_task = asyncio.create_task(run_backup_scheduler(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        try:
            await asyncio.wait_for(backup_task, timeout=2.0)
        except asyncio.TimeoutError:
            backup_task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VisiQuost",
        version=__version__,
        description="AI-powered Universal CRM with the Jarvis assistant.",
        lifespan=lifespan,
    )
    # Middleware runs in REVERSE registration order for requests. We want:
    #   1. RequestId (outermost) — stamps every log line
    #   2. RateLimit — reject early before hitting handlers
    #   3. CORS (innermost) — closest to routes so 429s carry CORS headers
    # So register in that reverse order: CORS, RateLimit, RequestId.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware, rules=default_rate_limits())
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(companies_router, prefix="/api/v1")
    app.include_router(contacts_router, prefix="/api/v1")
    app.include_router(leads_router, prefix="/api/v1")
    app.include_router(opportunities_router, prefix="/api/v1")
    app.include_router(pipelines_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(meetings_router, prefix="/api/v1")
    app.include_router(notes_router, prefix="/api/v1")
    app.include_router(jarvis_router, prefix="/api/v1")
    app.include_router(workspace_io_router, prefix="/api/v1")
    app.include_router(workspaces_router, prefix="/api/v1")
    app.include_router(activities_router, prefix="/api/v1")
    app.include_router(lead_scoring_router, prefix="/api/v1")
    app.include_router(workflows_router, prefix="/api/v1")
    app.include_router(tags_router, prefix="/api/v1")
    app.include_router(integrations_router, prefix="/api/v1")
    app.include_router(restore_router, prefix="/api/v1")
    app.include_router(email_templates_router, prefix="/api/v1")
    app.include_router(files_router, prefix="/api/v1")
    app.include_router(sentinela_router, prefix="/api/v1")

    # Design system compartilhado da suite (packages/ui) — servido em /ui.
    # Precisa ser montado ANTES do catch-all "/", senao o mount da raiz engole
    # a rota. Silenciosamente ignorado se a pasta nao existir (o app continua
    # funcional, so perde os tokens da marca).
    ui_dir = Path(__file__).resolve().parents[4] / "packages" / "ui"
    if ui_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(ui_dir)), name="sentinela-ui")

    # Mount the static frontend at "/". Path is relative to the repo root
    # (backend/ is the CWD when running uvicorn). Skipped silently if missing —
    # keeps tests happy in ephemeral environments.
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_dir.exists():
        # StaticFiles subclass que forca no-cache — evita browser servir HTML/JS/CSS
        # velho apos deploy sem hard-refresh do usuario.
        from starlette.responses import Response as _Resp
        from starlette.types import Scope

        class _NoCacheStatic(StaticFiles):
            async def get_response(self, path: str, scope: Scope) -> _Resp:  # type: ignore[override]
                resp = await super().get_response(path, scope)
                resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                resp.headers["Pragma"] = "no-cache"
                resp.headers["Expires"] = "0"
                return resp

        app.mount("/", _NoCacheStatic(directory=str(frontend_dir), html=True), name="frontend")
    return app


app = create_app()
