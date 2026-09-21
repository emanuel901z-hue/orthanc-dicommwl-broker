"""mwl_broker — DICOM MWL proxy/aggregator + C-STORE router for Orthanc."""

def _detect_version() -> str:
    """The version of the code that is actually running.

    `pyproject.toml` wins over the installed distribution metadata: an editable
    install (or a container built before a version bump) keeps stale metadata,
    and then the broker would report a version it is not running.
    """
    from pathlib import Path

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject.is_file():
        for line in pyproject.read_text().splitlines():
            if line.startswith("version"):
                return line.split("=", 1)[1].strip().strip('"\'')
    try:
        from importlib.metadata import version

        return version("mwl-broker")
    except Exception:  # no metadata and no source tree
        return "0.0.0"


__version__ = _detect_version()
