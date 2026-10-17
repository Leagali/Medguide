from celery import Celery

from medguide.infrastructure.settings import get_settings

settings = get_settings()
app = Celery("medguide", broker=settings.redis_url, include=["medguide.workers.tasks"])
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=3,
    broker_transport_options={
        "visibility_timeout": settings.lease_seconds + 300,
        "socket_timeout": 3,
        "socket_connect_timeout": 3,
    },
    task_soft_time_limit=max(1, settings.lease_seconds - 60),
    task_time_limit=settings.lease_seconds - 30,
    task_routes={
        "medguide.discover_source": {"queue": "discovery"},
        "medguide.ingest_guideline": {"queue": "ingestion"},
        "medguide.dispatch_due_sources": {"queue": "discovery"},
        "medguide.reconcile": {"queue": "discovery"},
    },
    beat_schedule={
        "due-sources": {
            "task": "medguide.dispatch_due_sources",
            "schedule": settings.dispatch_seconds,
        },
        "recover-pending": {"task": "medguide.reconcile", "schedule": settings.dispatch_seconds},
    },
    timezone="UTC",
    enable_utc=True,
)
