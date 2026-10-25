"""Contratos do demonstrador; não acessa banco, Redis ou site oficial."""

from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from demo.conitec.app import Backend, create_app


def setup_demo():
    source_id, gid, version_id, old_id, artifact_id, wrong_artifact = (
        str(uuid4()) for _ in range(6)
    )
    calls = []
    guideline = {
        "id": gid,
        "source_id": source_id,
        "title": "Diretriz de demonstração",
        "external_key": "diretriz-teste",
        "current_version_id": old_id,
    }
    versions = [
        {
            "id": version_id,
            "observed_version": 2,
            "detected_at": "2026-10-23T12:00:00Z",
            "extracted_text": "Texto da versão dois",
        },
        {
            "id": old_id,
            "observed_version": 1,
            "detected_at": "2026-10-17T12:00:00Z",
            "extracted_text": "Texto corrente após reversão",
        },
    ]

    def handler(request):
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path == "/api/sources":
            return httpx.Response(
                200, json=[{"id": source_id, "code": "conitec_pcdt", "enabled": True}]
            )
        if path == "/api/guidelines":
            return httpx.Response(200, json=[guideline])
        if path == f"/api/guidelines/{gid}":
            return httpx.Response(200, json=guideline)
        if path.endswith("/versions"):
            return httpx.Response(200, json=versions)
        if path.endswith("/artifacts"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": wrong_artifact,
                        "role": "main",
                        "reference_key": "main",
                        "pages_json": [{"page_number": 1, "text": "PDF mais novo, versão errada"}],
                    },
                    {
                        "id": artifact_id,
                        "role": "main",
                        "reference_key": "main",
                        "pages_json": [{"page_number": 1, "text": "PDF da versão corrente"}],
                    },
                ],
            )
        if path == "/api/runs" or path == "/api/jobs":
            return httpx.Response(200, json=[])
        if path.endswith("/discover"):
            return httpx.Response(202, json={"run_id": str(uuid4()), "published": False})
        if path == f"/api/artifacts/{artifact_id}/raw":
            return httpx.Response(200, content=b"%PDF-original-correto")
        return httpx.Response(404)

    backend = Backend(
        httpx.AsyncClient(base_url="http://api", transport=httpx.MockTransport(handler))
    )
    app = create_app(
        backend, links=lambda vid, _: [artifact_id] if vid == old_id else [wrong_artifact]
    )
    return app, gid, old_id, artifact_id, wrong_artifact, calls


def test_current_version_reversion_never_uses_latest_unrelated_pdf():
    app, gid, vid, aid, wrong, calls = setup_demo()
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get(f"/demo-api/guidelines/{gid}")
        assert response.status_code == 200
        assert response.json()["version"]["id"] == vid
        assert [a["id"] for a in response.json()["documents"]] == [aid]
        assert (
            client.get(f"/demo-api/guidelines/{gid}/pdf/{wrong}?version_id={vid}").status_code
            == 404
        )
        assert ("GET", f"/api/artifacts/{wrong}/raw") not in calls
        pdf = client.get(f"/demo-api/guidelines/{gid}/pdf/{aid}?version_id={vid}")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
        assert pdf.headers["content-type"] == "application/pdf"


def test_discovery_requires_page_header_and_reports_deferred_publication():
    app, _, _, _, _, calls = setup_demo()
    with TestClient(app, base_url="http://localhost") as client:
        assert client.post("/demo-api/discover").status_code == 403
        assert (
            client.post(
                "/demo-api/discover",
                headers={"X-MedGuide-Demo": "1", "Origin": "https://another-site.test"},
            ).status_code
            == 403
        )
        assert not any(path.endswith("/discover") for _, path in calls)
        response = client.post("/demo-api/discover", headers={"X-MedGuide-Demo": "1"})
        assert response.status_code == 202
        assert response.json()["published"] is False


def test_offline_backend_returns_actionable_error_without_fake_counts():
    def offline(request):
        raise httpx.ConnectError("offline", request=request)

    backend = Backend(
        httpx.AsyncClient(base_url="http://api", transport=httpx.MockTransport(offline))
    )
    with TestClient(create_app(backend), base_url="http://localhost") as client:
        response = client.get("/demo-api/state")
        assert response.status_code == 503
        assert "Compose" in response.json()["detail"]
        assert "counts" not in response.json()


def test_unregistered_temporary_sample_cannot_read_files():
    app, _, _, _, _, _ = setup_demo()
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get(f"/demo-api/sample/{uuid4()}/pdf").status_code == 404
        assert client.get("/demo-api/sample/not-an-id/result").status_code == 422


def test_pagination_reads_beyond_first_200_records():
    offsets = []

    def handler(request):
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(
            200,
            json=[{"code": "other"}] * 200
            if not offset
            else [{"code": "conitec_pcdt", "id": str(uuid4()), "enabled": True}],
        )

    backend = Backend(
        httpx.AsyncClient(base_url="http://api", transport=httpx.MockTransport(handler))
    )
    # O estado falha depois da fonte, pois o stub de paginação não fornece os demais
    # contratos. A prova é buscar a fonte com asyncio, sem usar um acervo real.
    import asyncio

    async def check():
        try:
            assert (await backend.source())["code"] == "conitec_pcdt"
        finally:
            await backend.client.aclose()

    asyncio.run(check())
    assert offsets == [0, 200]
