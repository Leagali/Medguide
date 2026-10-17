from collections.abc import Callable
from dataclasses import replace
from typing import Any

from medguide.domain.models import Source
from medguide.infrastructure.db import session_factory
from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.settings import Settings, get_settings
from medguide.repositories.pipeline import PipelineRepository
from medguide.repositories.sources import SourceRepository
from medguide.scrapers.registry import SCRAPER_REGISTRY, SOURCE_DEFINITIONS
from medguide.workers.publishing import publish


class SourceService:
    def __init__(
        self,
        sources: SourceRepository,
        pipeline: PipelineRepository,
        settings: Settings,
        publisher: Callable[[PipelineRepository, str, str], bool],
    ) -> None:
        self.sources, self.pipeline, self.settings = sources, pipeline, settings
        self.publisher = publisher

    def bootstrap(self) -> list[str]:
        return self.sources.ensure(SOURCE_DEFINITIONS.values(), self.settings)

    @staticmethod
    def describe(source: Source) -> dict[str, Any]:
        definition = SOURCE_DEFINITIONS.get(source.code)
        return {
            "code": source.code,
            "name": definition.name if definition else source.code,
            "registered": True,
            "enabled": source.enabled,
            "next_due_at": source.next_due_at,
            "discovery_interval": source.discovery_interval,
            "content_recheck_interval": source.content_recheck_interval,
        }

    def list(self) -> list[dict[str, Any]]:
        result = {source.code: self.describe(source) for source in self.sources.all()}
        for code, definition in SOURCE_DEFINITIONS.items():
            result.setdefault(
                code,
                {
                    "code": code,
                    "name": definition.name,
                    "registered": False,
                    "enabled": None,
                    "next_due_at": None,
                },
            )
        return [result[code] for code in sorted(result)]

    def require(self, code: str, *, register: bool = False) -> Source:
        source = self.sources.by_code(code)
        if source is None and code in SOURCE_DEFINITIONS:
            if not register:
                raise PipelineError("SOURCE_NOT_REGISTERED")
            self.sources.ensure([SOURCE_DEFINITIONS[code]], self.settings)
            source = self.sources.by_code(code)
        if source is None:
            raise PipelineError("UNKNOWN_SOURCE")
        if source.connector_key not in SCRAPER_REGISTRY:
            raise PipelineError("UNKNOWN_CONNECTOR")
        return source

    def set_enabled(self, code: str, enabled: bool) -> dict[str, Any]:
        if self.sources.by_code(code) is None and code in SOURCE_DEFINITIONS:
            # Disabling an unregistered default must never make it briefly schedulable.
            self.sources.ensure(
                [replace(SOURCE_DEFINITIONS[code], default_enabled=enabled)], self.settings
            )
        self.require(code)
        source = self.sources.set_enabled(code, enabled)
        assert source is not None
        return self.describe(source)

    def run(self, code: str) -> dict[str, Any]:
        source = self.require(code, register=True)
        if not source.enabled:
            raise PipelineError("SOURCE_DISABLED")
        reservation = self.pipeline.reserve_run_details(source.id)
        if reservation is None:
            raise PipelineError("SOURCE_DISABLED")
        run_id, reused = reservation
        published = self.publisher(self.pipeline, "discover_source", run_id)
        return {"code": code, "run_id": run_id, "reused": reused, "published": published}

    def status(self, code: str) -> dict[str, Any]:
        source = self.require(code)
        return {**self.describe(source), **self.sources.status(source.id)}


def build_service() -> SourceService:
    factory, settings = session_factory(), get_settings()
    return SourceService(
        SourceRepository(factory), PipelineRepository(factory, settings), settings, publish
    )
