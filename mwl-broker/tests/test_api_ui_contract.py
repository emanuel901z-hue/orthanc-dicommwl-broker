"""The API ↔ UI contract, in both directions.

**Reverse (UI → API):** every path the typed client calls must exist as a route —
otherwise the operator presses a button that 404s.

**Forward (API → UI):** every route is either reachable from the UI or listed
below with the reason why it is not. A new endpoint therefore cannot be added
without a decision: the test fails until it has a UI element or an entry here.

**Fields:** every field of the write schemas must be reachable in the UI too —
a new backend field with no input is the same class of gap (the
`strip_query_retrieve_level` switch came from exactly that).

The one-off answer to this question lives in `docs/api-completeness-audit.md`;
this test keeps it current. It found `POST /mpps/{step_id}/forward`: the MPPS card
showed *which* step the RIS had rejected, but the operator could only re-report
**all** pending steps, never that single one.
"""
import ast
import json
import re
from pathlib import Path

import pytest

from mwl_broker.main import app

ROOT = Path(__file__).resolve().parents[2]
OE3 = ROOT / "orthanc-explorer-3-usable"
CLIENT = OE3 / "src" / "api" / "broker.ts"

# Routes the UI deliberately does not call — with the reason.
API_ONLY = {
    "/healthz": "liveness probe for the container orchestrator",
    "/healthz/ready": "readiness probe (database + SCP)",
    "/metrics": "Prometheus scraping",
    "/api/v1/dicom-web/workitems": "UPS-RS: the DICOMweb interface for external consumers (conformance statement §9a)",
    "/api/v1/dicom-web/workitems/{param}": "UPS-RS (see above)",
    "/api/v1/dicom-web/workitems/{param}/state": "UPS-RS (see above)",
    "/api/v1/hl7/adt": "the ADT intake for the RIS; the UI offers the semantic equivalent (merge/link)",
    "/api/v1/orders/context": "for external MADO manifest creators (conformance statement §9c)",
    "/api/v1/mpps/{param}": "single-step detail for integrations — the UI lists the steps",
}

skip = pytest.mark.skipif(not OE3.is_dir(),
                          reason="the OE3 fork is a submodule — not checked out here")


def normalize(path: str) -> str:
    """Path parameters of either flavour (`{id}` / `${id}`) become `{param}`."""
    path = path.split("?")[0]
    path = re.sub(r"\$\{[^}]*\}", "{param}", path)
    path = re.sub(r"\{[^}]*\}", "{param}", path)
    return path.rstrip("/") or "/"


def backend_routes() -> set[str]:
    """The served contract: every path of the app's own OpenAPI document."""
    routes = set()
    for path, operations in app.openapi()["paths"].items():
        if path.startswith(("/openapi", "/docs", "/redoc")):
            continue
        if {"get", "post", "put", "delete", "patch"} & {m.lower() for m in operations}:
            routes.add(normalize(path))
    return routes


def _template_paths(text: str) -> set[str]:
    """Every path in a template literal, with `${…}` (even nested) as `{param}`.

    A regex is not enough: `` `/x/${id}/y?d=${a ? 'true' : 'false'}` `` contains a
    nested backtick and a ternary, so the plain match stops in the middle.
    """
    paths: set[str] = set()
    for start in (m.start() for m in re.finditer(r"`", text)):
        if not text.startswith("`/api/v1", start):
            continue
        out, i = [], start + 1
        while i < len(text):
            if text[i] == "`":
                break
            if text.startswith("${", i):
                depth, j = 1, i + 2
                while j < len(text) and depth:
                    depth += {"{": 1, "}": -1}.get(text[j], 0)
                    j += 1
                inner = text[i + 2:j - 1]
                # a conditional segment (`${id ? `/${id}` : ''}`) is optional — the
                # base path is what the client calls, not a path parameter
                if "`" not in inner:
                    out.append("{param}")
                i = j
                continue
            out.append(text[i])
            i += 1
        paths.add(normalize("".join(out)))
    return paths


def ui_paths() -> set[str]:
    """Paths the typed client calls (plain strings and template literals)."""
    text = CLIENT.read_text()
    plain = {normalize(m.group(1))
             for m in re.finditer(r"['\"](/api/v1[^'\"]*)['\"]", text)}
    return plain | _template_paths(text)


def client_methods() -> set[str]:
    """Method names of the broker client — to spot one nobody calls."""
    text = CLIENT.read_text()
    return set(re.findall(r"^\s{4,6}([a-zA-Z][a-zA-Z0-9]*):\s*(?:\(|async)", text, re.M))


def ui_source() -> str:
    """Everything the broker UI is written in (forms, client, types)."""
    parts = [CLIENT.read_text()]
    for path in (OE3 / "src" / "features" / "broker").rglob("*.ts*"):
        if path.name.endswith((".test.ts", ".test.tsx")):
            continue
        parts.append(path.read_text())
    return "\n".join(parts)


def openapi_schemas() -> dict:
    """The schemas of the running app, without starting a server."""
    return app.openapi()["components"]["schemas"]


@skip
def test_no_ui_call_without_a_route():
    missing = sorted(ui_paths() - backend_routes())
    assert not missing, f"the UI calls paths that do not exist: {missing}"


@skip
def test_every_route_is_reachable_or_explained():
    unused = sorted(backend_routes() - ui_paths() - set(API_ONLY))
    assert not unused, (
        "routes without a UI element — either wire them up or document why they "
        f"are API-only: {unused}"
    )


@skip
def test_the_allowlist_does_not_rot():
    """An entry that the UI now calls (or that no longer exists) is misleading."""
    stale = sorted(path for path in API_ONLY
                   if path not in backend_routes() or path in ui_paths())
    assert not stale, f"remove these from API_ONLY: {stale}"


@skip
def test_every_write_schema_field_is_reachable_in_the_ui():
    text = ui_source()
    schemas = openapi_schemas()
    gaps: dict[str, list[str]] = {}
    for name, schema in schemas.items():
        if not (name.endswith("In") or name.endswith("Update")):
            continue
        # coarse on purpose: the field name has to appear somewhere in the UI
        # source (form field, request type, query parameter). The precise check
        # for the two node forms follows below.
        missing = sorted(field for field in schema.get("properties", {})
                         if not re.search(rf"\b{re.escape(field)}\b", text))
        if missing:
            gaps[name] = missing
    # the import document is assembled by the UI from the export file, not typed
    gaps.pop("ConfigImportIn", None)
    assert not gaps, f"write fields no form can set: {gaps}"


@skip
def test_the_node_forms_cover_their_schemas_completely():
    """Sources and targets: every field of the schema is in the dialog."""
    text = (OE3 / "src" / "features" / "broker" / "components"
            / "NodeFormDialog.tsx").read_text()
    fields = set(re.findall(r"values\.([a-z_][a-z0-9_]*)", text))
    fields |= set(re.findall(r"set\('([a-z_][a-z0-9_]*)'", text))
    schemas = openapi_schemas()
    for schema_name in ("SourceIn", "TargetIn"):
        missing = sorted(f for f in schemas[schema_name]["properties"] if f not in fields)
        assert not missing, f"{schema_name}: not in the dialog: {missing}"


@skip
def test_no_client_method_without_a_caller():
    """A method the client defines but no view calls is a forgotten element.

    Not a hard rule — some methods exist for tests or for a planned view — but it
    has to be a decision, hence the short allowlist.
    """
    known_unused = {
        # per-row reads: the views list the rows, they never fetch a single one
        "get",
        # the "check a case" panel shows the routing decision that
        # `/simulate/transform` already returns (target, matched_via, reason) —
        # the dedicated route endpoint stays for API users
        "route",
    }
    text = ui_source()
    unused = sorted(name for name in client_methods()
                    if name not in known_unused
                    and not re.search(rf"brokerApi(?:\.\w+)*\.{re.escape(name)}\b", text))
    assert not unused, f"client methods no view calls: {unused}"
