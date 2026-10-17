import importlib
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from medguide.domain.models import IngestionJob
from medguide.infrastructure.db import get_session
from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.settings import get_settings
from medguide.repositories.pipeline import PipelineRepository
from medguide.workers.publishing import publish
from tests.integration.test_ingestion import setup_pipeline

api_module = importlib.import_module("medguide.api.app")


@pytest.fixture
def api(db, settings, monkeypatch):
    def sessions():
        with db() as session:
            yield session

    repository = PipelineRepository(db, settings)
    api_module.app.dependency_overrides[get_session] = sessions
    api_module.app.dependency_overrides[get_settings] = lambda: settings
    api_module.app.dependency_overrides[api_module.get_repository] = lambda: repository
    sent = []
    monkeypatch.setattr(
        api_module,
        "publish",
        lambda repo, task, identifier: sent.append((task, identifier)) or True,
    )
    with TestClient(
        api_module.app, headers={"Authorization": "Bearer request-test-token"}
    ) as client:
        yield client, sent
    api_module.app.dependency_overrides.clear()


def test_auth_health_and_readiness(api, settings, monkeypatch):
    client, _ = api
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/sources", headers={"Authorization": "Bearer wrong"}).status_code == 401
    redis = MagicMock()
    monkeypatch.setattr(api_module.Redis, "from_url", lambda *a, **kw: redis)
    assert client.get("/readyz").status_code == 200
    redis.__enter__.return_value.ping.side_effect = OSError("offline")
    assert client.get("/readyz").status_code == 503
    settings.admin_token = type(settings.admin_token)("")
    assert client.get("/api/sources").status_code == 503


def test_source_requests_and_async_discovery(api):
    client, sent = api
    assert client.post("/api/sources", json={"connector_key": "os.system"}).status_code == 422
    assert client.post("/api/sources", json={"base_url": "http://localhost"}).status_code == 422
    created = client.post("/api/sources", json={})
    assert created.status_code == 201
    source_id = created.json()["id"]
    assert client.post("/api/sources", json={}).status_code == 409
    run = client.post(f"/api/sources/{source_id}/discover")
    assert run.status_code == 202
    assert sent == [("discover_source", run.json()["run_id"])]
    again = client.post(f"/api/sources/{source_id}/discover")
    assert again.json()["run_id"] == run.json()["run_id"]
    assert client.get("/api/runs").json()[0]["status"] == "PENDING"
    assert (
        client.patch(f"/api/sources/{source_id}", json={"discovery_interval": 0}).status_code == 422
    )
    assert client.patch(f"/api/sources/{source_id}", json={"enabled": False}).status_code == 200
    assert client.post(f"/api/sources/{source_id}/discover").status_code == 409
    assert client.get("/api/guidelines?limit=201").status_code == 422
    assert client.get("/api/runs/missing").status_code == 404


def test_request_workflow_and_raw_retrieval(api, db, settings):
    client, _ = api
    repo, scraper, _, service, source_id = setup_pipeline(db, settings)
    accepted = client.post(f"/api/sources/{source_id}/discover")
    job_id = service.discover(accepted.json()["run_id"])[0]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "PENDING"
    assert service.ingest(job_id) == "VERSION_CREATED"
    guideline = client.get("/api/guidelines").json()[0]
    guideline_id = guideline["id"]
    versions = client.get(f"/api/guidelines/{guideline_id}/versions").json()
    assert len(versions) == 1
    assert "5 mg/day" in versions[0]["extracted_text"]
    assert len(client.get(f"/api/guidelines/{guideline_id}/observations").json()) == 1
    artifact = client.get(f"/api/guidelines/{guideline_id}/artifacts").json()[0]
    raw = client.get(f"/api/artifacts/{artifact['id']}/raw")
    assert raw.status_code == 200 and raw.content == scraper.data
    assert raw.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/metrics").json()["versions"] == 1
    assert client.post(f"/api/jobs/{job_id}/retry").status_code == 409


def test_failed_job_retry_creates_new_job_preserving_history(api, db, settings):
    client, sent = api
    repo, scraper, _, service, source_id = setup_pipeline(db, settings)
    scraper.error = PipelineError("HTTP_403")
    job_id = service.discover(repo.reserve_run(source_id))[0]
    assert service.ingest(job_id) == "HTTP_403"
    response = client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 202
    retry_id = response.json()["job_id"]
    assert retry_id != job_id
    assert sent[-1] == ("ingest_guideline", retry_id)
    assert client.post(f"/api/jobs/{job_id}/retry").status_code == 409
    with db() as session:
        assert session.get(IngestionJob, job_id).status == "FAILED"
        assert session.get(IngestionJob, retry_id).attempt_count == 0


def test_broker_failure_retains_pending_run(db, settings, monkeypatch):
    repo, _, _, _, source_id = setup_pipeline(db, settings)
    run_id = repo.reserve_run(source_id)
    module = importlib.import_module("medguide.workers.publishing")
    monkeypatch.setattr(module.app, "send_task", MagicMock(side_effect=OSError("offline")))
    assert publish(repo, "discover_source", run_id) is False
    assert ("discover_source", run_id) in repo.reconcile()
