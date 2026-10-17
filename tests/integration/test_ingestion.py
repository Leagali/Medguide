from datetime import timedelta

import pymupdf
import pytest
from sqlalchemy import func, select

from medguide.domain.models import (
    Artifact,
    CatalogObservation,
    CollectionRun,
    Guideline,
    GuidelineVersion,
    IngestionJob,
    Source,
    now,
)
from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.settings import CATALOG_URL
from medguide.infrastructure.storage import FileStorage
from medguide.ingestion.service import IngestionService
from medguide.repositories.pipeline import PipelineRepository
from medguide.scrapers.contracts import DiscoveredGuideline, FetchedDocument


def pdf_bytes(text="Guideline dose: 5 mg/day.", metadata=""):
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        if text:
            page.insert_text((50, 50), text)
        pdf.set_metadata({"subject": metadata})
        return pdf.tobytes()


class FixtureScraper:
    def __init__(self):
        self.items = [
            DiscoveredGuideline.model_validate(
                {
                    "source_key": "conitec_pcdt",
                    "external_key": "asthma",
                    "title": "Asma",
                    "catalog_url": CATALOG_URL,
                    "document_refs": [
                        {
                            "reference_key": "main",
                            "role": "main",
                            "source_url": "https://www.gov.br/a.pdf",
                        },
                    ],
                }
            )
        ]
        self.data = pdf_bytes()
        self.error = None

    def discover(self):
        return self.items

    def fetch_documents(self, item):
        if self.error:
            raise self.error
        return [
            FetchedDocument(
                ref.reference_key, ref.role, str(ref.source_url), self.data, "application/pdf"
            )
            for ref in item.document_refs
        ]


def setup_pipeline(db, settings):
    with db.begin() as session:
        source = Source(code="conitec_pcdt", connector_key="conitec_pcdt", base_url=CATALOG_URL)
        session.add(source)
        session.flush()
        source_id = source.id
    repository = PipelineRepository(db, settings)
    scraper = FixtureScraper()
    storage = FileStorage(settings.storage_root)
    service = IngestionService(repository, storage, lambda _: scraper)
    return repository, scraper, storage, service, source_id


def discover(repository, service, source_id):
    run_id = repository.reserve_run(source_id)
    return service.discover(run_id)


def expire_check(db):
    with db.begin() as session:
        guideline = session.scalar(select(Guideline))
        guideline.last_checked_at = now() - timedelta(days=31)


def test_new_document_raw_text_and_duplicate_delivery(db, settings):
    repo, scraper, storage, service, source_id = setup_pipeline(db, settings)
    jobs = discover(repo, service, source_id)
    assert len(jobs) == 1
    assert service.ingest(jobs[0]) == "VERSION_CREATED"
    assert service.ingest(jobs[0]) == "IGNORED"
    assert discover(repo, service, source_id) == []
    with db() as session:
        assert session.scalar(select(func.count()).select_from(GuidelineVersion)) == 1
        artifact = session.scalar(select(Artifact))
        assert storage.read(artifact.storage_key) == scraper.data
        assert artifact.pages_json[0]["page_number"] == 1
        assert "5 mg/day" in session.scalar(select(GuidelineVersion.extracted_text))
        assert session.scalar(select(func.count()).select_from(CatalogObservation)) == 2


def test_metadata_and_raw_change_do_not_create_false_version_then_text_change_does(db, settings):
    repo, scraper, _, service, source_id = setup_pipeline(db, settings)
    assert service.ingest(discover(repo, service, source_id)[0]) == "VERSION_CREATED"
    scraper.items = [scraper.items[0].model_copy(update={"source_change_note": "Anexo alterado"})]
    assert service.ingest(discover(repo, service, source_id)[0]) == "CONTENT_UNCHANGED"
    scraper.data = pdf_bytes(metadata="Changed binary metadata")
    expire_check(db)
    assert service.ingest(discover(repo, service, source_id)[0]) == "CONTENT_UNCHANGED"
    scraper.data = pdf_bytes("Guideline dose: 10 mg/day.")
    expire_check(db)
    assert service.ingest(discover(repo, service, source_id)[0]) == "VERSION_CREATED"
    with db() as session:
        assert session.scalar(select(func.count()).select_from(GuidelineVersion)) == 2
        assert session.scalar(select(func.count()).select_from(Artifact)) == 4
        current = session.get(
            GuidelineVersion, session.scalar(select(Guideline.current_version_id))
        )
        assert current.observed_version == 2


def test_empty_pdf_preserves_raw_and_requests_review(db, settings):
    repo, scraper, storage, service, source_id = setup_pipeline(db, settings)
    scraper.data = pdf_bytes("")
    job_id = discover(repo, service, source_id)[0]
    assert service.ingest(job_id) == "EXTRACTION_EMPTY"
    with db() as session:
        job = session.get(IngestionJob, job_id)
        assert job.status == "NEEDS_REVIEW"
        artifact = session.scalar(select(Artifact))
        assert storage.read(artifact.storage_key) == scraper.data
        assert session.scalar(select(func.count()).select_from(GuidelineVersion)) == 0


def test_permanent_and_transient_failures_are_durable(db, settings):
    repo, scraper, _, service, source_id = setup_pipeline(db, settings)
    job_id = discover(repo, service, source_id)[0]
    scraper.error = PipelineError("HTTP_503", transient=True)
    assert service.ingest(job_id) == "HTTP_503"
    with db.begin() as session:
        job = session.get(IngestionJob, job_id)
        assert job.status == "PENDING" and job.attempt_count == 1
        job.available_at = now() - timedelta(seconds=1)
    scraper.error = PipelineError("HTTP_403")
    assert service.ingest(job_id) == "HTTP_403"
    with db() as session:
        job = session.get(IngestionJob, job_id)
        assert job.status == "FAILED" and job.attempt_count == 2
    assert discover(repo, service, source_id) == []  # explicit retry required


def test_expired_lease_recovery_and_stale_owner_cannot_write(db, settings):
    repo, _, _, service, source_id = setup_pipeline(db, settings)
    job_id = discover(repo, service, source_id)[0]
    token = repo.claim(IngestionJob, job_id)
    assert token is not None
    assert repo.claim(IngestionJob, job_id) is None
    with db.begin() as session:
        session.get(IngestionJob, job_id).lease_until = now() - timedelta(seconds=1)
    assert ("ingest_guideline", job_id) in repo.reconcile()
    with pytest.raises(PipelineError, match="LEASE_LOST"), db.begin() as session:
        repo.owned(session, IngestionJob, job_id, token)
    assert service.ingest(job_id) == "VERSION_CREATED"


def test_all_raw_documents_saved_even_if_first_extraction_fails(db, settings):
    repo, scraper, storage, service, source_id = setup_pipeline(db, settings)
    item = scraper.items[0].model_dump(mode="json")
    item["document_refs"].append(
        {"reference_key": "annex-a", "role": "annex", "source_url": "https://www.gov.br/annex.pdf"}
    )
    scraper.items = [DiscoveredGuideline.model_validate(item)]
    scraper.data = pdf_bytes("")
    assert service.ingest(discover(repo, service, source_id)[0]) == "EXTRACTION_EMPTY"
    with db() as session:
        artifacts = list(session.scalars(select(Artifact)))
        assert len(artifacts) == 2
        assert all(storage.read(a.storage_key) == scraper.data for a in artifacts)


def test_active_run_and_job_are_unique(db, settings):
    repo, _, _, service, source_id = setup_pipeline(db, settings)
    first_run = repo.reserve_run(source_id)
    assert repo.reserve_run(source_id) == first_run
    jobs = service.discover(first_run)
    assert service.discover(first_run) == []
    assert discover(repo, service, source_id) == []
    assert len(jobs) == 1
    with db() as session:
        assert session.scalar(select(func.count()).select_from(IngestionJob)) == 1
        assert session.get(CollectionRun, first_run).status == "COMPLETED"
