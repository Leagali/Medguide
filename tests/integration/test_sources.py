import importlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from medguide.domain.models import CollectionRun, IngestionJob, Source, now
from medguide.infrastructure.errors import PipelineError
from medguide.repositories.pipeline import PipelineRepository, utc
from medguide.repositories.sources import SourceRepository
from medguide.sources import SourceService
from tests.integration.test_ingestion import setup_pipeline


def service_for(db, settings, publisher=lambda *args: True):
    return SourceService(
        SourceRepository(db), PipelineRepository(db, settings), settings, publisher
    )


def test_bootstrap_registers_due_source_without_starting_collection(db, settings):
    service = service_for(db, settings, lambda *args: pytest.fail("bootstrap must not publish"))
    assert service.bootstrap() == ["conitec_pcdt"]
    assert service.bootstrap() == []
    source = service.sources.by_code("conitec_pcdt")
    assert source.enabled
    assert service.pipeline.due_sources() == [source.id]
    with db() as session:
        assert session.scalar(select(func.count()).select_from(Source)) == 1
        assert session.scalar(select(func.count()).select_from(CollectionRun)) == 0


def test_bootstrap_preserves_disabled_source_and_custom_schedule(db, settings):
    service = service_for(db, settings)
    service.bootstrap()
    scheduled = now() + timedelta(days=4)
    with db.begin() as session:
        source = session.scalar(select(Source))
        source.enabled = False
        source.discovery_interval = 7200
        source.content_recheck_interval = 86400
        source.next_due_at = scheduled
        original_id = source.id
    assert service.bootstrap() == []
    source = service.sources.by_code("conitec_pcdt")
    assert source.id == original_id
    assert not source.enabled
    assert source.discovery_interval == 7200
    assert source.content_recheck_interval == 86400
    assert utc(source.next_due_at) == scheduled
    assert service.pipeline.due_sources() == []


def test_list_shows_available_and_persisted_sources_without_writing(db, settings):
    service = service_for(db, settings)
    assert service.list()[0]["registered"] is False
    assert service.sources.all() == []
    service.bootstrap()
    row = service.list()[0]
    assert row["code"] == "conitec_pcdt" and row["enabled"] and row["registered"]


def test_run_by_code_registers_missing_source_and_reuses_active_run(db, settings):
    sent = []
    service = service_for(
        db, settings, lambda repo, task, identifier: sent.append((task, identifier)) or True
    )
    first = service.run("conitec_pcdt")
    second = service.run("conitec_pcdt")
    assert first["reused"] is False and first["published"] is True
    assert second["reused"] is True and first["run_id"] == second["run_id"]
    assert sent == [("discover_source", first["run_id"])] * 2
    with db() as session:
        assert session.scalar(select(func.count()).select_from(CollectionRun)) == 1


def test_run_broker_failure_preserves_pending_work(db, settings):
    service = service_for(db, settings, lambda *args: False)
    result = service.run("conitec_pcdt")
    assert result["published"] is False
    assert ("discover_source", result["run_id"]) in service.pipeline.reconcile()


def test_enable_disable_and_unknown_source(db, settings):
    service = service_for(db, settings)
    assert service.set_enabled("conitec_pcdt", False)["enabled"] is False
    assert service.pipeline.due_sources() == []
    with pytest.raises(PipelineError, match="SOURCE_DISABLED"):
        service.run("conitec_pcdt")
    assert service.set_enabled("conitec_pcdt", True)["enabled"] is True
    assert service.run("conitec_pcdt")["run_id"]
    with pytest.raises(PipelineError, match="UNKNOWN_SOURCE"):
        service.run("arbitrary_import")
    with pytest.raises(PipelineError, match="UNKNOWN_SOURCE"):
        service.set_enabled("unknown", True)


def test_status_counts_only_jobs_from_requested_source(db, settings):
    repo, _, _, pipeline, source_id = setup_pipeline(db, settings)
    job_id = pipeline.discover(repo.reserve_run(source_id))[0]
    service = service_for(db, settings)
    status = service.status("conitec_pcdt")
    assert status["latest_run"]["status"] == "COMPLETED"
    assert status["jobs_by_status"]["PENDING"] == 1
    assert status["jobs_by_status"]["COMPLETED"] == 0
    assert pipeline.ingest(job_id) == "VERSION_CREATED"
    status = service.status("conitec_pcdt")
    assert status["jobs_by_status"]["COMPLETED"] == 1
    # A second source's failed job must not appear in the first source's status.
    second_repo, _, _, second_pipeline, second_source = setup_pipeline_with_alias(db, settings)
    second_job = second_pipeline.discover(second_repo.reserve_run(second_source))[0]
    with db.begin() as session:
        session.get(IngestionJob, second_job).status = "FAILED"
    assert service.status("conitec_pcdt")["jobs_by_status"]["FAILED"] == 0


def setup_pipeline_with_alias(db, settings):
    # Existing administrative aliases remain addressable by code.
    from medguide.infrastructure.settings import CATALOG_URL
    from medguide.infrastructure.storage import FileStorage
    from medguide.ingestion.service import IngestionService
    from tests.integration.test_ingestion import FixtureScraper

    with db.begin() as session:
        source = Source(code="alias", connector_key="conitec_pcdt", base_url=CATALOG_URL)
        session.add(source)
        session.flush()
        source_id = source.id
    repo = PipelineRepository(db, settings)
    scraper = FixtureScraper()
    storage = FileStorage(settings.storage_root)
    return repo, scraper, storage, IngestionService(repo, storage, lambda _: scraper), source_id


def test_cli_commands_render_results_and_use_exit_codes(db, settings, monkeypatch, capsys):
    cli = importlib.import_module("medguide.__main__")
    service = service_for(db, settings, lambda *args: False)
    monkeypatch.setattr(cli, "build_service", lambda: service)
    assert cli.main(["sources", "list"]) == 0
    assert "conitec_pcdt" in capsys.readouterr().out
    assert cli.main(["sources", "bootstrap"]) == 0
    assert "conitec_pcdt" in capsys.readouterr().out
    assert cli.main(["sources", "status", "conitec_pcdt"]) == 0
    assert "nenhuma" in capsys.readouterr().out
    assert cli.main(["sources", "run", "conitec_pcdt", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["published"] is False
    assert cli.main(["sources", "run", "conitec_pcdt"]) == 0
    assert "Pedido salvo" in capsys.readouterr().out
    assert cli.main(["sources", "disable", "conitec_pcdt"]) == 0
    capsys.readouterr()
    assert cli.main(["sources", "run", "conitec_pcdt"]) == 1
    assert "desabilitada" in capsys.readouterr().err
    assert cli.main(["sources", "enable", "conitec_pcdt"]) == 0
    capsys.readouterr()
    assert cli.main(["sources", "status", "missing"]) == 1
    assert "desconhecida" in capsys.readouterr().err


def test_startup_migrates_and_cli_works_without_admin_token(tmp_path):
    url = f"sqlite:///{(tmp_path / 'startup.db').as_posix()}"
    env = {
        **os.environ,
        "MEDGUIDE_DATABASE_URL": url,
        "MEDGUIDE_ADMIN_TOKEN": "",
        "PYTHONIOENCODING": "utf-8",
    }

    def run(module, *args):
        result = subprocess.run(
            [sys.executable, "-m", module, *args],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    assert "conitec_pcdt" in run("medguide.bootstrap")
    listed = json.loads(run("medguide", "sources", "list", "--json"))
    assert listed[0]["enabled"] is True
    run("medguide", "sources", "disable", "conitec_pcdt")
    run("medguide.bootstrap")
    status = json.loads(run("medguide", "sources", "status", "conitec_pcdt", "--json"))
    assert status["enabled"] is False and status["latest_run"] is None


@pytest.mark.postgres
def test_concurrent_bootstrap_and_run_requests(db, settings):
    if not os.getenv("TEST_DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("PostgreSQL concurrent transactions required")
    service = service_for(db, settings)
    with ThreadPoolExecutor(max_workers=4) as pool:
        inserted = list(pool.map(lambda _: service.bootstrap(), range(4)))
    assert sum(len(codes) for codes in inserted) == 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.run("conitec_pcdt"), range(4)))
    assert len({result["run_id"] for result in results}) == 1
    assert sum(not result["reused"] for result in results) == 1
