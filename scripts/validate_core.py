"""Read-only audit of collected guidelines, original files, text and API responses."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pymupdf
from sqlalchemy import func, select

from medguide.domain.models import (
    Artifact,
    CollectionRun,
    Guideline,
    GuidelineVersion,
    IngestionJob,
    Source,
    VersionArtifact,
)
from medguide.infrastructure.db import session_factory
from medguide.infrastructure.settings import get_settings
from medguide.infrastructure.storage import FileStorage
from medguide.ingestion.text import composite_hash, content_hash, extract, normalize
from medguide.scrapers.contracts import ExtractedDocument


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/medguide-core-validation"))
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    storage = FileStorage(settings.storage_root)
    report = {"checked_at": datetime.now(UTC).isoformat(), "checks": {}, "samples": []}
    with session_factory()() as session:
        counts = {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (
                Source,
                CollectionRun,
                Guideline,
                IngestionJob,
                Artifact,
                GuidelineVersion,
            )
        }
        report["counts"] = counts
        report["jobs_by_status"] = dict(
            session.execute(
                select(IngestionJob.status, func.count()).group_by(IngestionJob.status)
            ).all()
        )
        artifacts = list(session.scalars(select(Artifact).order_by(Artifact.id)))
        assert artifacts, "No downloaded artifacts to audit"
        pages, byte_count = 0, 0
        for index, artifact in enumerate(artifacts, 1):
            original = storage.read(artifact.storage_key)
            assert hashlib.sha256(original).hexdigest() == artifact.raw_sha256
            assert len(original) == artifact.size_bytes, f"Size mismatch: {artifact.id}"
            assert artifact.extraction_status == "EXTRACTED", f"Extraction pending: {artifact.id}"
            saved = ExtractedDocument(
                media_type=artifact.media_type,
                pages=artifact.pages_json,
                extractor_version=artifact.extractor_version,
            )
            assert content_hash(saved) == artifact.content_sha256, (
                f"Page hash mismatch: {artifact.id}"
            )
            fresh = extract(original, artifact.media_type)
            assert content_hash(fresh) == artifact.content_sha256, (
                f"Re-extraction mismatch: {artifact.id}"
            )
            pages += len(fresh.pages)
            byte_count += len(original)
            if index % 20 == 0:
                print(f"Verified {index}/{len(artifacts)} originals and extractions", flush=True)
        report["checks"]["originals_and_reextractions_verified"] = len(artifacts)
        report["total_pages"] = pages
        report["total_bytes"] = byte_count
        versions = list(session.scalars(select(GuidelineVersion)))
        assert versions, "No persisted text versions"
        for version in versions:
            linked = list(
                session.scalars(
                    select(Artifact)
                    .join(VersionArtifact, VersionArtifact.artifact_id == Artifact.id)
                    .where(VersionArtifact.version_id == version.id)
                )
            )
            assert linked, f"Version without originals: {version.id}"
            assert (
                composite_hash([(a.reference_key, a.role, a.content_sha256) for a in linked])
                == version.composite_content_sha256
            )
            expected_text = "\n\n".join(
                f"[{a.reference_key}]\n"
                + "\n\n".join(
                    f"[p.{page['page_number']}]\n{normalize(page['text'])}" for page in a.pages_json
                )
                for a in sorted(linked, key=lambda a: a.reference_key)
            )
            assert version.extracted_text == expected_text, f"Version text mismatch: {version.id}"
        report["checks"]["version_hashes_and_full_text_verified"] = len(versions)
        report["total_text_characters"] = sum(len(v.extracted_text) for v in versions)
        report["unicode_replacement_characters"] = sum(
            v.extracted_text.count("\ufffd") for v in versions
        )
        selected = []
        for guideline, version in session.execute(
            select(Guideline, GuidelineVersion)
            .join(GuidelineVersion, Guideline.current_version_id == GuidelineVersion.id)
            .order_by(Guideline.title)
        ):
            if guideline.title.casefold() in {
                "asma",
                "diabete melito tipo 2",
                "câncer de mama",
                "acidentes escorpiônicos",
            }:
                selected.append((guideline, version))
        assert selected, "No representative text samples found"
        token = settings.admin_token.get_secret_value()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        with httpx.Client(
            base_url=args.api_url, headers=headers, trust_env=False, timeout=60
        ) as client:
            for route in ("/docs", "/openapi.json", "/healthz", "/readyz"):
                assert client.get(route).status_code == 200, route
            report["checks"]["public_http_routes"] = "passed"
            if token:
                assert (
                    client.get(
                        "/api/guidelines", headers={"Authorization": "Bearer invalid"}
                    ).status_code
                    == 401
                )
            for guideline, version in selected:
                text_path = args.output / f"{guideline.external_key}.txt"
                text_path.write_text(version.extracted_text, encoding="utf-8")
                linked = session.scalar(
                    select(Artifact)
                    .join(VersionArtifact, VersionArtifact.artifact_id == Artifact.id)
                    .where(VersionArtifact.version_id == version.id)
                    .limit(1)
                )
                assert linked is not None
                sample = {
                    "title": guideline.title,
                    "characters": len(version.extracted_text),
                    "pages": len(linked.pages_json),
                    "source_url": linked.source_url,
                    "text_file": text_path.name,
                    "opening": version.extracted_text[:600],
                    "middle": version.extracted_text[len(version.extracted_text) // 2 :][:600],
                }
                if token:
                    response = client.get(f"/api/guidelines/{guideline.id}/versions")
                    assert response.status_code == 200
                    api_version = next(v for v in response.json() if v["id"] == version.id)
                    assert api_version["extracted_text"] == version.extracted_text
                    raw = client.get(f"/api/artifacts/{linked.id}/raw")
                    assert raw.status_code == 200 and raw.content == storage.read(
                        linked.storage_key
                    )
                    sample["authenticated_api_text_and_pdf"] = "passed"
                report["samples"].append(sample)
            report["checks"]["authenticated_api"] = "passed" if token else "not configured"
        first = selected[0]
        artifact = session.scalar(
            select(Artifact).where(Artifact.guideline_id == first[0].id).limit(1)
        )
        with pymupdf.open(stream=storage.read(artifact.storage_key), filetype="pdf") as pdf:
            pdf[min(5, len(pdf) - 1)].get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(
                args.output / "sample-original-page.png"
            )
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "samples"},
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    print("Exported full text samples and one original PDF page for visual inspection.")


if __name__ == "__main__":
    main()
