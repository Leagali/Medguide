"""Página local exclusiva para o vídeo; não integra o frontend final do MedGuide."""

import asyncio
import json
import os
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.middleware.trustedhost import TrustedHostMiddleware

from medguide.domain.models import GuidelineVersion, VersionArtifact
from medguide.infrastructure.db import session_factory
from medguide.infrastructure.settings import get_settings

HERE = Path(__file__).resolve().parent


class Backend:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(
            base_url=os.getenv("MEDGUIDE_DEMO_API_URL", "http://127.0.0.1:8000"),
            headers={"Authorization": f"Bearer {get_settings().admin_token.get_secret_value()}"},
            timeout=45,
            trust_env=False,
        )

    async def request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            result = await self.client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise HTTPException(503, "API indisponível. Inicie os serviços do Compose.") from exc
        if result.status_code in (401, 403):
            raise HTTPException(503, "Confira MEDGUIDE_ADMIN_TOKEN no ambiente do demonstrador.")
        if result.status_code >= 400:
            messages = {
                404: "Registro não encontrado no acervo.",
                409: "A fonte está desabilitada ou há um conflito de execução. Confira o status.",
                503: "Backend indisponível. Confira configuração, banco, Redis e armazenamento.",
            }
            raise HTTPException(
                result.status_code, messages.get(result.status_code, "A API recusou a operação.")
            )
        return result

    async def data(self, path: str, **params: object) -> object:
        return (await self.request("GET", path, params=params)).json()

    async def all(self, path: str, **params: object) -> list[dict]:
        records = []
        offset = 0
        while True:
            page = await self.data(path, limit=200, offset=offset, **params)
            records.extend(page)
            if len(page) < 200:
                return records
            offset += len(page)

    async def source(self) -> dict:
        for source in await self.all("/api/sources"):
            if source["code"] == "conitec_pcdt":
                return source
        raise HTTPException(503, "CONITEC não cadastrada. Execute sources bootstrap no projeto.")

    async def guideline(self, identifier: UUID) -> dict:
        source = await self.source()
        item = await self.data(f"/api/guidelines/{identifier}")
        if item["source_id"] != source["id"]:
            raise HTTPException(404, "Diretriz fora da fonte CONITEC.")
        return item


def linked_artifacts(version_id: str, guideline_id: str) -> list[str]:
    # A API não expõe os vínculos de versão. Esta consulta é somente de leitura;
    # evita mostrar um PDF de outra versão, inclusive após reversão de conteúdo.
    with session_factory()() as session:
        return list(
            session.scalars(
                select(VersionArtifact.artifact_id)
                .join(GuidelineVersion, GuidelineVersion.id == VersionArtifact.version_id)
                .where(
                    VersionArtifact.version_id == version_id,
                    GuidelineVersion.guideline_id == guideline_id,
                )
            )
        )


class Samples:
    """Uma execução por vez, arquivos e SQLite exclusivos em diretório temporário."""

    def __init__(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="medguide-video-")
        self.jobs: dict[str, Path] = {}
        self.active: str | None = None
        self.tasks: set[asyncio.Task] = set()
        self.processes: set[asyncio.subprocess.Process] = set()

    def state(self, identifier: str) -> dict:
        root = self.jobs.get(identifier)
        if root is None:
            raise HTTPException(404, "Ensaio não encontrado nesta sessão do demonstrador.")
        return json.loads((root / "state.json").read_text(encoding="utf-8"))

    async def start(self, external_key: str | None) -> str:
        if self.active:
            return self.active
        if len(self.jobs) >= 6:
            raise HTTPException(409, "Limite de 6 ensaios por sessão. Reinicie o demonstrador.")
        identifier = str(uuid4())
        root = Path(self.directory.name) / identifier
        root.mkdir()
        self.jobs[identifier] = root
        self.active = identifier
        (root / "state.json").write_text(
            json.dumps({"status": "RUNNING", "stage": "DISCOVERY", "events": []}),
            encoding="utf-8",
        )
        task = asyncio.create_task(self.run(identifier, external_key))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return identifier

    async def run(self, identifier: str, external_key: str | None) -> None:
        root = self.jobs[identifier]
        env = os.environ.copy()
        env.pop("MEDGUIDE_ADMIN_TOKEN", None)
        env["MEDGUIDE_DATABASE_URL"] = f"sqlite:///{root / 'sample.db'}"
        env["MEDGUIDE_STORAGE_ROOT"] = str(root / "raw")
        process = None
        failure = None
        try:
            with (root / "worker.log").open("wb") as log:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(HERE / "sample_worker.py"),
                    str(root),
                    external_key or "",
                    env=env,
                    stdout=log,
                    stderr=log,
                )
                self.processes.add(process)
                await asyncio.wait_for(process.wait(), timeout=180)
                if process.returncode != 0 or self.state(identifier)["status"] == "RUNNING":
                    failure = "O ensaio não concluiu. Consulte worker.log ou tente novamente."
        except TimeoutError:
            failure = "Tempo de 3 minutos excedido. A fonte pode estar lenta; tente novamente."
        except asyncio.CancelledError:
            raise
        except OSError:
            failure = "Não foi possível iniciar o processo temporário de extração."
        finally:
            if process:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                self.processes.discard(process)
            if failure:
                state = self.state(identifier)
                state.update(status="FAILED", error=failure)
                (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
            self.active = None

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.directory.cleanup()


class SampleRequest(BaseModel):
    external_key: str | None = Field(default=None, max_length=200)


def create_app(
    backend: Backend | None = None,
    links: Callable[[str, str], list[str]] = linked_artifacts,
) -> FastAPI:
    api = backend or Backend()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.samples = Samples()
        yield
        await app.state.samples.close()
        await api.client.aclose()

    app = FastAPI(title="MedGuide — demonstração para o vídeo", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def local_controls(request: Request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin")
            if request.headers.get("x-medguide-demo") != "1" or (
                origin and urlsplit(origin).netloc != request.headers.get("host")
            ):
                return JSONResponse({"detail": "Inicie a operação pela página local."}, 403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/")
    async def index():
        return FileResponse(HERE / "static" / "index.html")

    @app.get("/demo-api/state")
    async def state():
        source = await api.source()
        guidelines, runs, jobs = await asyncio.gather(
            api.all("/api/guidelines", source_id=source["id"]),
            api.data("/api/runs", source_id=source["id"], limit=1),
            api.all("/api/jobs"),
        )
        identifiers = {g["id"] for g in guidelines}
        relevant = [j for j in jobs if j["guideline_id"] in identifiers]
        latest = {}
        for job in relevant:  # API ordena os jobs do mais recente para o mais antigo.
            latest.setdefault(job["guideline_id"], job)
        for guideline in guidelines:
            job = latest.get(guideline["id"])
            guideline["job"] = (
                {k: job[k] for k in ("id", "status", "stage", "last_error", "attempt_count")}
                if job
                else None
            )
        counts = Counter(j["status"] for j in relevant)
        return {
            "source": source,
            "guidelines": guidelines,
            "latest_run": runs[0] if runs else None,
            "counts": {
                "guidelines": len(guidelines),
                "with_text": sum(bool(g["current_version_id"]) for g in guidelines),
                "pending": counts["PENDING"] + counts["PROCESSING"],
                "review": counts["FAILED"] + counts["NEEDS_REVIEW"],
            },
            "checked_at": datetime.now(UTC).isoformat(),
        }

    @app.post("/demo-api/discover", status_code=202)
    async def discover():
        source = await api.source()
        return (await api.request("POST", f"/api/sources/{source['id']}/discover")).json()

    @app.get("/demo-api/guidelines/{identifier}")
    async def detail(identifier: UUID, version_id: UUID | None = None):
        guideline = await api.guideline(identifier)
        versions = await api.all(f"/api/guidelines/{identifier}/versions")
        selected_id = str(version_id) if version_id else guideline["current_version_id"]
        selected = next((v for v in versions if v["id"] == selected_id), None)
        if version_id and selected is None:
            raise HTTPException(404, "Versão não encontrada para esta diretriz.")
        documents = []
        if selected:
            try:
                ids = await asyncio.to_thread(links, selected["id"], str(identifier))
            except Exception as exc:
                raise HTTPException(
                    503, "Não foi possível ler os vínculos da versão no banco."
                ) from exc
            documents = [
                a
                for a in await api.all(f"/api/guidelines/{identifier}/artifacts")
                if a["id"] in ids
            ]
            documents.sort(key=lambda a: (a["role"] != "main", a["reference_key"]))
        return {
            "guideline": guideline,
            "versions": [
                {k: v[k] for k in ("id", "observed_version", "detected_at")} for v in versions
            ],
            "version": selected,
            "documents": documents,
            "scope": "archive",
        }

    @app.get("/demo-api/guidelines/{identifier}/pdf/{artifact_id}")
    async def pdf(identifier: UUID, artifact_id: UUID, version_id: UUID):
        guideline = await api.guideline(identifier)
        try:
            ids = await asyncio.to_thread(links, str(version_id), guideline["id"])
        except Exception as exc:
            raise HTTPException(503, "Vínculo do documento indisponível.") from exc
        if str(artifact_id) not in ids:
            raise HTTPException(404, "Este original não pertence à versão selecionada.")
        original = await api.request("GET", f"/api/artifacts/{artifact_id}/raw")
        if not original.content.startswith(b"%PDF-"):
            raise HTTPException(422, "O original não é um PDF.")
        return Response(
            original.content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="medguide-{artifact_id}.pdf"'},
        )

    @app.post("/demo-api/sample", status_code=202)
    async def sample(payload: SampleRequest):
        identifier = await app.state.samples.start(payload.external_key)
        return {"id": identifier, "scope": "temporary"}

    @app.get("/demo-api/sample/{identifier}")
    async def sample_state(identifier: UUID):
        return app.state.samples.state(str(identifier))

    @app.get("/demo-api/sample/{identifier}/result")
    async def sample_result(identifier: UUID):
        if app.state.samples.state(str(identifier))["status"] != "COMPLETED":
            raise HTTPException(409, "A extração temporária ainda não concluiu.")
        root = app.state.samples.jobs[str(identifier)]
        return json.loads((root / "result.json").read_text(encoding="utf-8"))

    @app.get("/demo-api/sample/{identifier}/pdf")
    async def sample_pdf(identifier: UUID):
        if app.state.samples.state(str(identifier))["status"] != "COMPLETED":
            raise HTTPException(409, "O PDF temporário ainda não está disponível.")
        return FileResponse(
            app.state.samples.jobs[str(identifier)] / "original.pdf",
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="ensaio-temporario.pdf"'},
        )

    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    return app


app = create_app()
