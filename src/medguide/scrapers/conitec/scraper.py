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
        return [fetch_reference(self.client, ref) for ref in item.document_refs]
