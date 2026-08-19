FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY daemon.py ./
COPY utils/ ./utils/
COPY services/ ./services/
COPY scheduler/ ./scheduler/
COPY models/ ./models/
COPY config/ ./config/
COPY scripts/ ./scripts/

RUN mkdir -p /app/state /app/retry_queue /app/logs

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd -m -u 1000 digisim && chown -R digisim:digisim /app
USER digisim

ENTRYPOINT ["python", "daemon.py"]
