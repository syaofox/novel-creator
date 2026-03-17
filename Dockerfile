# ============================================================
# Stage 1: Install Python dependencies
# ============================================================
FROM python:3.13-slim AS deps

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ============================================================
# Stage 2: Build CSS assets
# ============================================================
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY app/static ./app/static
RUN npm run build:css

# ============================================================
# Stage 3: Production runtime
# ============================================================
FROM python:3.13-slim AS production

WORKDIR /app

COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN mkdir -p data books && \
    groupadd --gid 1000 nonroot && \
    useradd --uid 1000 --gid nonroot --shell /bin/bash --create-home nonroot

COPY --from=builder /app/app/static ./app/static
COPY --chown=nonroot:nonroot . .

USER nonroot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
