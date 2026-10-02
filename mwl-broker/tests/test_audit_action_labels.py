"""Every change-log action needs a label in the UI.

The audit page renders `t('broker.action_<action>', { defaultValue: action })` —
an action without a translation shows the operator the **raw code** in the change
log ("update.setting" instead of "Setting changed"). Exactly that was reported
from a running installation.

The list is read from the code (AST), so a new `audit.record(..., "<action>", …)`
cannot slip through. Actions built with an f-string (`f"patient.{result['action']}"`)
are expanded from the values the code can actually produce — and the expansion is
checked against the source, so it cannot rot into a list nobody uses.
"""
import ast
import json
import re
from pathlib import Path

import pytest

from mwl_broker import adt

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1] / "mwl_broker"
OE3 = ROOT / "orthanc-explorer-3-usable"
LOCALES = ("en", "de")


def _record_calls() -> list[ast.Call]:
    calls: list[ast.Call] = []
    for path in BACKEND.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            # audit.record(session, actor, action, entity, …)
            if name == "record" and len(node.args) >= 3:
                calls.append(node)
    return calls


def _crud_kinds() -> set[str]:
    """The `kind` values the CRUD helper is registered with (create.<kind> …)."""
    kinds = set()
    for path in BACKEND.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name != "_crud":
                continue
            literals = [a.value for a in node.args if isinstance(a, ast.Constant)
                        and isinstance(a.value, str)]
            if literals:
                kinds.add(literals[-1])
    return kinds


def _source_text() -> str:
    return "\n".join(path.read_text() for path in BACKEND.glob("*.py"))


def audited_actions() -> set[str]:
    """Every action string an `audit.record` call can write."""
    actions: set[str] = set()
    for call in _record_calls():
        arg = call.args[2]
        if isinstance(arg, ast.Constant):
            actions.add(str(arg.value))
        elif isinstance(arg, ast.JoinedStr):
            # an f-string without a placeholder (`f"hl7.reprocess"`) is a literal
            if not any(isinstance(v, ast.FormattedValue) for v in arg.values):
                actions.add("".join(v.value for v in arg.values if isinstance(v, ast.Constant)))
                continue
            prefix = "".join(v.value for v in arg.values if isinstance(v, ast.Constant))
            actions |= _expand(prefix)
    return actions


def _expand(prefix: str) -> set[str]:
    """Concrete actions behind an f-string prefix, verified against the source."""
    source = _source_text()
    if prefix in ("create.", "update.", "delete."):
        return {prefix + kind for kind in _crud_kinds()}
    if prefix == "rollback.":
        from mwl_broker import audit

        return {prefix + entity for entity in audit.SERIALIZERS}
    if prefix == "patient.":
        values = {value for name, value in vars(adt).items()
                  if name.startswith("ACTION_") and isinstance(value, str)}
        values.discard(adt.ACTION_NA)          # not applied, so never recorded
        # the merge API records the *kind* it created (`f"patient.{row['kind']}"`),
        # which is not an ADT action — the audit page showed "patient.merge" raw
        kinds = {"merge", "link"}
        for kind in kinds:
            assert f'"{kind}"' in source, (
                f"patient.{kind} is not produced any more — update this expansion")
        return {prefix + value for value in values | kinds}
    if prefix in ("hl7.", "gdt."):
        # the HL7 intake can cancel (ORC-1 CA/OC) and refuse; the GDT record has
        # no order control — `gdt.parse` always reports "NW", so it only ever
        # creates or updates
        values = ({"created", "updated", "cancelled", "cancel-unknown", "rejected"}
                  if prefix == "hl7." else {"created", "updated"})
        # the expansion has to match what the code produces — otherwise this
        # test would happily check a list nobody writes any more
        for value in values:
            assert f'"{value}"' in source, (
                f"{prefix}{value} is not produced by the backend any more — "
                "update this expansion")
        return {prefix + value for value in values}
    raise AssertionError(
        f"audit.record uses the f-string prefix {prefix!r} — teach this test how "
        "to expand it, otherwise its actions have no label check")


def _locale(language: str) -> dict:
    path = OE3 / "src" / "i18n" / "locales" / f"{language}.json"
    return json.loads(path.read_text())["broker"]


@pytest.mark.skipif(not OE3.is_dir(),
                    reason="the OE3 fork is a submodule — not checked out here")
def test_the_action_list_is_not_empty():
    """A silent AST scan (e.g. after a rename) must not make the check useless."""
    assert len(audited_actions()) >= 50


@pytest.mark.skipif(not OE3.is_dir(),
                    reason="the OE3 fork is a submodule — not checked out here")
@pytest.mark.parametrize("language", LOCALES)
def test_every_audited_action_has_a_label(language):
    keys = _locale(language)
    missing = sorted(action for action in audited_actions()
                     if f"action_{action.replace('.', '_')}" not in keys)
    assert not missing, (
        f"{language}: change-log actions without a UI label: {missing} — "
        "the audit page would show the raw code"
    )


@pytest.mark.skipif(not OE3.is_dir(),
                    reason="the OE3 fork is a submodule — not checked out here")
@pytest.mark.parametrize("language", LOCALES)
def test_no_action_label_without_a_code(language):
    """A label for an action nobody writes is a leftover, not a feature."""
    keys = _locale(language)
    known = {f"action_{action.replace('.', '_')}" for action in audited_actions()}
    orphans = sorted(key for key in keys
                     if key.startswith("action_") and key not in known)
    assert not orphans, f"{language}: labels without an action: {orphans}"


def test_the_ui_never_prints_a_raw_action():
    """The page has to go through the key helper, not interpolate the code."""
    source = (OE3 / "src" / "features" / "broker" / "pages" / "AuditPage.tsx").read_text()
    assert "auditActionKey" in source
    # a bare `{entry.action}` / `{detail.action}` is exactly the bug that was
    # reported from a running installation
    assert not re.search(r"\{\s*(entry|detail|rollbackTarget)\.action\s*\}", source)
