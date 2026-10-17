from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from medguide.infrastructure.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def session_factory() -> sessionmaker[Session]:
    return sessionmaker(get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with session_factory()() as session:
        yield session
