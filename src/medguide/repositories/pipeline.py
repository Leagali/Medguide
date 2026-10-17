from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from medguide.domain.models import (
    Artifact,
    CatalogObservation,
    CollectionRun,
    Guideline,
    GuidelineVersion,
    IngestionJob,
    Source,
    VersionArtifact,
    new_id,
    now,
)
from medguide.infrastructure.errors import LeaseLost, PipelineError
from medguide.infrastructure.settings import Settings
from medguide.ingestion.text import NORMALIZER_VERSION, composite_hash, digest, normalize
from medguide.scrapers.contracts import DiscoveredGuideline, ExtractedDocument, FetchedDocument

ACTIVE = ("PENDING", "PROCESSING")


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def fingerprint(item: DiscoveredGuideline) -> str:
    payload = item.model_dump(mode="json")
    payload["document_refs"] = sorted(
        payload["document_refs"], key=lambda ref: ref["reference_key"]
    )
    return digest(payload)


class PipelineRepository:
    def __init__(self, factory: sessionmaker[Session], settings: Settings) -> None:
        self.factory = factory
        self.settings = settings

    def reserve_run(self, source_id: str, *, due_only: bool = False) -> str | None:
        with self.factory.begin() as session:
            source = session.scalar(select(Source).where(Source.id == source_id).with_for_update())
            if source is None or not source.enabled:
                return None
            if due_only and utc(source.next_due_at) > now():
                return None
            active = session.scalar(
                select(CollectionRun.id).where(
                    CollectionRun.source_id == source.id, CollectionRun.status.in_(ACTIVE)
                )
            )
            if active:
                return active
            run = CollectionRun(
                source_id=source.id, connector_version=self.settings.connector_version
            )
            session.add(run)
            source.next_due_at = now() + timedelta(seconds=source.discovery_interval)
            session.flush()
            return run.id

    def due_sources(self) -> list[str]:
        with self.factory() as session:
            return list(
                session.scalars(
                    select(Source.id).where(Source.enabled.is_(True), Source.next_due_at <= now())
                )
            )

    def previous_found_count(self, source_id: str) -> int | None:
        with self.factory() as session:
            return session.scalar(
                select(CollectionRun.found_count)
                .where(CollectionRun.source_id == source_id, CollectionRun.status == "COMPLETED")
                .order_by(CollectionRun.finished_at.desc())
                .limit(1)
            )

    def claim(self, model: type[CollectionRun] | type[IngestionJob], identifier: str) -> str | None:
        token = new_id()
        with self.factory.begin() as session:
            conditions = [
                model.id == identifier,
                model.status == "PENDING",
                model.attempt_count < self.settings.task_attempts,
            ]
            conditions.append(model.available_at <= now())
            result = session.execute(
                update(model)
                .where(*conditions)
                .values(
                    status="PROCESSING",
                    lease_token=token,
                    lease_until=now() + timedelta(seconds=self.settings.lease_seconds),
                    attempt_count=model.attempt_count + 1,
                )
            )
            return token if result.rowcount == 1 else None  # type: ignore[attr-defined]

    @staticmethod
    def owned(
        session: Session,
        model: type[CollectionRun] | type[IngestionJob],
        identifier: str,
        token: str,
    ) -> Any:
        record = cast(
            CollectionRun | IngestionJob | None,
            session.scalar(select(model).where(model.id == identifier).with_for_update()),
        )
        if (
            record is None
            or record.status != "PROCESSING"
            or record.lease_token != token
            or record.lease_until is None
            or utc(record.lease_until) <= now()
        ):
            raise LeaseLost()
        return record

    def run_source(self, run_id: str) -> Source:
        with self.factory() as session:
            run = session.get(CollectionRun, run_id)
            if run is None:
                raise PipelineError("RUN_NOT_FOUND")
            source = session.get(Source, run.source_id)
            if source is None:
                raise PipelineError("SOURCE_NOT_FOUND")
            return source

    def complete_discovery(
        self, run_id: str, token: str, items: list[DiscoveredGuideline]
    ) -> list[str]:
        queued = []
        with self.factory.begin() as session:
            run = self.owned(session, CollectionRun, run_id, token)
            source = session.get(Source, run.source_id)
            assert source is not None
            if not items:
                raise PipelineError("CATALOG_EMPTY")
            for item in items:
                if item.source_key != source.connector_key:
                    raise PipelineError("SOURCE_KEY_MISMATCH")
                guideline = session.scalar(
                    select(Guideline)
                    .where(
                        Guideline.source_id == source.id,
                        Guideline.external_key == item.external_key,
                    )
                    .with_for_update()
                )
                if guideline is None:
                    guideline = Guideline(
                        source_id=source.id,
                        external_key=item.external_key,
                        title=item.title,
                        catalog_url=str(item.catalog_url),
                    )
                    session.add(guideline)
                    session.flush()
                guideline.title = item.title
                guideline.catalog_url = str(item.catalog_url)
                guideline.last_seen_at = now()
                item_fingerprint = fingerprint(item)
                observation = session.scalar(
                    select(CatalogObservation).where(
                        CatalogObservation.guideline_id == guideline.id,
                        CatalogObservation.run_id == run_id,
                    )
                )
                if observation is None:
                    session.add(
                        CatalogObservation(
                            guideline_id=guideline.id,
                            run_id=run_id,
                            fingerprint=item_fingerprint,
                            source_metadata_json=item.model_dump(mode="json"),
                        )
                    )
                latest = session.scalar(
                    select(IngestionJob)
                    .where(IngestionJob.guideline_id == guideline.id)
                    .order_by(IngestionJob.created_at.desc())
                    .limit(1)
                )
                active = session.scalar(
                    select(IngestionJob.id).where(
                        IngestionJob.guideline_id == guideline.id, IngestionJob.status.in_(ACTIVE)
                    )
                )
                changed = (
                    latest is None
                    or fingerprint(DiscoveredGuideline.model_validate(latest.payload_json))
                    != item_fingerprint
                )
                checked = guideline.last_checked_at
                due = (
                    checked is None
                    or utc(checked) + timedelta(seconds=source.content_recheck_interval) <= now()
                )
                failed_same = latest is not None and latest.status == "FAILED" and not changed
                if not active and not failed_same and (changed or due):
                    job = IngestionJob(
                        guideline_id=guideline.id,
                        payload_json=item.model_dump(mode="json"),
                        idempotency_key=f"{run_id}:{guideline.id}",
                    )
                    session.add(job)
                    session.flush()
                    queued.append(job.id)
            run.status, run.finished_at = "COMPLETED", now()
            run.found_count, run.queued_count = len(items), len(queued)
            run.lease_until, run.lease_token = None, None
        return queued

    def job_context(self, job_id: str) -> tuple[Source, DiscoveredGuideline]:
        with self.factory() as session:
            job = session.get(IngestionJob, job_id)
            if job is None:
                raise PipelineError("JOB_NOT_FOUND")
            guideline = session.get(Guideline, job.guideline_id)
            assert guideline is not None
            source = session.get(Source, guideline.source_id)
            assert source is not None
            return source, DiscoveredGuideline.model_validate(job.payload_json)

    def set_stage(self, job_id: str, token: str, stage: str) -> None:
        with self.factory.begin() as session:
            job = self.owned(session, IngestionJob, job_id, token)
            job.stage = stage

    def save_raw(
        self, job_id: str, token: str, fetched: FetchedDocument, storage_key: str, raw_hash: str
    ) -> str:
        with self.factory.begin() as session:
            job = self.owned(session, IngestionJob, job_id, token)
            artifact = session.scalar(
                select(Artifact).where(
                    Artifact.job_id == job_id,
                    Artifact.reference_key == fetched.reference_key,
                    Artifact.raw_sha256 == raw_hash,
                )
            )
            if artifact is None:
                artifact = Artifact(
                    guideline_id=job.guideline_id,
                    job_id=job_id,
                    reference_key=fetched.reference_key,
                    role=fetched.role,
                    storage_key=storage_key,
                    source_url=fetched.source_url,
                    raw_sha256=raw_hash,
                    media_type=fetched.media_type,
                    size_bytes=len(fetched.data),
                )
                session.add(artifact)
                session.flush()
            return artifact.id

    def save_extraction(
        self,
        job_id: str,
        token: str,
        artifact_id: str,
        document: ExtractedDocument,
        content_sha256: str,
    ) -> None:
        with self.factory.begin() as session:
            self.owned(session, IngestionJob, job_id, token)
            artifact = session.get(Artifact, artifact_id)
            assert artifact is not None
            artifact.pages_json = [page.model_dump() for page in document.pages]
            artifact.content_sha256 = content_sha256
            artifact.extraction_status = "EXTRACTED"
            artifact.extractor_version = document.extractor_version
            artifact.normalizer_version = NORMALIZER_VERSION

    def complete_ingestion(self, job_id: str, token: str, artifact_ids: list[str]) -> str:
        with self.factory.begin() as session:
            job = self.owned(session, IngestionJob, job_id, token)
            guideline = session.scalar(
                select(Guideline).where(Guideline.id == job.guideline_id).with_for_update()
            )
            assert guideline is not None
            artifacts = list(session.scalars(select(Artifact).where(Artifact.id.in_(artifact_ids))))
            if not artifacts or any(a.content_sha256 is None for a in artifacts):
                raise PipelineError("INCOMPLETE_EXTRACTION")
            composite = composite_hash(
                [(a.reference_key, a.role, a.content_sha256 or "") for a in artifacts]
            )
            version = session.scalar(
                select(GuidelineVersion).where(
                    GuidelineVersion.guideline_id == guideline.id,
                    GuidelineVersion.composite_content_sha256 == composite,
                )
            )
            if version is None:
                number = (
                    session.scalar(
                        select(func.max(GuidelineVersion.observed_version)).where(
                            GuidelineVersion.guideline_id == guideline.id
                        )
                    )
                    or 0
                ) + 1
                version = GuidelineVersion(
                    guideline_id=guideline.id,
                    observed_version=number,
                    composite_content_sha256=composite,
                    extracted_text="\n\n".join(
                        f"[{a.reference_key}]\n"
                        + "\n\n".join(
                            f"[p.{p['page_number']}]\n{normalize(p['text'])}"
                            for p in a.pages_json or []
                        )
                        for a in sorted(artifacts, key=lambda a: a.reference_key)
                    ),
                    extractor_version=",".join(
                        sorted({a.extractor_version or "" for a in artifacts})
                    ),
                    normalizer_version=NORMALIZER_VERSION,
                )
                session.add(version)
                session.flush()
                for artifact in artifacts:
                    session.add(VersionArtifact(version_id=version.id, artifact_id=artifact.id))
                outcome = "VERSION_CREATED"
            else:
                outcome = (
                    "CONTENT_UNCHANGED"
                    if guideline.current_version_id == version.id
                    else "CONTENT_REVERTED"
                )
            guideline.current_version_id = version.id
            guideline.last_checked_at = now()
            job.status, job.result, job.finished_at = "COMPLETED", outcome, now()
            job.lease_token, job.lease_until = None, None
            job.stage = "PERSIST"
            return outcome

    def fail(
        self,
        model: type[CollectionRun] | type[IngestionJob],
        identifier: str,
        token: str,
        stage: str,
        error: PipelineError,
    ) -> None:
        with self.factory.begin() as session:
            record = self.owned(session, model, identifier, token)
            if model is IngestionJob:
                record.stage, record.last_error = stage, error.code
            else:
                record.error_summary = f"{stage}:{error.code}"
            record.lease_token, record.lease_until = None, None
            if error.transient and record.attempt_count < self.settings.task_attempts:
                record.status, record.published_at = "PENDING", None
                record.available_at = now() + timedelta(
                    seconds=max(60 * record.attempt_count, error.retry_after)
                )
            else:
                review = error.code in ("EXTRACTION_EMPTY", "DOCUMENT_UNAVAILABLE")
                record.status = "NEEDS_REVIEW" if review else "FAILED"
                record.finished_at = now()
                if model is IngestionJob and review:
                    guideline = session.get(Guideline, record.guideline_id)
                    assert guideline is not None
                    guideline.last_checked_at = now()
                if model is IngestionJob:
                    session.execute(
                        update(Artifact)
                        .where(
                            Artifact.job_id == identifier, Artifact.extraction_status == "PENDING"
                        )
                        .values(extraction_status=error.code)
                    )

    def reconcile(self) -> list[tuple[str, str]]:
        pending: list[tuple[str, str]] = []
        with self.factory.begin() as session:
            for model, task in (
                (CollectionRun, "discover_source"),
                (IngestionJob, "ingest_guideline"),
            ):
                records = session.scalars(
                    select(model)
                    .where(
                        or_(
                            model.status == "PENDING",
                            (model.status == "PROCESSING") & (model.lease_until < now()),
                        )
                    )
                    .with_for_update(skip_locked=True)
                )
                for raw_record in records:
                    record = cast(CollectionRun | IngestionJob, raw_record)
                    if record.attempt_count >= self.settings.task_attempts:
                        record.status, record.finished_at = "FAILED", now()
                        if isinstance(record, IngestionJob):
                            record.last_error = "LEASE_ATTEMPTS_EXHAUSTED"
                        else:
                            record.error_summary = "DISCOVERY:LEASE_ATTEMPTS_EXHAUSTED"
                        record.lease_token, record.lease_until = None, None
                        continue
                    if utc(record.available_at) > now():
                        continue
                    if record.status == "PROCESSING":
                        record.status, record.published_at = "PENDING", None
                        record.lease_token, record.lease_until = None, None
                    if (
                        record.published_at is None
                        or utc(record.published_at)
                        + timedelta(seconds=self.settings.republish_seconds)
                        <= now()
                    ):
                        pending.append((task, record.id))
        return pending

    def mark_published(self, task: str, identifier: str) -> None:
        model = CollectionRun if task == "discover_source" else IngestionJob
        with self.factory.begin() as session:
            session.execute(
                update(model)
                .where(model.id == identifier, model.status == "PENDING")
                .values(published_at=now())
            )
