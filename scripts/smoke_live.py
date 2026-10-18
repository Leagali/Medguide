"""Limited live smoke: one catalogue request and one official PDF; no full crawl."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from medguide.domain.models import Artifact, Base, GuidelineVersion, IngestionJob, Source
from medguide.infrastructure.http import SafeHttpClient
from medguide.infrastructure.settings import CATALOG_URL, Settings
from medguide.infrastructure.storage import FileStorage
from medguide.ingestion.service import IngestionService
from medguide.repositories.pipeline import PipelineRepository
from medguide.scrapers.conitec.scraper import ConitecPCDTScraper


def main() -> None:
    output = Path("test-results")
    output.mkdir(exist_ok=True)
    os.makedirs("data", exist_ok=True)
    with TemporaryDirectory(prefix="live-smoke-", dir="data") as directory:
        root = Path(directory)
        settings = Settings(
            _env_file=None, database_url=f"sqlite:///{root / 'smoke.db'}", storage_root=root / "raw"
        )
        engine = create_engine(settings.database_url)
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        with SafeHttpClient(settings) as http:
            scraper = ConitecPCDTScraper(http, CATALOG_URL)
            items = scraper.discover()
            candidate = items[0]

            class SingleItemScraper:
                def discover(self):
                    return [candidate]

                def fetch_documents(self, item):
                    return scraper.fetch_documents(item)

            with factory.begin() as session:
                source = Source(
                    code="conitec_pcdt", connector_key="conitec_pcdt", base_url=CATALOG_URL
                )
                session.add(source)
                session.flush()
                source_id = source.id
            repo = PipelineRepository(factory, settings)
            storage = FileStorage(settings.storage_root)
            service = IngestionService(repo, storage, lambda _: SingleItemScraper())
            run_id = repo.reserve_run(source_id)
            jobs = service.discover(run_id)
            assert len(jobs) == 1, "Discovery did not create a durable job"
            result = service.ingest(jobs[0])
            assert result == "VERSION_CREATED", result
            assert service.ingest(jobs[0]) == "IGNORED"
            with factory() as session:
                artifact = session.scalar(select(Artifact))
                version = session.scalar(select(GuidelineVersion))
                assert artifact is not None and version is not None
                assert storage.read(artifact.storage_key).startswith(b"%PDF-")
                job = session.get(IngestionJob, jobs[0])
                report = {
                    "catalog_url": CATALOG_URL,
                    "catalog_items": len(items),
                    "title": candidate.title,
                    "document_url": artifact.source_url,
                    "bytes": artifact.size_bytes,
                    "pages": len(artifact.pages_json or []),
                    "raw_sha256": artifact.raw_sha256,
                    "content_sha256": artifact.content_sha256,
                    "extracted_characters": len(version.extracted_text),
                    "job_status": job.status,
                    "duplicate_delivery": "IGNORED",
                    "database": "temporary SQLite (not PostgreSQL validation)",
                }
                (output / "live-smoke.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(json.dumps(report, ensure_ascii=False, indent=2))
        engine.dispose()


if __name__ == "__main__":
    main()
