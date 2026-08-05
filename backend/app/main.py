from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import router as api_v1_router
from app.config import PROJECT_ROOT, Settings
from app.security.vault import VaultManager


FRONTEND_DIR = PROJECT_ROOT / "frontend"
BUILD_VERSION = "0.0.2.4"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="人生图谱 LifeGraph",
        version=BUILD_VERSION,
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.vault = VaultManager(settings.data_dir, settings.session_ttl_seconds)

    @app.middleware("http")
    async def disable_frontend_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["X-LifeGraph-Build"] = BUILD_VERSION
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            error = detail
        else:
            error = {"code": "HTTP_ERROR", "message": str(detail)}
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": error},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"服务器内部错误：{exc.__class__.__name__}: {exc}",
                },
            },
        )

    app.include_router(api_v1_router)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/health", include_in_schema=False)
    def health() -> dict:
        return {"ok": True, "service": "lifegraph", "version": BUILD_VERSION}

    return app


app = create_app()
