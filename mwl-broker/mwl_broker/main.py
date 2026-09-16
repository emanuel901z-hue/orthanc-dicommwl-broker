"""FastAPI entrypoint. Startup: DB init → seed → DICOM SCP thread → echo loop.

Run:  uvicorn mwl_broker.main:app --host 0.0.0.0 --port 8081
"""
import json
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from . import api, db
from .config import get_settings
from .dimse import BrokerSCP
from .echo import echo_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("mwl_broker.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db.init_db()
    if settings.seed_config_json:
        try:
            db.seed_from_json(json.loads(settings.seed_config_json))
        except Exception as exc:
            log.error("seed config failed: %s", exc)

    scp = None
    stop = threading.Event()
    echo_thread = None
    if settings.start_dicom:
        scp = BrokerSCP(settings)
        scp.start()
        api.bind_scp(scp)
    if settings.start_echo_loop:
        echo_thread = threading.Thread(
            target=echo_loop, args=(settings.echo_interval_s, stop), daemon=True
        )
        echo_thread.start()
    try:
        yield
    finally:
        stop.set()
        if echo_thread is not None:
            echo_thread.join(timeout=2)
        if scp is not None:
            scp.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="mwl-broker", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev convenience; tighten behind the reverse proxy
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api.router)

    @app.get("/metrics")
    def prometheus_metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "db": db.check_db()}

    return app


app = create_app()
