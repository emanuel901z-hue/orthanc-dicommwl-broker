"""The deployment configuration must actually reach the broker.

Two failure classes, both found in a production review — this file keeps them
from coming back:

* **An ENV name that does not match what the deployment writes.** The field
  `broker_aet` made pydantic look for `BROKER_BROKER_AET`, while `.env`,
  compose, `setup.sh` and the docs all say `BROKER_AET`. The operator's AET was
  silently ignored, the broker kept answering as `MWLBROKER`, and every
  modality configured with the documented name would have been rejected at
  association time — a go-live failure that no test noticed, because the
  default and the deployment value happened to be identical.

* **A variable documented in `.env.example` that compose never forwards.**
  There is no `env_file:`, so only the variables listed in the
  `x-broker-environment` anchor reach the container. Everything else in `.env`
  is inert — a documented-but-dead variable is worse than an undocumented one.

The checks are deliberately functional where they can be: a documented variable
is set and the parsed setting is compared, so an alias/prefix mistake cannot
hide behind a matching default.
"""
import re
from pathlib import Path

import pytest

from mwl_broker.config import Settings

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "mwl-broker" / "mwl_broker" / "config.py"
COMPOSE = ROOT / "docker-compose.yml"
ENV_EXAMPLE = ROOT / ".env.example"

# Settings that belong to the deployment, not to `.env`: their value has to
# match the compose mapping / the mounted volume, so they are not meant to be
# set through the environment or the UI (see DEPLOYMENT_ONLY in
# settings_service and the read-only rendering in the UI).
DEPLOYMENT_OWNED = {"spool_dir", "tls_dir", "tls_inbound_port", "instance_id"}

# Variables in `.env.example` that configure compose itself (port mappings,
# binds, the second instance) rather than the broker process.
COMPOSE_SIDE = {
    "API_BIND", "API_PORT", "TLS_PORT", "MAX_BODY_BYTES",
    "B_API_BIND", "B_API_PORT", "B_DICOM_PORT", "B_TLS_PORT", "B_INSTANCE_ID",
}


def _setting_fields() -> list[str]:
    """The declared settings of the pydantic model, in file order."""
    return re.findall(r"^\s{4}([a-z_]+)\s*:\s*(?:bool|int|str)",
                      CONFIG.read_text(), re.M)


def _documented_env_names() -> list[str]:
    """Every BROKER_* variable `.env.example` documents."""
    return sorted(set(re.findall(r"^(BROKER_[A-Z0-9_]+)=", ENV_EXAMPLE.read_text(), re.M)))


def _probe(field: str, default) -> tuple[str, object]:
    """A value that must differ from the default, so a missed variable shows."""
    if isinstance(default, bool):
        return ("true" if not default else "false"), not default
    if isinstance(default, int):
        return str(default + 1), default + 1
    return "ZZPROBE", "ZZPROBE"


@pytest.mark.parametrize("env_name", _documented_env_names())
def test_a_documented_variable_really_changes_the_setting(env_name, monkeypatch):
    """Set the documented name and check that the broker sees it.

    The default and the probe differ, so an ignored variable (wrong prefix,
    wrong alias) fails here instead of silently at the customer's site.
    """
    field = env_name[len("BROKER_"):].lower()
    if field not in Settings.model_fields:
        pytest.skip(f"{env_name} is not a broker setting (compose/port variable)")
    default = Settings.model_fields[field].default
    value, expected = _probe(field, default)

    monkeypatch.setenv(env_name, value)

    assert getattr(Settings(), field) == expected, (
        f"{env_name} is documented but the broker does not read it "
        f"(field {field!r} still has its default {default!r})"
    )


def test_the_documented_aet_name_is_the_one_that_wins(monkeypatch):
    """`BROKER_AET` is the documented spelling and must beat the legacy alias."""
    monkeypatch.setenv("BROKER_AET", "MWL_KH")
    monkeypatch.setenv("BROKER_BROKER_AET", "LEGACY")

    assert Settings().broker_aet == "MWL_KH"


def test_the_legacy_aet_alias_still_works(monkeypatch):
    """A deployment that already uses the double prefix keeps working."""
    monkeypatch.delenv("BROKER_AET", raising=False)
    monkeypatch.setenv("BROKER_BROKER_AET", "LEGACY")

    assert Settings().broker_aet == "LEGACY"


def test_every_documented_broker_variable_reaches_the_container():
    """`.env` values are only forwarded when compose lists them (no `env_file`).

    A variable that `.env.example` documents but compose drops is a trap: the
    operator edits `.env`, restarts, and nothing happens.
    """
    compose = COMPOSE.read_text()
    dead = []
    for env_name in _documented_env_names():
        suffix = env_name[len("BROKER_"):]
        if suffix in COMPOSE_SIDE:
            continue
        if env_name in compose:
            continue
        dead.append(env_name)
    assert not dead, (
        "documented in .env.example but never forwarded by docker-compose.yml "
        f"(the container would ignore them): {dead}"
    )


def test_compose_forwards_the_environment_of_both_instances():
    """The second instance inherits the same anchor — that is deliberate."""
    compose = COMPOSE.read_text()
    assert compose.count("<<: *broker-environment") >= 2


def test_deployment_owned_settings_are_not_offered_as_ui_settings():
    """A UI-editable `spool_dir` would point the container at an unmapped path.

    Same class of mistake as the TLS port: the value has to match the compose
    mapping / the mounted volume, so it must not be changeable at runtime.
    """
    from mwl_broker import settings_service

    for key in sorted(DEPLOYMENT_OWNED):
        assert key in settings_service.KNOWN, f"{key} is not a setting any more"
        assert key in settings_service.DEPLOYMENT_ONLY, (
            f"{key} is deployment-owned but the API would still let the UI change it"
        )


def test_the_api_refuses_to_change_a_deployment_owned_setting(client):
    """`spool_dir` in the UI would send images to the ephemeral container disk.

    The spool volume is mounted at a fixed path; a runtime change would keep the
    broker "working" while every buffered image is lost on the next restart —
    the exact opposite of what the spool promises.
    """
    settings = client.get("/api/v1/settings").json()
    by_key = {entry["key"]: entry for entry in settings}

    assert by_key["spool_dir"]["editable"] is False
    assert by_key["tls_inbound_port"]["editable"] is False
    assert by_key["echo_interval_s"]["editable"] is True

    refused = client.put("/api/v1/settings/spool_dir", json={"value": "/tmp/spool"})
    assert refused.status_code == 409
    assert "deployment" in refused.json()["detail"]

    # a normal setting still works
    assert client.put("/api/v1/settings/echo_interval_s",
                      json={"value": "45"}).status_code == 200


def test_settings_that_need_a_restart_say_so(client):
    """A switch that looks immediate and silently does nothing is worse than no
    switch.

    `mpps_enabled`, the TLS listener and the MLLP listener are read **once**
    while the process starts (the SCP builds its presentation contexts, the
    listener opens its socket / starts its thread). The API has to mark them so
    the UI can say "after a restart".
    """
    rows = {row["key"]: row for row in client.get("/api/v1/settings").json()}

    for key in ("mpps_enabled",
                "tls_inbound_enabled", "tls_inbound_cert_file", "tls_inbound_key_file",
                "tls_inbound_ca_file", "tls_inbound_client_auth",
                "hl7_mllp_enabled", "hl7_mllp_bind", "hl7_mllp_port"):
        assert rows[key]["restart_required"] is True, f"{key} needs a restart"


def test_settings_that_apply_immediately_are_not_marked(client):
    """The other direction: a flag on everything would be as useless as none."""
    rows = {row["key"]: row for row in client.get("/api/v1/settings").json()}

    for key in ("spool_enabled", "cache_enabled", "echo_interval_s", "rbac_mode",
                "retention_query_log_days", "prefetch_max_concurrency",
                "notify_webhook_url", "atna_enabled"):
        assert rows[key]["restart_required"] is False, f"{key} applies immediately"


def test_every_restart_required_setting_exists(client):
    """A typo in the list would silently mark nothing."""
    from mwl_broker import settings_service

    assert settings_service.RESTART_REQUIRED <= set(settings_service.KNOWN)
    assert settings_service.RESTART_REQUIRED  # not empty by accident
