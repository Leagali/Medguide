import hashlib
import json
import re
import unicodedata

import pymupdf
from bs4 import BeautifulSoup

from medguide.infrastructure.errors import PipelineError
from medguide.scrapers.contracts import ExtractedDocument, ExtractedPage

NORMALIZER_VERSION = "unicode-nfc-whitespace/1"


def extract(data: bytes, media_type: str) -> ExtractedDocument:
    if data.startswith(b"%PDF-"):
        try:
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                if pdf.is_encrypted:
                    raise PipelineError("PDF_ENCRYPTED")
                pages = [
                    ExtractedPage(page_number=i + 1, text=page.get_text("text", sort=True))
                    for i, page in enumerate(pdf)
                ]
            return ExtractedDocument(
                media_type="application/pdf",
                pages=pages,
                extractor_version=f"pymupdf/{pymupdf.VersionBind}",
            )
        except (RuntimeError, ValueError) as exc:
            raise PipelineError("PDF_INVALID") from exc
    if media_type == "text/html":
        soup = BeautifulSoup(data, "lxml")
        content = soup.select_one("[data-guideline-content], .documentText")
        if content is None:
            raise PipelineError("HTML_CONTENT_NOT_FOUND")
        for element in content.select("script, style, nav, noscript"):
            element.decompose()
        return ExtractedDocument(
            media_type="text/html",
            extractor_version="beautifulsoup/1",
            pages=[ExtractedPage(page_number=1, text=content.get_text("\n", strip=True))],
        )
    raise PipelineError("UNSUPPORTED_MEDIA_TYPE")


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[^\S\n]+", " ", value)
    value = "\n".join(line.strip() for line in value.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def content_hash(document: ExtractedDocument) -> str:
    pages = [(page.page_number, normalize(page.text)) for page in document.pages]
    if not any(text for _, text in pages):
        raise PipelineError("EXTRACTION_EMPTY")
    return digest(pages)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def composite_hash(references: list[tuple[str, str, str]]) -> str:
    return digest(sorted(references))
