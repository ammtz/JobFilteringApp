"""
Pytest fixtures for Flask-based testing.
Integration tests use a DB session that rolls back after each test.
Set DATABASE_URL to a Postgres URL to run integration tests.
"""
from collections.abc import Generator
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.main import app as flask_app


def _is_postgres(url: str) -> bool:
    return "postgresql" in (url or "").split(":")[0].lower()


@pytest.fixture(scope="session")
def engine():
    return create_engine(settings.DATABASE_URL)


@pytest.fixture(scope="session")
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def db_session(session_factory, engine) -> Generator[Session, None, None]:
    """Session that rolls back after each test. Requires Postgres."""
    if not _is_postgres(settings.DATABASE_URL):
        pytest.skip("Integration tests require Postgres DATABASE_URL")
    connection = engine.connect()
    transaction = connection.begin()
    session = session_factory(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Flask test client with get_db monkey-patched to use rolling-back session."""
    import app.core.database as db_module

    original_get_db = db_module.get_db

    @contextmanager
    def override_get_db():
        yield db_session

    db_module.get_db = override_get_db
    flask_app.config["TESTING"] = True
    try:
        with flask_app.test_client() as c:
            yield c
    finally:
        db_module.get_db = original_get_db


@pytest.fixture
def client_no_db():
    """Test client without DB override. Use for e2e when DB is available."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c
