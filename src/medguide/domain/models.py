from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    connector_key: Mapped[str] = mapped_column(String(80))
    base_url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    discovery_interval: Mapped[int] = mapped_column(Integer, default=86400)
    content_recheck_interval: Mapped[int] = mapped_column(Integer, default=2592000)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (Index("ix_sources_due", "next_due_at", "enabled"),)


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    found_count: Mapped[int] = mapped_column(Integer, default=0)
    queued_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    connector_version: Mapped[str] = mapped_column(String(100))
    __table_args__ = (
        Index("ix_runs_source_started", "source_id", "started_at"),
        Index(
            "uq_active_run_source",
            "source_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'PROCESSING')"),
            sqlite_where=text("status IN ('PENDING', 'PROCESSING')"),
        ),
    )


class Guideline(Base):
    __tablename__ = "guidelines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    external_key: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    catalog_url: Mapped[str] = mapped_column(Text)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("guideline_versions.id", name="fk_current_version", use_alter=True)
    )
    __table_args__ = (UniqueConstraint("source_id", "external_key"),)


class CatalogObservation(Base):
    __tablename__ = "catalog_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guideline_id: Mapped[str] = mapped_column(ForeignKey("guidelines.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("collection_runs.id"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    source_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("guideline_id", "run_id"),)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guideline_id: Mapped[str] = mapped_column(ForeignKey("guidelines.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(150), unique=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(String(30))
    result: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        Index("ix_jobs_status_created", "status", "created_at"),
        Index(
            "uq_active_job_guideline",
            "guideline_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'PROCESSING')"),
            sqlite_where=text("status IN ('PENDING', 'PROCESSING')"),
        ),
    )


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guideline_id: Mapped[str] = mapped_column(ForeignKey("guidelines.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("ingestion_jobs.id"))
    reference_key: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30))
    storage_key: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    raw_sha256: Mapped[str] = mapped_column(String(64))
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(100))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    size_bytes: Mapped[int] = mapped_column(Integer)
    extraction_status: Mapped[str] = mapped_column(String(40), default="PENDING")
    pages_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    extractor_version: Mapped[str | None] = mapped_column(String(80))
    normalizer_version: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint("job_id", "reference_key", "raw_sha256"),)


class GuidelineVersion(Base):
    __tablename__ = "guideline_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guideline_id: Mapped[str] = mapped_column(ForeignKey("guidelines.id"))
    observed_version: Mapped[int] = mapped_column(Integer)
    composite_content_sha256: Mapped[str] = mapped_column(String(64))
    extracted_text: Mapped[str] = mapped_column(Text)
    extractor_version: Mapped[str] = mapped_column(String(200))
    normalizer_version: Mapped[str] = mapped_column(String(80))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("guideline_id", "composite_content_sha256"),
        UniqueConstraint("guideline_id", "observed_version"),
        Index("ix_versions_guideline_detected", "guideline_id", "detected_at"),
    )


class VersionArtifact(Base):
    __tablename__ = "version_artifacts"
    version_id: Mapped[str] = mapped_column(ForeignKey("guideline_versions.id"), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), primary_key=True)
