from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from medguide.domain.models import CollectionRun, Guideline, IngestionJob, Source
from medguide.infrastructure.settings import Settings
from medguide.scrapers.registry import SourceDefinition


class SourceRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory

    def ensure(self, definitions: Iterable[SourceDefinition], settings: Settings) -> list[str]:
        """Insert missing defaults, preserving every field of existing sources."""
        created = []
        with self.factory.begin() as session:
            for definition in definitions:
                if session.scalar(select(Source.id).where(Source.code == definition.code)):
                    continue
                try:
                    with session.begin_nested():
                        session.add(
                            Source(
                                code=definition.code,
                                connector_key=definition.connector_key,
                                base_url=definition.base_url,
                                enabled=definition.default_enabled,
                                discovery_interval=settings.discovery_interval,
                                content_recheck_interval=settings.content_recheck_interval,
                            )
                        )
                        session.flush()
                    created.append(definition.code)
                except IntegrityError:
                    # A concurrent bootstrap may have inserted this code while we waited.
                    if (
                        session.scalar(select(Source.id).where(Source.code == definition.code))
                        is None
                    ):
                        raise
        return created

    def by_code(self, code: str) -> Source | None:
        with self.factory() as session:
            return session.scalar(select(Source).where(Source.code == code))

    def all(self) -> list[Source]:
        with self.factory() as session:
            return list(session.scalars(select(Source).order_by(Source.code)))

    def set_enabled(self, code: str, enabled: bool) -> Source | None:
        with self.factory.begin() as session:
            source = session.scalar(select(Source).where(Source.code == code).with_for_update())
            if source:
                source.enabled = enabled
            return source

    def status(self, source_id: str) -> dict[str, Any]:
        with self.factory() as session:
            latest = session.scalar(
                select(CollectionRun)
                .where(CollectionRun.source_id == source_id)
                .order_by(CollectionRun.started_at.desc())
                .limit(1)
            )
            counts = dict(
                session.execute(
                    select(IngestionJob.status, func.count())
                    .join(Guideline, IngestionJob.guideline_id == Guideline.id)
                    .where(Guideline.source_id == source_id)
                    .group_by(IngestionJob.status)
                ).all()
            )
            return {
                "latest_run": None
                if latest is None
                else {
                    "id": latest.id,
                    "status": latest.status,
                    "started_at": latest.started_at,
                    "finished_at": latest.finished_at,
                    "found_count": latest.found_count,
                    "queued_count": latest.queued_count,
                    "error": latest.error_summary,
                },
                "jobs_by_status": {
                    status: counts.get(status, 0)
                    for status in ("PENDING", "PROCESSING", "COMPLETED", "FAILED", "NEEDS_REVIEW")
                },
            }
