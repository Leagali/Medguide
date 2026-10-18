from celery.signals import setup_logging
from redis import Redis

from medguide.infrastructure.db import session_factory
from medguide.infrastructure.http import SafeHttpClient
from medguide.infrastructure.observability import configure_logging
from medguide.infrastructure.settings import get_settings
from medguide.infrastructure.storage import FileStorage
from medguide.ingestion.service import IngestionService
from medguide.repositories.pipeline import PipelineRepository
from medguide.scrapers.registry import resolve_scraper
from medguide.workers.celery_app import app
from medguide.workers.publishing import publish


@setup_logging.connect
def setup_worker_logging(**kwargs: object) -> None:
    configure_logging()


def repository() -> PipelineRepository:
    return PipelineRepository(session_factory(), get_settings())


@app.task(name="medguide.discover_source")
def discover_source(run_id: str) -> None:
    settings, repo = get_settings(), repository()
    with (
        Redis.from_url(settings.redis_url) as rate_store,
        SafeHttpClient(settings, rate_store=rate_store) as client,
    ):
        service = IngestionService(
            repo,
            FileStorage(settings.storage_root),
            lambda source: resolve_scraper(source.connector_key, client, source.base_url),
        )
        for job_id in service.discover(run_id):
            publish(repo, "ingest_guideline", job_id)


@app.task(name="medguide.ingest_guideline")
def ingest_guideline(job_id: str) -> None:
    settings = get_settings()
    with (
        Redis.from_url(settings.redis_url) as rate_store,
        SafeHttpClient(settings, rate_store=rate_store) as client,
    ):
        IngestionService(
            repository(),
            FileStorage(settings.storage_root),
            lambda source: resolve_scraper(source.connector_key, client, source.base_url),
        ).ingest(job_id)


@app.task(name="medguide.dispatch_due_sources")
def dispatch_due_sources() -> None:
    repo = repository()
    for source_id in repo.due_sources():
        run_id = repo.reserve_run(source_id, due_only=True)
        if run_id:
            publish(repo, "discover_source", run_id)


@app.task(name="medguide.reconcile")
def reconcile() -> None:
    repo = repository()
    for task, identifier in repo.reconcile():
        publish(repo, task, identifier)
