import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from medguide.domain.models import GuidelineVersion, IngestionJob
from medguide.workers.publishing import publish
from tests.integration.test_ingestion import setup_pipeline


@pytest.mark.postgres
def test_concurrent_source_reservation_and_duplicate_job_claim(db, settings):
    if not os.getenv("TEST_DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("PostgreSQL row locks required")
    repo, _, _, service, source_id = setup_pipeline(db, settings)
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = list(pool.map(lambda _: repo.reserve_run(source_id), range(4)))
    assert len(set(runs)) == 1
    job_id = service.discover(runs[0])[0]
    with ThreadPoolExecutor(max_workers=4) as pool:
        tokens = list(pool.map(lambda _: repo.claim(IngestionJob, job_id), range(4)))
    assert sum(token is not None for token in tokens) == 1


@pytest.mark.postgres
def test_real_redis_celery_delivery_runs_both_pipeline_stages(db, settings, monkeypatch):
    url = os.getenv("TEST_REDIS_URL")
    if not url or not os.getenv("TEST_DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("TEST_REDIS_URL and PostgreSQL required")
    from celery.contrib.testing.worker import start_worker

    from medguide.workers import tasks
    from medguide.workers.celery_app import app

    repo, scraper, _, _, source_id = setup_pipeline(db, settings)
    settings.redis_url = url
    monkeypatch.setattr(tasks, "repository", lambda: repo)
    monkeypatch.setattr(tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(tasks, "resolve_scraper", lambda *args: scraper)
    previous_broker = app.conf.broker_url
    app.conf.broker_url = url
    app.control.purge()
    try:
        with start_worker(
            app,
            pool="solo",
            queues=["discovery", "ingestion"],
            perform_ping_check=False,
            shutdown_timeout=15,
        ):
            run_id = repo.reserve_run(source_id)
            assert publish(repo, "discover_source", run_id)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                with db() as session:
                    completed = session.scalar(
                        select(IngestionJob).where(IngestionJob.status == "COMPLETED")
                    )
                    if completed:
                        break
                time.sleep(0.1)
            else:
                pytest.fail("Celery did not complete the persisted ingestion job")
            with db() as session:
                assert session.scalar(select(func.count()).select_from(GuidelineVersion)) == 1
    finally:
        app.conf.broker_url = previous_broker
