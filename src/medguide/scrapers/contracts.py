from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class DocumentReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    reference_key: str = Field(min_length=1, max_length=200)
    role: Literal["main", "annex", "supplement"]
    source_url: HttpUrl | None = None
    media_hint: Literal["pdf", "html", "unknown"] = "unknown"
    source_context: dict[str, str] = Field(default_factory=dict)


class DiscoveredGuideline(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_key: str = Field(min_length=1, max_length=80)
    external_key: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=2000)
    catalog_url: HttpUrl
    publication_date: date | None = None
    change_date: date | None = None
    source_change_note: str | None = None
    source_metadata: dict[str, str] = Field(default_factory=dict)
    document_refs: list[DocumentReference] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_references(self) -> "DiscoveredGuideline":
        keys = [ref.reference_key for ref in self.document_refs]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate document reference_key")
        return self


@dataclass(frozen=True)
class FetchedDocument:
    reference_key: str
    role: str
    source_url: str
    data: bytes
    media_type: str


class ExtractedPage(BaseModel):
    page_number: int = Field(ge=1)
    text: str


class ExtractedDocument(BaseModel):
    media_type: str
    pages: list[ExtractedPage]
    extractor_version: str


class SourceScraper(Protocol):
    def discover(self) -> list[DiscoveredGuideline]: ...
    def fetch_documents(self, item: DiscoveredGuideline) -> list[FetchedDocument]: ...
