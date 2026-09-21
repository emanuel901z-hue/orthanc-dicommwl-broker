"""Role-based access for the broker API — read vs. write, decided by the proxy.

The broker itself does not authenticate users: it sits behind a reverse proxy
that authenticates and injects the user's roles in a header. This module turns
those roles into one decision — *may this request change configuration?* — and
keeps the policy in one place:

* `off` (default): no enforcement. A single-admin installation works unchanged.
* `enforce`: every non-GET request to the API needs the write role in the roles
  header. Reads stay open (the proxy already authenticated the user); the
  decision is logged and auditable through the change log's actor field.

The UI asks `GET /rbac/status` once and disables the write actions when the
operator is not allowed to write — instead of letting them run into 403s.
"""
import logging

from . import settings_service

log = logging.getLogger("mwl_broker.rbac")

MODE_OFF = "off"
MODE_ENFORCE = "enforce"

# Read-only endpoints that happen to use POST. A read-only operator must be able
# to *look*: dry-runs, C-ECHO and the TLS handshake check change nothing. Blocking
# them would take away exactly the safe tools (measured: 403 on POST /simulate/*).
READ_ONLY_POST_PATTERNS = (
    r"^/api/v1/simulate/(route|station|transform|worklist)$",
    r"^/api/v1/(sources|targets)/[^/]+/echo$",
    r"^/api/v1/tls/test$",
)

# Routes that are only read-only *when* they ask for a dry run. Applying the same
# payload must keep the write role, so the decision looks at the query string.
DRY_RUN_POST_PATTERNS = (
    r"^/api/v1/hl7/orm$",
    r"^/api/v1/config/import$",
)


def _config() -> dict:
    return {
        "mode": (settings_service.get_str("rbac_mode") or "off").strip().lower(),
        "roles_header": (settings_service.get_str("rbac_roles_header") or "X-OE3-Roles").strip(),
        "write_role": (settings_service.get_str("rbac_write_role") or "brokerWrite").strip(),
        "actor_header": (settings_service.get_str("audit_actor_header") or "X-OE3-User").strip(),
    }


def reset_for_tests() -> None:
    """Nothing cached — kept so test fixtures stay uniform."""


def enforce() -> bool:
    return settings_service.get_str("rbac_mode").strip().lower() == "enforce"


def roles_from_headers(headers) -> list[str]:
    """The roles the proxy injected (comma separated, case-insensitive)."""
    cfg = _config()
    raw = headers.get(cfg["roles_header"], "") or ""
    return [part.strip() for part in raw.split(",") if part.strip()]


def is_read_only_request(method: str, path: str, query: str = "") -> bool:
    """Whether this request only reads, even though it is not a GET.

    Kept next to the policy so the intent is documented in one place: the
    middleware asks this before it denies anything.
    """
    if method in ("GET", "HEAD", "OPTIONS"):
        return True
    import re

    for pattern in READ_ONLY_POST_PATTERNS:
        if re.match(pattern, path):
            return True
    for pattern in DRY_RUN_POST_PATTERNS:
        if re.match(pattern, path) and re.search(r"(^|&)dry_run=(true|1|yes)(&|$)", query or ""):
            return True
    return False


def can_write(headers) -> bool:
    """Whether this request may change configuration."""
    cfg = _config()
    if cfg["mode"] != "enforce":
        return True
    write_role = cfg["write_role"]
    return write_role in roles_from_headers(headers)


def describe(headers=None) -> dict:
    """State for the status endpoint and the UI banner."""
    cfg = _config()
    roles = roles_from_headers(headers) if hasattr(headers, "get") else []
    return {
        "mode": cfg["mode"],
        "enforced": cfg["mode"] == "enforce",
        "roles_header": cfg["roles_header"],
        "write_role": cfg["write_role"],
        "roles": roles,
        "can_write": (not cfg["mode"] == "enforce") or (cfg["write_role"] in roles),
    }
