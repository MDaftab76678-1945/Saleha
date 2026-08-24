# Multi-Stage Production Dockerfile for Saleha AI Platform
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml setup.py README.md ./
COPY saleha/ ./saleha/

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

FROM python:3.11-slim

WORKDIR /workspace

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/saleha /usr/local/bin/saleha

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    nodejs \
    npm \
    golang \
    default-jre \
    && rm -rf /var/lib/apt/lists/*

ENV OLLAMA_HOST="http://host.docker.internal:11434"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000 8080

ENTRYPOINT ["saleha"]
CMD ["serve", "--port", "8000", "--no-open"]

