"""Extração oficial limitada a um PDF; SQLite e RAW sempre temporários."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from redis import Redis
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from medguide.domain.models import Artifact, Base, GuidelineVersion, IngestionJob, Source
from medguide.infrastructure.http import SafeHttpClient
from medguide.infrastructure.settings import CATALOG_URL, Settings
from medguide.infrastructure.storage import FileStorage
from medguide.ingestion.service import IngestionService
from medguide.repositories.pipeline import PipelineRepository
from medguide.scrapers.conitec.scraper import ConitecPCDTScraper
from medguide.scrapers.contracts import DiscoveredGuideline


def main(root: Path, external_key: str) -> None:
    state = {"status": "RUNNING", "stage": "DISCOVERY", "events": []}

    def emit(stage: str, message: str, **values: object) -> None:
        state.update(stage=stage, **values)
        state["events"].append(
            {"stage": stage, "message": message, "at": datetime.now(UTC).isoformat()}
        )
        temporary = root / "state.next"
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        temporary.replace(root / "state.json")

    class ObservedRepository(PipelineRepository):
        def set_stage(self, job_id: str, token: str, stage: str) -> None:
            super().set_stage(job_id, token, stage)
            labels = {
                "FETCH": "Recuperando o documento oficial.",
                "PERSIST": "Preservando os dados no ambiente temporário.",
                "EXTRACT": "Extraindo o texto das páginas do PDF.",
                "NORMALIZE": "Normalizando o texto e calculando sua integridade.",
            }
            emit(stage, labels[stage])

    engine = None
    try:
        settings = Settings(
            _env_file=None,
            database_url=f"sqlite:///{root / 'sample.db'}",
            storage_root=root / "raw",
        )
        engine = create_engine(settings.database_url)
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        emit("DISCOVERY", "Consultando o catálogo oficial da CONITEC.")
        with (
            Redis.from_url(settings.redis_url) as rate_store,
            SafeHttpClient(settings, rate_store=rate_store) as http,
        ):
            scraper = ConitecPCDTScraper(http, CATALOG_URL)
            items = scraper.discover()
            candidate = (
                next((item for item in items if item.external_key == external_key), None)
                if external_key
                else items[0]
            )
            if candidate is None:
                raise ValueError("A diretriz selecionada não foi encontrada no catálogo atual.")
            # A demonstração escolhe apenas o documento principal; não representa
            # uma nova versão completa da diretriz no acervo da aplicação.
            reference = next(
                (ref for ref in candidate.document_refs if ref.role == "main"),
                candidate.document_refs[0],
            )
            candidate = DiscoveredGuideline.model_validate(
                {
                    **candidate.model_dump(mode="json"),
                    "document_refs": [reference.model_dump(mode="json")],
                }
            )
            emit(
                "DISCOVERY",
                "Catálogo consultado; documento principal selecionado.",
                title=candidate.title,
                catalog_items=len(items),
            )

            class OneDocument:
                def discover(self):
                    return [candidate]

                def fetch_documents(self, item):
                    documents = scraper.fetch_documents(item)
                    if len(documents) != 1 or not documents[0].data.startswith(b"%PDF-"):
                        raise ValueError("O documento principal recuperado não é um PDF único.")
                    return documents

            with factory.begin() as session:
                source = Source(
                    code="conitec_pcdt", connector_key="conitec_pcdt", base_url=CATALOG_URL
                )
                session.add(source)
                session.flush()
                source_id = source.id
            repo = ObservedRepository(factory, settings)
            storage = FileStorage(settings.storage_root)
            service = IngestionService(repo, storage, lambda _: OneDocument())
            jobs = service.discover(repo.reserve_run(source_id))
            if len(jobs) != 1:
                raise ValueError("O ensaio não criou o job esperado.")
            outcome = service.ingest(jobs[0])
            if outcome != "VERSION_CREATED":
                raise ValueError(f"Extração não concluída: {outcome}.")
            duplicate = service.ingest(jobs[0])
            with factory() as session:
                artifact = session.scalar(select(Artifact))
                version = session.scalar(select(GuidelineVersion))
                job = session.get(IngestionJob, jobs[0])
                original = storage.read(artifact.storage_key)
                (root / "original.pdf").write_bytes(original)
                result = {
                    "scope": "temporary",
                    "guideline": {
                        "id": None,
                        "title": candidate.title,
                        "external_key": candidate.external_key,
                    },
                    "versions": [],
                    "version": {
                        "id": version.id,
                        "observed_version": version.observed_version,
                        "detected_at": version.detected_at.isoformat(),
                        "extracted_text": version.extracted_text,
                    },
                    "documents": [
                        {
                            "id": artifact.id,
                            "role": artifact.role,
                            "reference_key": artifact.reference_key,
                            "source_url": artifact.source_url,
                            "media_type": artifact.media_type,
                            "fetched_at": artifact.fetched_at.isoformat(),
                            "pages_json": artifact.pages_json,
                            "size_bytes": artifact.size_bytes,
                            "raw_sha256": artifact.raw_sha256,
                            "content_sha256": artifact.content_sha256,
                        }
                    ],
                }
                (root / "result.json").write_text(
                    json.dumps(result, ensure_ascii=False), encoding="utf-8"
                )
                emit(
                    "COMPLETED",
                    "PDF preservado, texto extraído e reexecução conferida.",
                    status="COMPLETED",
                    pages=len(artifact.pages_json),
                    characters=len(version.extracted_text),
                    job_status=job.status,
                    duplicate_delivery=duplicate,
                )
    except Exception as exc:
        emit("FAILED", "Não foi possível concluir o ensaio.", status="FAILED", error=str(exc)[:300])
    finally:
        if engine:
            engine.dispose()


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
