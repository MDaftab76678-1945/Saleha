# ==============================================================================
# Saleha AI: Production Multi-Stage Container Image
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY saleha ./saleha

RUN pip install --no-cache-dir --upgrade pip setuptools wheel build && \
    pip install --no-cache-dir .

# Final Production Stage
FROM python:3.12-slim AS runner

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/saleha /usr/local/bin/saleha
COPY . .

ENV PYTHONUNBUFFERED=1
ENV SALEHA_ENV=production
ENV SALEHA_HOST=0.0.0.0
ENV SALEHA_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["saleha"]
CMD ["dev", "--port", "8000"]
