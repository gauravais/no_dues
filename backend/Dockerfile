FROM python:3.12-slim

# Install system dependencies and ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official binary image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create non-root user
RUN useradd -m -u 10001 -s /bin/bash appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy dependency specifications first for Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies without root project
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source code, migrations, and scripts
COPY README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY scripts ./scripts
COPY docker-entrypoint.sh ./docker-entrypoint.sh

# Complete uv sync for the project package
RUN uv sync --frozen --no-dev

# Fix ownership and execution permissions
RUN chmod +x ./docker-entrypoint.sh && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
