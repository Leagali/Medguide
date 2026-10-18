import pytest

from medguide.infrastructure.storage import FileStorage
from medguide.ingestion.text import composite_hash, content_hash, extract, normalize
from tests.integration.test_ingestion import pdf_bytes


def test_normalizer_preserves_clinical_values_paragraphs_and_unicode():
    assert normalize("Dose:  5\u00a0mg/dia\r\n\r\nNão usar: 10 mmol/L.\n") == (
        "Dose: 5 mg/dia\n\nNão usar: 10 mmol/L."
    )
    assert normalize("cafe\u0301") == "café"


def test_composite_is_order_independent_but_includes_reference_and_role():
    a, b = ("main", "main", "hash-a"), ("annex", "annex", "hash-b")
    assert composite_hash([a, b]) == composite_hash([b, a])
    assert composite_hash([a, b]) != composite_hash([a, ("other", "annex", "hash-b")])


def test_pdf_signature_overrides_mime_and_binary_metadata_is_not_content():
    a = extract(pdf_bytes(metadata="A"), "application/octet-stream")
    b = extract(pdf_bytes(metadata="B"), "application/pdf")
    assert content_hash(a) == content_hash(b)


def test_html_extracts_only_explicit_content():
    document = extract(
        b"<main data-guideline-content>Dose: 5 mg<script>evil()</script></main>", "text/html"
    )
    assert document.pages[0].text == "Dose: 5 mg"


def test_storage_integrity_and_path_traversal(settings):
    storage = FileStorage(settings.storage_root)
    key, digest = storage.put(b"original")
    assert storage.put(b"original") == (key, digest)
    storage.path(key).write_bytes(b"corrupt")
    with pytest.raises(OSError, match="integrity"):
        storage.read(key)
    with pytest.raises(ValueError):
        storage.read("../../secret")
