"""Settings that are read once at boot must say so — checked against the code.

`settings_service.RESTART_REQUIRED` is a hand-kept list, and a list nobody
verifies rots: the next setting that is read while the process starts (a listener,
a thread, a presentation context) would look like an immediate switch in the UI,
exactly the "switch that does nothing" this codebase warns about elsewhere.

So the list is checked against the **read sites** in the code:

* every marked setting is read only in the startup readers (the list stays true),
* every setting read *only* in the startup readers is marked, deployment-owned,
  or listed in `LIVE_DESPITE_STARTUP_READER` with a reason.

The second direction is the one that catches a new mistake. It is deliberately
conservative: it only looks at where the value is **read**, not at who calls the
reader, because "started from the lifespan" (a worker thread) does not mean "read
once" — a thread that re-reads per tick is live.
"""
import ast
from pathlib import Path

import pytest

from mwl_broker import settings_service

BACKEND = Path(__file__).resolve().parents[1] / "mwl_broker"

GETTERS = {"get_bool", "get_int", "get_str", "get_raw"}

# Functions that read settings **once**, while the process starts:
# the lifespan (the MLLP thread is started there), the MLLP thread body itself,
# the AE construction (presentation contexts), and the TLS configuration helper
# the listener is built from.
STARTUP_READERS = {
    "main:lifespan",
    "mllp:serve",
    "mpps:enabled",
    "dimse:_build_ae",
    "tls:_config",
}

# `tls:_config()` is shared: `build_server_context()` uses it once at boot, and
# `client_tls_args()` uses it per outbound association. A key read only there can
# therefore be either — these four are the live ones, and they are named here so
# the exception is visible instead of silently accepted.
LIVE_DESPITE_STARTUP_READER = {
    "tls_outbound_ca_file",
    "tls_outbound_client_cert_file",
    "tls_outbound_client_key_file",
    "tls_outbound_verify",
}


def read_sites() -> dict[str, set[str]]:
    """`{setting: {"module:function"}}` — where the value is read."""
    sites: dict[str, set[str]] = {}
    for path in sorted(BACKEND.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                func = call.func
                name = func.attr if isinstance(func, ast.Attribute) else ""
                if (name in GETTERS and call.args
                        and isinstance(call.args[0], ast.Constant)):
                    sites.setdefault(call.args[0].value, set()).add(f"{path.stem}:{node.name}")
    return sites


SITES = read_sites()


def test_the_scan_finds_the_readers():
    """A silent scanner (renamed helper, changed getter) must not pass."""
    assert len(SITES) > 40, "the settings scan found too few read sites"
    for reader in STARTUP_READERS:
        module, _, func = reader.partition(":")
        source = (BACKEND / f"{module}.py").read_text()
        assert f"def {func}(" in source, f"{reader} does not exist any more"


def test_a_marked_setting_is_really_read_at_startup():
    """The other direction: a setting that became live must lose the mark —
    otherwise the UI keeps claiming a restart is needed."""
    wrong = {
        key: sorted(SITES.get(key, []))
        for key in settings_service.RESTART_REQUIRED
        if not SITES.get(key) or not SITES[key] <= STARTUP_READERS
    }
    assert not wrong, (
        "these are marked as restart-only but are read while running: "
        f"{wrong} — remove them from RESTART_REQUIRED"
    )


def test_a_setting_read_only_at_startup_is_marked():
    """Forward: the check that catches a new mistake."""
    startup_only = {
        key for key, where in SITES.items() if where and where <= STARTUP_READERS
    }
    unexplained = sorted(
        key for key in startup_only
        if key not in settings_service.RESTART_REQUIRED
        and key not in settings_service.DEPLOYMENT_ONLY
        and key not in LIVE_DESPITE_STARTUP_READER
    )
    assert not unexplained, (
        f"{unexplained} are read only while the process starts "
        f"({ {k: sorted(SITES[k]) for k in unexplained} }) — the UI would show a "
        "switch that does nothing. Add them to settings_service.RESTART_REQUIRED, "
        "or to LIVE_DESPITE_STARTUP_READER with a reason."
    )


def test_the_two_setting_axes_do_not_overlap():
    """`DEPLOYMENT_ONLY` says *where* a value may be changed, `RESTART_REQUIRED`
    says *when* it takes effect — they are different axes, and a key on both would
    show two badges that contradict each other ("set by the deployment" and
    "after a restart"). `tls_inbound_port` is deployment-owned and read at
    startup; it is deliberately only on the first list."""
    assert not (settings_service.RESTART_REQUIRED & settings_service.DEPLOYMENT_ONLY)
    assert settings_service.RESTART_REQUIRED


def test_the_startup_only_set_is_not_empty():
    """A canary for the scan itself: if it finds nothing, the checks above pass
    for the wrong reason."""
    startup_only = {key for key, where in SITES.items() if where and where <= STARTUP_READERS}

    assert len(startup_only) >= 10, f"the scan found too few: {sorted(startup_only)}"
