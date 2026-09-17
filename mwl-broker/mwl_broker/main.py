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
    app = FastAPI(
        title="MWL Broker",
        version="0.1.0",
        summary="DICOM Modality Worklist broker — C-FIND proxy/aggregator + C-STORE router",
        description=(
            "Sits between modalities and multiple upstream RIS/KIS systems:\n\n"
            "* **MWL SCP** — modalities send C-FIND; the broker fans out to all "
            "enabled sources in parallel, merges and deduplicates by "
            "PatientID/AccessionNumber/SPS-ID (first source by priority wins), "
            "and streams the merged answers back.\n"
            "* **C-STORE router** — incoming instances are matched against "
            "worklist provenance (`seen_items`) and forwarded to the PACS "
            "selected by the first matching routing rule, falling back to the "
            "default target.\n\n"
            "This REST API manages sources, targets and routing rules and "
            "exposes monitoring data (status, PHI-free logs, C-ECHO). "
            "Prometheus metrics are served at `/metrics`."
        ),
        openapi_tags=[
            {"name": "sources", "description": "Upstream MWL sources (RIS/KIS) queried via C-FIND."},
            {"name": "targets", "description": "PACS targets that receive forwarded C-STORE traffic."},
            {"name": "rules", "description": "Routing rules: worklist source → store target."},
            {"name": "logs", "description": "C-FIND and C-STORE audit logs (PHI-free)."},
            {"name": "monitoring", "description": "Health, status snapshot, C-ECHO and Prometheus metrics."},
        ],
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev convenience; tighten behind the reverse proxy
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api.router)

    @app.get(
        "/metrics", tags=["monitoring"],
        summary="Prometheus metrics",
        description="Prometheus text exposition format (C-FIND/C-STORE counters, "
                    "echo gauges, durations).",
        response_class=Response,
    )
    def prometheus_metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get(
        "/healthz", tags=["monitoring"],
        summary="Liveness + DB check",
        description="Returns `ok` and whether the config/log database is reachable.",
    )
    def healthz():
        return {"ok": True, "db": db.check_db()}

    return app


app = create_app()
