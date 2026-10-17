import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from medguide.domain.models import (
    Artifact,
    CatalogObservation,
    CollectionRun,
    Guideline,
    GuidelineVersion,
    IngestionJob,
    Source,
    new_id,
)
from medguide.infrastructure.db import get_session, session_factory
from medguide.infrastructure.observability import configure_logging
from medguide.infrastructure.settings import CATALOG_URL, Settings, get_settings
from medguide.infrastructure.storage import FileStorage
from medguide.repositories.pipeline import ACTIVE, PipelineRepository
from medguide.scrapers.registry import SCRAPER_REGISTRY
from medguide.workers.publishing import publish


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


app = FastAPI(title="MedGuide Ingestion", version="0.1.0", lifespan=lifespan)
bearer = HTTPBearer(auto_error=False)


def authorize(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    expected = settings.admin_token.get_secret_value()
    if not expected:
        raise HTTPException(503, "Administration is disabled: configure MEDGUIDE_ADMIN_TOKEN")
    if credentials is None or not hmac.compare_digest(
        credentials.credentials.encode(), expected.encode()
    ):
        raise HTTPException(
            401, "Invalid administration token", headers={"WWW-Authenticate": "Bearer"}
        )


def get_repository() -> PipelineRepository:
    return PipelineRepository(session_factory(), get_settings())


Db = Annotated[Session, Depends(get_session)]
Repo = Annotated[PipelineRepository, Depends(get_repository)]
Config = Annotated[Settings, Depends(get_settings)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]
api = APIRouter(prefix="/api", dependencies=[Depends(authorize)])


def serialize(record: Any) -> dict[str, Any]:
    return {column.key: getattr(record, column.key) for column in inspect(type(record)).columns}


def require(session: Session, model: Any, identifier: str) -> Any:
    record = session.get(model, identifier)
    if record is None:
        raise HTTPException(404, "Record not found")
    return record


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$", default="conitec_pcdt")
    connector_key: str = "conitec_pcdt"
    enabled: bool = True


class SourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    discovery_interval: int | None = Field(default=None, ge=60)
    content_recheck_interval: int | None = Field(default=None, ge=60)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def ready(session: Db, settings: Config) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
        # Check schema as well as the database socket.
        session.scalar(select(Source.id).limit(1))
        with Redis.from_url(
            settings.redis_url, socket_connect_timeout=2, socket_timeout=2
        ) as redis:
            redis.ping()
        root = settings.storage_root
        root.mkdir(parents=True, exist_ok=True)
        probe = root / f".ready-{new_id()}"
        try:
            probe.write_bytes(b"ready")
        finally:
            probe.unlink(missing_ok=True)
    except Exception as exc:
        raise HTTPException(503, "Database, broker, schema or storage unavailable") from exc
    return {"status": "ready"}


@api.get("/sources")
def sources(session: Db, limit: Limit = 50, offset: Offset = 0) -> list[dict[str, Any]]:
    return [
        serialize(s)
        for s in session.scalars(select(Source).order_by(Source.code).limit(limit).offset(offset))
    ]


@api.post("/sources", status_code=201)
def create_source(payload: SourceCreate, session: Db, settings: Config) -> dict[str, Any]:
    if payload.connector_key not in SCRAPER_REGISTRY or payload.connector_key != "conitec_pcdt":
        raise HTTPException(422, "Connector is not homologated")
    source = Source(
        code=payload.code,
        connector_key=payload.connector_key,
        base_url=CATALOG_URL,
        enabled=payload.enabled,
        discovery_interval=settings.discovery_interval,
        content_recheck_interval=settings.content_recheck_interval,
    )
    session.add(source)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Source code already exists") from exc
    return serialize(source)


@api.patch("/sources/{source_id}")
def update_source(source_id: str, payload: SourcePatch, session: Db) -> dict[str, Any]:
    source = require(session, Source, source_id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(source, key, value)
    session.commit()
    return serialize(source)


@api.post("/sources/{source_id}/discover", status_code=202)
def request_discovery(source_id: str, session: Db, repo: Repo) -> dict[str, Any]:
    source = require(session, Source, source_id)
    if not source.enabled:
        raise HTTPException(409, "Source is disabled")
    run_id = repo.reserve_run(source_id)
    if run_id is None:
        raise HTTPException(409, "Source unavailable")
    return {"run_id": run_id, "published": publish(repo, "discover_source", run_id)}


@api.get("/runs")
def runs(
    session: Db, source_id: str | None = None, limit: Limit = 50, offset: Offset = 0
) -> list[dict[str, Any]]:
    query = select(CollectionRun).order_by(CollectionRun.started_at.desc())
    if source_id:
        query = query.where(CollectionRun.source_id == source_id)
    return [serialize(r) for r in session.scalars(query.limit(limit).offset(offset))]


@api.get("/runs/{run_id}")
def run_detail(run_id: str, session: Db) -> dict[str, Any]:
    return serialize(require(session, CollectionRun, run_id))


@api.get("/guidelines")
def guidelines(
    session: Db, source_id: str | None = None, limit: Limit = 50, offset: Offset = 0
) -> list[dict[str, Any]]:
    query = select(Guideline).order_by(Guideline.title)
    if source_id:
        query = query.where(Guideline.source_id == source_id)
    return [serialize(g) for g in session.scalars(query.limit(limit).offset(offset))]


@api.get("/guidelines/{guideline_id}")
def guideline_detail(guideline_id: str, session: Db) -> dict[str, Any]:
    return serialize(require(session, Guideline, guideline_id))


@api.get("/guidelines/{guideline_id}/versions")
def versions(
    guideline_id: str, session: Db, limit: Limit = 50, offset: Offset = 0
) -> list[dict[str, Any]]:
    require(session, Guideline, guideline_id)
    return [
        serialize(v)
        for v in session.scalars(
            select(GuidelineVersion)
            .where(GuidelineVersion.guideline_id == guideline_id)
            .order_by(GuidelineVersion.observed_version.desc())
            .limit(limit)
            .offset(offset)
        )
    ]


@api.get("/guidelines/{guideline_id}/observations")
def observations(
    guideline_id: str, session: Db, limit: Limit = 50, offset: Offset = 0
) -> list[dict[str, Any]]:
    require(session, Guideline, guideline_id)
    return [
        serialize(o)
        for o in session.scalars(
            select(CatalogObservation)
            .where(CatalogObservation.guideline_id == guideline_id)
            .order_by(CatalogObservation.observed_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ]


@api.get("/guidelines/{guideline_id}/artifacts")
def artifacts(
    guideline_id: str, session: Db, limit: Limit = 50, offset: Offset = 0
) -> list[dict[str, Any]]:
    require(session, Guideline, guideline_id)
    return [
        serialize(a)
        for a in session.scalars(
            select(Artifact)
            .where(Artifact.guideline_id == guideline_id)
            .order_by(Artifact.fetched_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ]


@api.get("/artifacts/{artifact_id}/raw")
def raw_document(artifact_id: str, session: Db, settings: Config) -> Response:
    artifact = require(session, Artifact, artifact_id)
    try:
        data = FileStorage(settings.storage_root).read(artifact.storage_key)
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Raw storage unavailable or integrity check failed") from exc
    return Response(
        data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.id}.raw"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@api.get("/jobs")
def jobs(
    session: Db, status: str | None = None, limit: Limit = 50, offset: Offset = 0
) -> list[dict[str, Any]]:
    query = select(IngestionJob).order_by(IngestionJob.created_at.desc())
    if status:
        query = query.where(IngestionJob.status == status)
    return [serialize(j) for j in session.scalars(query.limit(limit).offset(offset))]


@api.get("/jobs/{job_id}")
def job_detail(job_id: str, session: Db) -> dict[str, Any]:
    return serialize(require(session, IngestionJob, job_id))


@api.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, session: Db, repo: Repo) -> dict[str, Any]:
    previous = require(session, IngestionJob, job_id)
    if previous.status not in ("FAILED", "NEEDS_REVIEW"):
        raise HTTPException(409, "Only failed or review jobs can be retried")
    guideline = session.scalar(
        select(Guideline).where(Guideline.id == previous.guideline_id).with_for_update()
    )
    assert guideline is not None
    if not require(session, Source, guideline.source_id).enabled:
        raise HTTPException(409, "Source is disabled")
    if session.scalar(
        select(IngestionJob.id).where(
            IngestionJob.guideline_id == guideline.id, IngestionJob.status.in_(ACTIVE)
        )
    ):
        raise HTTPException(409, "Guideline already has an active job")
    latest = session.scalar(
        select(CatalogObservation)
        .where(CatalogObservation.guideline_id == guideline.id)
        .order_by(CatalogObservation.observed_at.desc())
        .limit(1)
    )
    job = IngestionJob(
        guideline_id=guideline.id,
        idempotency_key=f"manual:{new_id()}",
        payload_json=latest.source_metadata_json if latest else previous.payload_json,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Guideline already has an active job") from exc
    return {"job_id": job.id, "published": publish(repo, "ingest_guideline", job.id)}


@api.get("/metrics")
def metrics(session: Db) -> dict[str, Any]:
    counts = {
        status: count
        for status, count in session.execute(
            select(IngestionJob.status, func.count()).group_by(IngestionJob.status)
        )
    }
    failures = [
        {"stage": stage, "count": count}
        for stage, count in session.execute(
            select(IngestionJob.stage, func.count())
            .where(IngestionJob.status == "FAILED")
            .group_by(IngestionJob.stage)
        )
    ]
    successes = [
        {"source_id": source, "last_success_at": timestamp}
        for source, timestamp in session.execute(
            select(CollectionRun.source_id, func.max(CollectionRun.finished_at))
            .where(CollectionRun.status == "COMPLETED")
            .group_by(CollectionRun.source_id)
        )
    ]
    return {
        "jobs_by_status": counts,
        "failures_by_stage": failures,
        "versions": session.scalar(select(func.count()).select_from(GuidelineVersion)),
        "artifacts": session.scalar(select(func.count()).select_from(Artifact)),
        "source_successes": successes,
    }


app.include_router(api)
