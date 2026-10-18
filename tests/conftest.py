import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from medguide.domain.models import Base, Guideline
from medguide.infrastructure.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        storage_root=tmp_path / "raw",
        request_interval=0,
        admin_token="request-test-token",
        redis_url="redis://localhost:6379/15",
    )


@pytest.fixture
def db():
    url = os.getenv("TEST_DATABASE_URL", "sqlite://")
    options = (
        {}
        if url.startswith("postgresql")
        else {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    )
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    with engine.begin() as connection:
        connection.execute(update(Guideline).values(current_version_id=None))
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / "fixtures"
