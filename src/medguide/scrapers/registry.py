from collections.abc import Callable

from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.http import SafeHttpClient
from medguide.scrapers.conitec.scraper import ConitecPCDTScraper
from medguide.scrapers.contracts import SourceScraper

SCRAPER_REGISTRY: dict[str, Callable[[SafeHttpClient, str], SourceScraper]] = {
    "conitec_pcdt": ConitecPCDTScraper,
}


def resolve_scraper(key: str, client: SafeHttpClient, base_url: str) -> SourceScraper:
    try:
        factory = SCRAPER_REGISTRY[key]
    except KeyError as exc:
        raise PipelineError("UNKNOWN_CONNECTOR") from exc
    return factory(client, base_url)
