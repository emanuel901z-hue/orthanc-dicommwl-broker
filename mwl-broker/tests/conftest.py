import os

os.environ["BROKER_DATABASE_URL"] = "sqlite:///./test_mwl.db"
os.environ["BROKER_START_DICOM"] = "false"
os.environ["BROKER_START_ECHO_LOOP"] = "false"

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_echo_state():
    """The echo status lives in a module global — reset it per test."""
    from mwl_broker import echo

    echo.reset_for_tests()
    yield
    echo.reset_for_tests()


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
