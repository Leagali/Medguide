from collections.abc import Callable
from dataclasses import dataclass

from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.http import SafeHttpClient
from medguide.infrastructure.settings import CATALOG_URL
from medguide.scrapers.conitec.scraper import ConitecPCDTScraper
from medguide.scrapers.contracts import SourceScraper


@dataclass(frozen=True)
class SourceDefinition:
    code: str
    name: str
    connector_key: str
    base_url: str
    factory: Callable[[SafeHttpClient, str], SourceScraper]
    default_enabled: bool = True


SOURCE_DEFINITIONS = {
    "conitec_pcdt": SourceDefinition(
        code="conitec_pcdt",
        name="CONITEC PCDT",
        connector_key="conitec_pcdt",
        base_url=CATALOG_URL,
        factory=ConitecPCDTScraper,
    ),
}

SCRAPER_REGISTRY: dict[str, Callable[[SafeHttpClient, str], SourceScraper]] = {
    definition.connector_key: definition.factory for definition in SOURCE_DEFINITIONS.values()
}


def resolve_scraper(key: str, client: SafeHttpClient, base_url: str) -> SourceScraper:
    try:
        factory = SCRAPER_REGISTRY[key]
    except KeyError as exc:
        raise PipelineError("UNKNOWN_CONNECTOR") from exc
    return factory(client, base_url)
