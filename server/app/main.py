"""DRASS FastAPI application."""
import logging
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import OperationalError
from .api import routes_core, routes_more
from .core.config import get_settings
from .db import SessionLocal
from .domain.errors import DrassError
from .services import files_service, index_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("drass.app")
settings = get_settings()


def _retry_loop(stop: threading.Event) -> None:
    """Failed embeddings are retried every 10 minutes (PRD s19 'retry is queued')."""
    while not stop.wait(600):
        try:
            index_service.rebuild(SessionLocal, "failed", 0)
        except Exception:   # noqa: BLE001
            log.exception("retry loop error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    files_service.ensure_dirs()
    stop = threading.Event()
    if settings.embedder != "hash":
        threading.Thread(target=_retry_loop, args=(stop,), daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="DRASS API", lifespan=lifespan,
              docs_url="/docs" if settings.enable_docs else None,
              redoc_url=None, openapi_url="/openapi.json" if settings.enable_docs else None)
app.include_router(routes_core.router)
app.include_router(routes_more.router)


def _err(status: int, code: str, message: str, fields=None) -> JSONResponse:
    body = {"success": False, "error_code": code, "message": message}
    if fields:
        body["fields"] = fields
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(DrassError)
async def drass_handler(request: Request, exc: DrassError):
    return _err(exc.http_status, exc.error_code, exc.message, exc.fields)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    fields = {".".join(str(p) for p in e["loc"][1:]) or "body": e["msg"] for e in exc.errors()}
    return _err(422, "VALIDATION_ERROR", "Some values are missing or invalid.", fields)


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
    return _err(exc.status_code, code, "The requested resource was not found." if exc.status_code == 404 else str(exc.detail))


@app.exception_handler(OperationalError)
async def db_handler(request: Request, exc: OperationalError):
    log.error("database unavailable: %s", exc)
    return _err(503, "DATABASE_UNAVAILABLE", "The database is currently unavailable. Please try again shortly.")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return _err(500, "INTERNAL_ERROR", "Something went wrong on the server. The error has been logged.")


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
