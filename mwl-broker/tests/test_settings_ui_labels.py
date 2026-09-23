"""Every setting the API exposes needs a label in the UI.

The settings page renders `t('broker.setting_<key>', { defaultValue: <key> })` —
a setting without a translation shows the **raw key** ("spool_lease_s") to the
operator, which is exactly what a novice-safe interface must not do. The
description falls back to the API's English text, the label does not.

Found by comparing the running API (72 settings) with the locale files: 15 had no
label — the high-availability settings added in B1 among them, plus the MPPS and
HL7 ones. The check below keeps that from happening again.
"""
import json
from pathlib import Path

import pytest

from mwl_broker import settings_service

ROOT = Path(__file__).resolve().parents[2]
OE3 = ROOT / "orthanc-explorer-3-usable"
LOCALES = ("en", "de")          # the reference languages; the rest fall back to English


def _locale(language: str) -> dict:
    path = OE3 / "src" / "i18n" / "locales" / f"{language}.json"
    return json.loads(path.read_text())["broker"]


@pytest.mark.skipif(not OE3.is_dir(),
                    reason="the OE3 fork is a submodule — not checked out here")
def test_every_setting_has_a_label_and_a_description():
    keys = sorted(settings_service.KNOWN)
    assert len(keys) > 50, "the settings table looks wrong"

    for language in LOCALES:
        broker = _locale(language)
        missing_label = [key for key in keys if f"setting_{key}" not in broker]
        missing_desc = [key for key in keys if f"settingDesc_{key}" not in broker]

        assert not missing_label, (
            f"{language}: these settings would show their raw key: {missing_label}")
        assert not missing_desc, (
            f"{language}: these settings have no description: {missing_desc}")


@pytest.mark.skipif(not OE3.is_dir(),
                    reason="the OE3 fork is a submodule — not checked out here")
def test_the_locales_have_no_settings_the_backend_does_not_know():
    """A label for a setting that no longer exists is a leftover, not a feature."""
    known = set(settings_service.KNOWN)
    for language in LOCALES:
        broker = _locale(language)
        orphans = sorted(
            key[len("setting_"):] for key in broker
            if key.startswith("setting_") and not key.startswith("settingDesc_")
            and key[len("setting_"):] not in known
        )
        assert not orphans, f"{language}: labels without a setting: {orphans}"
