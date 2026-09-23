"""Every entity the change log can carry needs a label in the UI.

The audit page renders `t('broker.entity_<entity>')` — an entity without a
translation shows the operator a **raw key** like `broker.entity_patient_merge`
in the change log. The screenshot walk over the deployment found exactly that
(`broker-audit-mobile: keine Rohschlüssel`), after four entities had been added
over time without their label: the PIR merge, the field merge rules, the MPPS
steps and the HL7 field map.

The list of entities is read from the code itself (AST), so a new
`audit.record(..., "<entity>", ...)` cannot slip through unnoticed.
"""
import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1] / "mwl_broker"
OE3 = ROOT / "orthanc-explorer-3-usable"
LOCALES = ("en", "de")          # the reference languages; the rest fall back to English


def audited_entities() -> set[str]:
    """Every string passed as the `entity` argument of an `audit.record` call."""
    entities: set[str] = set()
    for path in BACKEND.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name != "record":
                continue
            # audit.record(session, actor, action, entity, entity_id, ...)
            if len(node.args) >= 4 and isinstance(node.args[3], ast.Constant):
                entities.add(str(node.args[3].value))
            for keyword in node.keywords:
                if keyword.arg == "entity" and isinstance(keyword.value, ast.Constant):
                    entities.add(str(keyword.value.value))
    return entities


def _locale(language: str) -> dict:
    path = OE3 / "src" / "i18n" / "locales" / f"{language}.json"
    return json.loads(path.read_text())["broker"]


@pytest.mark.skipif(not OE3.is_dir(),
                    reason="the OE3 fork is a submodule — not checked out here")
def test_the_entity_list_is_not_empty():
    """A silent AST scan (e.g. after a rename) must not make the check useless."""
    assert len(audited_entities()) >= 10


@pytest.mark.skipif(not OE3.is_dir(),
                    reason="the OE3 fork is a submodule — not checked out here")
@pytest.mark.parametrize("language", LOCALES)
def test_every_audited_entity_has_a_label(language):
    keys = _locale(language)
    missing = sorted(entity for entity in audited_entities()
                     if f"entity_{entity}" not in keys)
    assert not missing, (
        f"{language}: change-log entities without a UI label: {missing} — "
        "the audit page would show the raw key"
    )
