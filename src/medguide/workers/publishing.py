import logging

from medguide.repositories.pipeline import PipelineRepository
from medguide.workers.celery_app import app

logger = logging.getLogger(__name__)


def publish(repository: PipelineRepository, task: str, identifier: str) -> bool:
    try:
        app.send_task(
            f"medguide.{task}",
            args=[identifier],
            queue="discovery" if task == "discover_source" else "ingestion",
            retry=False,
        )
        repository.mark_published(task, identifier)
        return True
    except Exception:
        # Durable pending record is the outbox; reconciliation safely republishes it.
        logger.warning(
            "publication_deferred",
            extra={
                "context": {
                    "task": task,
                    "record_id": identifier,
                    "error_code": "BROKER_PUBLICATION_FAILED",
                }
            },
        )
        return False
