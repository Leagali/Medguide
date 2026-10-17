import logging
import time
from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from medguide.domain.models import CollectionRun, IngestionJob, Source
from medguide.infrastructure.errors import LeaseLost, PipelineError
from medguide.infrastructure.storage import RawStorage
from medguide.ingestion.text import content_hash, extract
from medguide.repositories.pipeline import PipelineRepository
from medguide.scrapers.contracts import DiscoveredGuideline, SourceScraper

logger = logging.getLogger(__name__)


def classify(error: Exception) -> PipelineError:
    if isinstance(error, PipelineError):
        return error
    if isinstance(error, (OSError, SQLAlchemyError)):
        return PipelineError(type(error).__name__.upper(), transient=True)
    if isinstance(error, ValidationError):
        return PipelineError("CONTRACT_INVALID")
    return PipelineError(f"UNEXPECTED_{type(error).__name__.upper()}")


class IngestionService:
    def __init__(
        self,
        repository: PipelineRepository,
        storage: RawStorage,
        scraper_factory: Callable[[Source], SourceScraper],
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.scraper_factory = scraper_factory

    def discover(self, run_id: str) -> list[str]:
        token = self.repository.claim(CollectionRun, run_id)
        if token is None:
            return []
        started = time.monotonic()
        try:
            source = self.repository.run_source(run_id)
            items = self.scraper_factory(source).discover()
            validated = [
                DiscoveredGuideline.model_validate(item.model_dump(mode="json")) for item in items
            ]
            result = self.repository.complete_discovery(run_id, token, validated)
            logger.info(
                "discovery_completed",
                extra={
                    "context": {
                        "collection_run_id": run_id,
                        "source_id": source.id,
                        "source_code": source.code,
                        "stage": "DISCOVERY",
                        "found_count": len(items),
                        "queued_count": len(result),
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    }
                },
            )
            return result
        except LeaseLost:
            return []
        except Exception as exc:
            error = classify(exc)
            try:
                self.repository.fail(CollectionRun, run_id, token, "DISCOVERY", error)
            except LeaseLost:
                pass
            logger.warning(
                "discovery_failed",
                extra={
                    "context": {
                        "collection_run_id": run_id,
                        "stage": "DISCOVERY",
                        "error_code": error.code,
                    }
                },
            )
            return []

    def ingest(self, job_id: str) -> str:
        token = self.repository.claim(IngestionJob, job_id)
        if token is None:
            return "IGNORED"
        stage, started = "FETCH", time.monotonic()
        try:
            source, candidate = self.repository.job_context(job_id)
            documents = self.scraper_factory(source).fetch_documents(candidate)
            expected = {ref.reference_key: ref.role for ref in candidate.document_refs}
            if (
                len(documents) != len(expected)
                or {d.reference_key: d.role for d in documents} != expected
            ):
                raise PipelineError("DOCUMENT_REFERENCES_MISMATCH")
            stored = []
            # Commit every original before extraction. A parser failure never loses the RAW.
            for document in documents:
                if len(document.data) > self.repository.settings.max_download_bytes:
                    raise PipelineError("DOWNLOAD_TOO_LARGE")
                key, raw_hash = self.storage.put(document.data)
                artifact_id = self.repository.save_raw(job_id, token, document, key, raw_hash)
                stored.append((artifact_id, document))
            for artifact_id, document in stored:
                stage = "EXTRACT"
                extracted = extract(document.data, document.media_type)
                stage = "NORMALIZE"
                sha256 = content_hash(extracted)
                self.repository.save_extraction(job_id, token, artifact_id, extracted, sha256)
            stage = "PERSIST"
            result = self.repository.complete_ingestion(job_id, token, [a for a, _ in stored])
            logger.info(
                "ingestion_completed",
                extra={
                    "context": {
                        "ingestion_job_id": job_id,
                        "source_id": source.id,
                        "source_code": source.code,
                        "guideline_external_key": candidate.external_key,
                        "stage": stage,
                        "result": result,
                        "size_bytes": sum(len(d.data) for _, d in stored),
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    }
                },
            )
            return result
        except LeaseLost:
            return "LEASE_LOST"
        except Exception as exc:
            error = classify(exc)
            try:
                self.repository.fail(IngestionJob, job_id, token, stage, error)
            except LeaseLost:
                return "LEASE_LOST"
            logger.warning(
                "ingestion_failed",
                extra={
                    "context": {
                        "ingestion_job_id": job_id,
                        "stage": stage,
                        "error_code": error.code,
                    }
                },
            )
            return error.code
