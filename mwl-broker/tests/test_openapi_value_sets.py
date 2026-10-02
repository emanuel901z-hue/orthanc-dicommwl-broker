"""Every declared value set matches the constants the code produces.

A `Literal` on a **response** model is a promise to the caller — and a trap for the
service: a value outside the set makes FastAPI raise `ResponseValidationError`, so
the operator sees a 500 for data that is perfectly fine. The sets were prose in
descriptions before ("queued | failed | dead | sent"), which meant the OpenAPI
document did not carry them and Swagger could not show a dropdown.

So each set is compared with the module that produces it: a new constant fails
this test instead of turning into a 500 in the field.

Two sets stay prose on purpose and are listed at the bottom with the reason.
"""
import pytest

from mwl_broker import adt, audit, breaker, health_checks, mpps, notify, rbac, spool
from mwl_broker.main import app

SCHEMAS = app.openapi()["components"]["schemas"]


def enum_of(schema: str, field: str) -> set[str]:
    """The declared values of one response field."""
    properties = SCHEMAS[schema]["properties"]
    assert field in properties, f"{schema}.{field} does not exist"
    values = properties[field].get("enum")
    assert values is not None, (
        f"{schema}.{field} declares no value set — the allowed values belong in the "
        "schema, not only in the description text"
    )
    return set(values)


def enum_of_parameter(path: str, method: str, name: str) -> set[str]:
    """The declared values of one query parameter."""
    for parameter in app.openapi()["paths"][path][method].get("parameters", []):
        if parameter["name"] == name:
            values = parameter["schema"].get("enum")
            assert values is not None, f"{method} {path} :: {name} declares no value set"
            return set(values)
    raise AssertionError(f"{method} {path} has no parameter {name}")


def test_the_state_of_a_breaker_is_closed():
    assert enum_of("BreakerStateOut", "state") == {
        breaker.STATE_CLOSED, breaker.STATE_HALF_OPEN, breaker.STATE_OPEN,
    }


def test_the_step_statuses_match_the_protocol_values():
    assert enum_of("MppsStepOut", "status") == set(mpps.STATUSES)
    # the query filter offers the same values plus "all"
    assert enum_of_parameter("/api/v1/mpps", "get", "status") == {"", *mpps.STATUSES}


def test_the_access_modes_match():
    assert enum_of("RbacStatusOut", "mode") == {rbac.MODE_OFF, rbac.MODE_ENFORCE}


def test_every_spool_status_the_table_can_hold_is_declared():
    assert enum_of("SpoolItemOut", "status") == {
        spool.STATUS_QUEUED, spool.STATUS_CLAIMED, spool.STATUS_SENT,
        spool.STATUS_FAILED, spool.STATUS_DEAD,
    }


def test_the_severities_match_the_finding_and_event_tables():
    assert enum_of("FindingOut", "severity") == set(health_checks.SEVERITY_ORDER)
    assert enum_of("NotifyEventOut", "severity") == {
        severity for severity, _description in notify.EVENTS.values()
    }


# Every entity value `audit.record(...)` writes. The set is bigger than
# `audit.SERIALIZERS`: cache, tls, spool, mpps_step, hl7_message, hl7_field_map,
# merge_rule, patient_merge and prefetch appear in the change log without being
# rollbackable — the first version of this test took SERIALIZERS and the missing
# `patient_merge` turned `GET /audit/config` into a 500 for those rows.
AUDITED_ENTITIES = {
    "source", "target", "station", "rule", "transform", "setting", "local_item",
    "ups_subscription", "cache", "hl7_field_map", "hl7_message", "merge_rule",
    "mpps_step", "patient_merge", "prefetch", "spool", "tls",
}


def test_the_entities_cover_everything_the_change_log_records():
    assert enum_of("AuditEntryOut", "entity") == AUDITED_ENTITIES
    assert enum_of("ImportChangeOut", "entity") == AUDITED_ENTITIES
    # the serialisers are the *rollbackable* subset — they have to be part of it
    assert set(audit.SERIALIZERS) <= AUDITED_ENTITIES


def test_the_patient_actions_match_the_adt_module():
    assert enum_of("Hl7AdtOut", "action") == {
        value for name, value in vars(adt).items()
        if name.startswith("ACTION_") and isinstance(value, str)
    }


def test_the_small_fixed_sets_are_declared():
    assert enum_of("TlsOverviewOut", "inbound_client_auth") == {"none", "optional", "required"}
    assert enum_of("AtnaStatsOut", "protocol") == {"tcp", "tls"}
    assert enum_of("StatsOut", "group_by") == {"source", "modality", "station"}
    assert enum_of("RollbackOut", "action") == {"delete", "recreate", "restore"}
    assert enum_of("SimulateRouteOut", "matched_via") == {
        "accession", "study_uid", "default", "none",
    }
    assert enum_of("SimulateTransformOut", "matched_via") == {
        "accession", "study_uid", "default", "none",
    }
    assert enum_of("ImportChangeOut", "action") == {"create", "update"}


@pytest.mark.parametrize("schema,field,reason", [
    ("SettingOut", "kind", "carries its choices inline: enum:<a,b>"),
    ("Hl7MessageDetailOut", "transport", "replay:<transport> — an open suffix"),
    ("GdtParseOut", "action", "documented with 'e.g.' — the set is not closed"),
    ("QueryLogOut", "status", "compound wording ('partial (a source failed …)')"),
    ("StoreLogOut", "status", "compound wording"),
    ("WorklistPreviewOut", "status", "compound wording"),
])
def test_the_open_sets_stay_prose(schema, field, reason):
    """The other direction: a set that is *not* closed must not claim to be."""
    values = SCHEMAS[schema]["properties"][field].get("enum")
    assert values is None, (
        f"{schema}.{field} now has a fixed set ({values}) — remove it from this list "
        f"and check the code ({reason})"
    )
