from urllib.parse import urljoin

from bs4 import BeautifulSoup

from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.http import SafeHttpClient
from medguide.scrapers.contracts import DocumentReference, FetchedDocument


def fetch_reference(client: SafeHttpClient, ref: DocumentReference) -> FetchedDocument:
    allowed_context = {"unavailable"}
    if set(ref.source_context) - allowed_context:
        raise PipelineError("INVALID_SOURCE_CONTEXT")
    if ref.source_url is None:
        raise PipelineError("DOCUMENT_UNAVAILABLE")
    url = str(ref.source_url)
    visited: set[str] = set()
    for _ in range(5):
        if url in visited:
            raise PipelineError("DOCUMENT_NAVIGATION_CYCLE")
        visited.add(url)
        resource = client.get(url)
        if resource.data.startswith(b"%PDF-"):
            return FetchedDocument(
                ref.reference_key, ref.role, resource.url, resource.data, "application/pdf"
            )
        if resource.media_type not in ("text/html", "application/xhtml+xml"):
            raise PipelineError("INVALID_DOCUMENT_SIGNATURE")
        soup = BeautifulSoup(resource.data, "lxml")
        main = soup.select_one("#content-core") or soup.select_one("article") or soup
        download = main.select_one(
            "a[href$='@@download/file'], a[href$='/download'], a[href$='.pdf'], "
            "a[data-medguide-document]"
        )
        if download:
            url = urljoin(resource.url, str(download["href"]))
            continue
        # Only an explicitly marked official HTML document is accepted as content.
        if main.select_one(".documentText, [data-guideline-content]"):
            return FetchedDocument(
                ref.reference_key, ref.role, resource.url, resource.data, "text/html"
            )
        raise PipelineError("DOCUMENT_LINK_NOT_FOUND")
    raise PipelineError("DOCUMENT_NAVIGATION_LIMIT")
