"""The support and training documents must match the system they describe.

A support concept that names an alert nobody fires, a runbook chapter that was
renamed, or a help page that no longer exists is worse than no document: it is
what an operator follows at 3 a.m. and what a tender is judged against. These
checks bind the two new documents to the code:

* every alert in `support-and-sla.md` exists in the rules file — and every rule
  in the file is covered by the table,
* every `runbook.md#anchor` link (in all documents) resolves to a real heading,
* every script the documents tell someone to run exists,
* every help page listed in `training.md` really has its text in the UI.
"""
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
RULES = ROOT / "deploy" / "monitoring" / "prometheus-rules.yml"
OE3 = ROOT / "orthanc-explorer-3-usable"

SUPPORT = DOCS / "support-and-sla.md"
TRAINING = DOCS / "training.md"


def _slug(heading: str) -> str:
    """GitHub's heading anchor: lower case, punctuation away, spaces to hyphens."""
    text = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return text.strip().replace(" ", "-")


def _headings(path: Path) -> set[str]:
    return {_slug(match.group(1))
            for match in re.finditer(r"^#{1,6}\s+(.+)$", path.read_text(), re.M)}


def _anchors(text: str) -> list[tuple[str, str]]:
    """All `file.md#anchor` links in a document."""
    return re.findall(r"\]\(([\w.\-]+\.md)#([^)\s]+)\)", text)


# ── Alarme ────────────────────────────────────────────────────────────────


def test_every_alert_in_the_support_concept_really_exists():
    documented = set(re.findall(r"`(MWL[A-Za-z]+)`", SUPPORT.read_text()))
    real = {rule["alert"] for group in yaml.safe_load(RULES.read_text())["groups"]
            for rule in group["rules"]}

    assert documented, "the support concept names no alert at all"
    assert documented <= real, f"documented but not configured: {documented - real}"


def test_the_support_concept_covers_every_rule():
    """A rule nobody reacts to is a rule nobody needs."""
    documented = set(re.findall(r"`(MWL[A-Za-z]+)`", SUPPORT.read_text()))
    real = {rule["alert"] for group in yaml.safe_load(RULES.read_text())["groups"]
            for rule in group["rules"]}

    assert real <= documented, f"configured but undocumented: {real - documented}"


# ── Runbook-Anker ─────────────────────────────────────────────────────────


def test_every_runbook_link_points_at_a_real_chapter():
    """Renaming a chapter must not leave links pointing into nowhere."""
    runbook = DOCS / "runbook.md"
    headings = _headings(runbook)
    broken: list[str] = []

    for document in sorted(DOCS.glob("*.md")) + [ROOT / "README.md"]:
        for target, anchor in _anchors(document.read_text()):
            if target != "runbook.md":
                continue
            if anchor not in headings:
                broken.append(f"{document.name} → runbook.md#{anchor}")

    assert not broken, "links to runbook chapters that do not exist:\n  " + "\n  ".join(broken)


def test_every_anchor_in_the_whole_documentation_resolves():
    """Same check for all documents — cross-references drift silently."""
    broken: list[str] = []
    for document in sorted(DOCS.glob("*.md")) + [ROOT / "README.md"]:
        for target, anchor in _anchors(document.read_text()):
            other = document.parent / target
            if not other.is_file():
                broken.append(f"{document.name} → {target} (file missing)")
                continue
            if anchor not in _headings(other):
                broken.append(f"{document.name} → {target}#{anchor}")
    assert not broken, "unresolvable links:\n  " + "\n  ".join(broken)


# ── Skripte ───────────────────────────────────────────────────────────────


def test_every_script_the_documents_tell_you_to_run_exists():
    scripts: set[str] = set()
    for document in (SUPPORT, TRAINING, DOCS / "runbook.md", DOCS / "ha.md"):
        scripts |= set(re.findall(r"\./((?:deploy/)?[\w.\-]+\.sh)", document.read_text()))
        scripts |= set(re.findall(r"(mwl-broker/scripts/[\w.\-]+\.py)", document.read_text()))

    assert scripts, "the documents mention no script at all"
    missing = [script for script in sorted(scripts) if not (ROOT / script).is_file()]
    assert not missing, f"documented but not there: {missing}"


# ── Hilfeseiten der Oberfläche ────────────────────────────────────────────


@pytest.mark.skipif(not OE3.is_dir(),
                    reason="the OE3 fork is a submodule — not checked out here")
def test_the_training_document_lists_every_help_page():
    """The ten help pages are a training asset — the list has to be complete."""
    listed = set(re.findall(r"`(overview|sources|targets|rules|transforms|stations|"
                            r"worklist|spool|audit|settings)`", TRAINING.read_text()))
    in_ui = set()
    for path in (OE3 / "src" / "features" / "broker").rglob("*.tsx"):
        if path.name.endswith(".test.tsx"):
            continue
        in_ui |= set(re.findall(r'helpId="([\w-]+)"', path.read_text()))

    assert in_ui, "no help page found in the UI"
    assert in_ui <= listed, f"help pages missing from the training document: {in_ui - listed}"

    # …and each of them really carries text (not just an empty placeholder)
    texts = json.loads((OE3 / "src" / "i18n" / "locales" / "en.json").read_text())["broker"]
    for page in sorted(in_ui):
        assert f"help_{page}_title" in texts, f"help_{page}_title is missing in en.json"
        assert f"help_{page}_what" in texts, f"help_{page}_what is missing in en.json"
