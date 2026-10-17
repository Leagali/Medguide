import httpx
from sqlalchemy import select

from medguide.domain.models import GuidelineVersion, Source
from medguide.infrastructure.http import SafeHttpClient
from medguide.scrapers.conitec.documents import fetch_reference
from medguide.scrapers.contracts import DiscoveredGuideline
from medguide.scrapers.registry import SCRAPER_REGISTRY, resolve_scraper
from tests.integration.test_ingestion import setup_pipeline


def test_second_registered_scraper_uses_three_steps_without_pipeline_changes(
    db, settings, monkeypatch
):
    repo, fixture, storage, service, source_id = setup_pipeline(db, settings)
    visited = []

    def handler(request):
        path = request.url.path
        visited.append(path)
        if path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if path == "/detail":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text='<article><a data-medguide-document href="/intermediate">PDF</a></article>',
            )
        if path == "/intermediate":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text='<article><a href="/final.pdf">Download</a></article>',
            )
        return httpx.Response(
            200, content=fixture.data, headers={"content-type": "application/pdf"}
        )

    class ThreeStepScraper:
        def __init__(self, client, base_url):
            self.client = client

        def discover(self):
            data = fixture.items[0].model_dump(mode="json")
            data["source_key"] = "three_step_test"
            data["document_refs"][0]["source_url"] = "https://www.gov.br/detail"
            return [DiscoveredGuideline.model_validate(data)]

        def fetch_documents(self, candidate):
            return [fetch_reference(self.client, ref) for ref in candidate.document_refs]

    monkeypatch.setitem(SCRAPER_REGISTRY, "three_step_test", ThreeStepScraper)
    with db.begin() as session:
        session.get(Source, source_id).connector_key = "three_step_test"
    with SafeHttpClient(
        settings, transport=httpx.MockTransport(handler), resolver=lambda _: ["8.8.8.8"]
    ) as client:
        service.scraper_factory = lambda source: resolve_scraper(
            source.connector_key, client, source.base_url
        )
        jobs = service.discover(repo.reserve_run(source_id))
        assert service.ingest(jobs[0]) == "VERSION_CREATED"
    assert visited == ["/robots.txt", "/detail", "/intermediate", "/final.pdf"]
    with db() as session:
        assert session.scalar(select(GuidelineVersion.observed_version)) == 1
