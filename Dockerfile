FROM ghcr.io/astral-sh/uv:0.13.1 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app \
    && mkdir -p /data/raw && chown app:app /data/raw /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/medguide src/medguide
COPY alembic.ini ./
COPY migrations migrations
RUN uv sync --frozen --no-dev && chown -R app:app /app
USER app
CMD ["uvicorn", "medguide.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
