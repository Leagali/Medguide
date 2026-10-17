import hashlib
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl

from medguide.infrastructure.errors import PipelineError
from medguide.scrapers.contracts import DiscoveredGuideline, DocumentReference

DATE = r"(\d{1,2}/\d{1,2}/\d{4})"
NOTE = re.compile(
    r"(?:anexo\s+alterado|alterad[oa]|retificad[oa]|portaria\s+atualizada)\s+em\s*" + DATE, re.I
)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        day, month, year = map(int, value.split("/"))
        return date(year, month, day)
    except ValueError:
        return None


def identity(title: str) -> str:
    # The catalogue provides no durable ID. Use the clinical title, excluding change notes.
    stable = NOTE.sub("", title)
    stable = unicodedata.normalize("NFKD", stable).encode("ascii", "ignore").decode().lower()
    stable = re.sub(r"[^a-z0-9]+", "-", stable).strip("-")
    return stable[:140] + "-" + hashlib.sha256(stable.encode()).hexdigest()[:12]


def parse_catalog(html: str | bytes, catalog_url: str) -> list[DiscoveredGuideline]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one("#parent-fieldname-text") or soup.select_one("article") or soup
    items: dict[str, DiscoveredGuideline] = {}
    for row in container.select("table tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        first: Tag = cells[0]
        title = first.get_text(" ", strip=True)
        if not title or len(title) < 3:
            continue
        links = first.select("a[href]")
        # Missing links still produce a durable candidate requiring explicit review.
        clean_title = re.split(
            r"\s*\(?\s*(?:Anexo alterado|Alterado em|Portaria atualizada)", title, flags=re.I
        )[0].rstrip(" -(")
        key = identity(clean_title)
        refs: list[DocumentReference] = []
        seen: set[str] = set()
        for index, link in enumerate(links):
            url = urljoin(catalog_url, str(link["href"]))
            if url in seen or urlsplit(url).scheme not in ("https", "http"):
                continue
            seen.add(url)
            refs.append(
                DocumentReference(
                    reference_key="main" if index == 0 else f"annex-{index}",
                    role="main" if index == 0 else "annex",
                    source_url=HttpUrl(url),
                    media_hint="pdf" if ".pdf" in url.lower() else "unknown",
                )
            )
        text = " ".join(row.stripped_strings)
        note = NOTE.search(text)
        published = re.search(r"publicad[oa]\s*(?:em)?\s*" + DATE, text, re.I)
        # Explicit annex links outside the title cell, never the Portaria/summary columns.
        for link in row.select("a[href]"):
            label = link.get_text(" ", strip=True)
            url = urljoin(catalog_url, str(link["href"]))
            if re.search(r"\banexo\b", label, re.I) and url not in seen:
                seen.add(url)
                refs.append(
                    DocumentReference(
                        reference_key=f"annex-{len(refs)}", role="annex", source_url=HttpUrl(url)
                    )
                )
        if not refs:
            refs = [
                DocumentReference(
                    reference_key="main",
                    role="main",
                    source_context={"unavailable": "no_document_link"},
                )
            ]
        item = DiscoveredGuideline(
            source_key="conitec_pcdt",
            external_key=key,
            title=clean_title,
            catalog_url=HttpUrl(catalog_url),
            publication_date=parse_date(published[1] if published else None),
            change_date=parse_date(note[1] if note else None),
            source_change_note=note[0] if note else None,
            source_metadata={"catalog_title": title, "catalog_row": text},
            document_refs=refs,
        )
        if key in items and items[key] != item:
            raise PipelineError("CATALOG_IDENTITY_COLLISION")
        items[key] = item
    if not items:
        raise PipelineError("CATALOG_SCHEMA_INCOMPATIBLE")
    return list(items.values())
