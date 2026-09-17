import os
import shutil
from pathlib import Path

os.environ["BROKER_DATABASE_URL"] = "sqlite:///./test_mwl.db"
os.environ["BROKER_START_DICOM"] = "false"
os.environ["BROKER_START_ECHO_LOOP"] = "false"
os.environ["BROKER_START_SPOOL"] = "false"   # the worker is driven explicitly in tests
os.environ["BROKER_START_ATNA"] = "false"    # the ATNA drain worker is driven explicitly
# a writable spool directory (the production default lives under /var/lib)
SPOOL_DIR = Path(__file__).resolve().parent.parent / ".pytest-spool"
os.environ["BROKER_SPOOL_DIR"] = str(SPOOL_DIR)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_echo_state():
    """Echo status and alert de-bounce live in module globals — reset per test."""
    from mwl_broker import atna, echo, notify

    echo.reset_for_tests()
    notify.reset_for_tests()
    atna.reset_for_tests()
    yield
    echo.reset_for_tests()
    notify.reset_for_tests()
    atna.reset_for_tests()


@pytest.fixture(autouse=True)
def fresh_spool():
    """Spooled payloads must not leak between tests."""
    from mwl_broker import spool

    shutil.rmtree(SPOOL_DIR, ignore_errors=True)
    yield
    spool.reset_for_tests()
    shutil.rmtree(SPOOL_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def fresh_db():
    from mwl_broker import db
    from mwl_broker.models import Base

    db.reset_for_tests()
    engine = db.get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    db.reset_for_tests()


@pytest.fixture()
def client():
    """FastAPI test client with the app's lifespan (seed + SCP off in tests)."""
    from fastapi.testclient import TestClient

    from mwl_broker.main import create_app

    with TestClient(create_app()) as c:
        yield c
