from datetime import date

import pytest
from pydantic import ValidationError

from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.settings import CATALOG_URL
from medguide.scrapers.conitec.catalog import parse_catalog
from medguide.scrapers.contracts import DiscoveredGuideline


def test_representative_catalog(fixture_dir):
    items = parse_catalog((fixture_dir / "catalog.html").read_bytes(), CATALOG_URL)
    assert len(items) == 6
    asthma, arthritis, corrected, missing, multiple, alternate = items
    assert asthma.title == "Asma"
    assert asthma.change_date == date(2026, 9, 4)
    assert asthma.publication_date == date(2026, 4, 2)
    assert "Anexo alterado" in asthma.source_change_note
    assert arthritis.change_date == date(2026, 5, 20)
    assert corrected.change_date == date(2024, 12, 5)
    assert missing.publication_date is None
    assert missing.document_refs[0].source_url is None
    assert len(multiple.document_refs) == 3
    assert alternate.title == "Variação de layout"


def test_identity_does_not_depend_on_url_or_note(fixture_dir):
    html = (fixture_dir / "catalog.html").read_text(encoding="utf-8")
    before = parse_catalog(html, CATALOG_URL)[0]
    after = parse_catalog(
        html.replace("04/09/2026", "10/10/2026").replace("asma.pdf", "asma-v2.pdf"), CATALOG_URL
    )[0]
    assert before.external_key == after.external_key


def test_incompatible_layout_fails_instead_of_empty_success():
    with pytest.raises(PipelineError, match="CATALOG_SCHEMA_INCOMPATIBLE"):
        parse_catalog("<html>maintenance</html>", CATALOG_URL)


def test_contract_rejects_duplicate_reference_keys(fixture_dir):
    item = parse_catalog((fixture_dir / "catalog.html").read_bytes(), CATALOG_URL)[0]
    payload = item.model_dump(mode="json")
    payload["document_refs"] *= 2
    with pytest.raises(ValidationError, match="Duplicate"):
        DiscoveredGuideline.model_validate(payload)


def test_official_catalog_snapshot(fixture_dir):
    items = parse_catalog((fixture_dir / "conitec_snapshot.html").read_bytes(), CATALOG_URL)
    assert len(items) == 4
    titles = {item.title: item for item in items}
    assert titles["Asma"].change_date == date(2026, 9, 4)
    assert titles["Artrite Reumatoide"].change_date == date(2026, 5, 20)
    assert titles["Câncer de Mama"].change_date == date(2024, 12, 5)


def test_annex_keys_are_stable_when_links_reorder():
    main = '<a href="/main.pdf">Diretriz</a>'
    a = '<a href="/a.pdf">Anexo A</a>'
    b = '<a href="/b.pdf">Anexo B</a>'

    def parse(links):
        return parse_catalog(
            f"<table><tr><td>{links}</td><td>Sem data</td></tr></table>", CATALOG_URL
        )[0]

    before, after = parse(main + a + b), parse(main + b + a)
    assert before.external_key == after.external_key
    assert {r.reference_key: str(r.source_url) for r in before.document_refs} == {
        r.reference_key: str(r.source_url) for r in after.document_refs
    }
