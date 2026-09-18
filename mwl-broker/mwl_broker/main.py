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
from .schemas import ReadyOut
from .config import get_settings
from .dimse import BrokerSCP
from . import atna
from . import mllp
from . import rbac
from . import rbac
from .echo import echo_loop
from .spool import worker as spool_worker

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
    spool_thread = None
    mllp_thread = None
    if settings.start_dicom:
        scp = BrokerSCP(settings)
        scp.start()
        api.bind_scp(scp)
    if settings.start_echo_loop:
        echo_thread = threading.Thread(
            target=echo_loop, args=(settings.echo_interval_s, stop), daemon=True
        )
        echo_thread.start()
    if settings.start_atna:
        atna.start()
    if settings.hl7_mllp_enabled:
        mllp_thread = threading.Thread(target=mllp.serve, args=(stop,), daemon=True)
        mllp_thread.start()
    if settings.start_spool:
        # store and forward: retries instances that could not be delivered
        spool_thread = threading.Thread(target=spool_worker, args=(stop,), daemon=True)
        spool_thread.start()
    try:
        yield
    finally:
        stop.set()
        atna.stop()
        if echo_thread is not None:
            echo_thread.join(timeout=2)
        if spool_thread is not None:
            spool_thread.join(timeout=2)
        if mllp_thread is not None:
            mllp_thread.join(timeout=2)
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
            {"name": "transforms", "description": "DICOM attribute modifications applied before forwarding (tag set/remove/prefix/suffix/replace/copy)."},
            {"name": "settings", "description": "Runtime settings — UI override over the deployment ENV default."},
            {"name": "local", "description": "Local worklist items (emergencies) and the HL7 ORM interface."},
            {"name": "rbac", "description": "Access mode: who may change the configuration (decided by the proxy)."},
            {"name": "retention", "description": "Retention and deletion: per-table overview and a manual cleanup."},
            {"name": "tls", "description": "DICOM TLS: certificate management, mTLS options and endpoint checks."},
            {"name": "atna", "description": "IHE ATNA audit trail: PS3.15 audit messages over syslog/TLS."},
            {"name": "spool", "description": "C-STORE spool: store-and-forward queue with retries and dead letters."},
            {"name": "cache", "description": "Worklist cache: snapshots that bridge an unreachable RIS, with a bounded stale window."},
            {"name": "audit", "description": "Configuration change log (before/after snapshots)."},
            {"name": "config", "description": "Configuration export, import (dry-run) and rollback."},
            {"name": "simulation", "description": "Dry-run simulation of routing and modify rules — same code as the live path."},
            {"name": "logs", "description": "C-FIND and C-STORE audit logs (PHI-free)."},
            {"name": "monitoring", "description": "Health, status snapshot, C-ECHO and Prometheus metrics."},
        ],
        lifespan=lifespan,
    )
    # Read/write split, decided by the proxy's roles header. Off by default:
    # a single-admin installation works unchanged.
    @app.middleware("http")
    async def rbac_guard(request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS") \
                and request.url.path.startswith("/api/v1") \
                and not rbac.can_write(request.headers):
            log.warning("RBAC: write denied for %s %s (roles: %s)", request.method,
                        request.url.path, rbac.roles_from_headers(request.headers))
            from fastapi.responses import JSONResponse

            return JSONResponse(
                {"detail": "Your account is not allowed to change the broker "
                           "configuration (missing role "
                           f"'{rbac.describe(request.headers)['write_role']}')."},
                status_code=403,
            )
        return await call_next(request)

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
        response_description="Metrics in Prometheus text exposition format.",
        response_class=Response,
    )
    def prometheus_metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get(
        "/healthz/ready", response_model=ReadyOut, tags=["monitoring"],
        summary="Readiness probe",
        description="Verifies that the required components are up: the config/log "
                    "database and — when DICOM is enabled — the listening SCP. "
                    "Returns 503 when not ready (for orchestrators/load balancers).",
        response_description="`{ready, checks}` — 503 when a required component is down.",
        responses={503: {"description": "At least one required component is down."}},
    )
    def healthz_ready(response: Response):
        settings = get_settings()
        checks = {
            "db": db.check_db(),
            "scp": api.scp_listening() if settings.start_dicom else True,
        }
        ready = all(checks.values())
        if not ready:
            response.status_code = 503
        return {"ready": ready, "checks": checks}

    @app.get(
        "/healthz", tags=["monitoring"],
        summary="Liveness + DB check",
        description="Returns `ok` and whether the config/log database is reachable.",
        response_description="`{ok, db}` — `db` is false when the database is unreachable.",
    )
    def healthz():
        return {"ok": True, "db": db.check_db()}

    return app


app = create_app()
