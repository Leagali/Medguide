from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.http import SafeHttpClient
from medguide.scrapers.conitec.catalog import parse_catalog
from medguide.scrapers.conitec.documents import fetch_reference
from medguide.scrapers.contracts import DiscoveredGuideline, FetchedDocument


class ConitecPCDTScraper:
    def __init__(self, client: SafeHttpClient, catalog_url: str) -> None:
        self.client = client
        self.catalog_url = catalog_url

    def discover(self) -> list[DiscoveredGuideline]:
        resource = self.client.get(self.catalog_url)
        return parse_catalog(resource.data, resource.url)

    def fetch_documents(self, item: DiscoveredGuideline) -> list[FetchedDocument]:
        try:
            return [fetch_reference(self.client, ref) for ref in item.document_refs]
        except PipelineError as exc:
            if exc.code not in ("HTTP_404", "DOCUMENT_LINK_NOT_FOUND"):
                raise
            # Re-resolve expired references using durable catalogue identity, once.
            refreshed = next(
                (
                    candidate
                    for candidate in self.discover()
                    if candidate.external_key == item.external_key
                ),
                None,
            )
            if refreshed is None or refreshed.document_refs == item.document_refs:
                raise
            return [fetch_reference(self.client, ref) for ref in refreshed.document_refs]
