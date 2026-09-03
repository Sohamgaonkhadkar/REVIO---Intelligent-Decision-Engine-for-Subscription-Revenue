# One image, two runtime roles (api/ops) — PHASE_4 §5.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir . && pip install --no-cache-dir "psycopg[binary]" uvicorn

COPY core ./core
COPY apps ./apps
COPY adapters ./adapters
COPY sim ./sim
COPY configs ./configs
COPY db ./db
COPY scripts ./scripts
COPY tools ./tools

# Non-root runtime user
RUN useradd -m rd && chown -R rd:rd /app
USER rd

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
