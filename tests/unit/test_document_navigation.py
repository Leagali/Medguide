import httpx
import pytest

from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.http import SafeHttpClient
from medguide.scrapers.conitec.scraper import ConitecPCDTScraper
from tests.integration.test_ingestion import FixtureScraper


def test_expired_document_url_resolved_from_durable_catalog_identity(settings, monkeypatch):
    fixture = FixtureScraper()
    candidate = fixture.items[0]
    payload = candidate.model_dump(mode="json")
    payload["document_refs"][0]["source_url"] = "https://www.gov.br/current.pdf"
    updated = type(candidate).model_validate(payload)
    requests = []

    def handler(request):
        requests.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/a.pdf":
            return httpx.Response(404)
        return httpx.Response(200, content=fixture.data)

    with SafeHttpClient(
        settings, transport=httpx.MockTransport(handler), resolver=lambda _: ["8.8.8.8"]
    ) as client:
        scraper = ConitecPCDTScraper(client, str(candidate.catalog_url))
        monkeypatch.setattr(scraper, "discover", lambda: [updated])
        assert scraper.fetch_documents(candidate)[0].data == fixture.data
    assert requests == ["/robots.txt", "/a.pdf", "/current.pdf"]


def test_403_is_not_bypassed_or_refreshed(settings, monkeypatch):
    candidate = FixtureScraper().items[0]
    with SafeHttpClient(
        settings,
        transport=httpx.MockTransport(lambda _: httpx.Response(403)),
        resolver=lambda _: ["8.8.8.8"],
    ) as client:
        scraper = ConitecPCDTScraper(client, str(candidate.catalog_url))
        monkeypatch.setattr(scraper, "discover", lambda: pytest.fail("must not refresh on 403"))
        with pytest.raises(PipelineError, match="HTTP_403"):
            scraper.fetch_documents(candidate)
