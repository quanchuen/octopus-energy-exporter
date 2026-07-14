# syntax=docker/dockerfile:1

########## builder: resolve deps into a venv using uv ##########
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first, from the lockfile only, so this layer is cached
# until pyproject.toml / uv.lock change. --no-dev drops pytest; --no-install-project
# defers installing our own code so app edits don't bust the dependency cache.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Now bring in the source and install the project itself.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

########## runtime: slim image with just the venv + code ##########
FROM python:3.14-slim-bookworm AS runtime

# Non-root user
RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    EXPORTER_PORT=9090 \
    EXPORTER_ADDR=0.0.0.0

USER app
EXPOSE 9090

# exec form => python is PID 1 and receives SIGTERM, which main.py handles for
# graceful shutdown.
CMD ["python", "main.py"]

# Liveness: scrape our own /metrics endpoint (no curl in slim image).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9090/metrics').read()"]
