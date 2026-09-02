"""
Saleha Agents: DevOps & CI/CD Deployment Agent

Synthesizes production Docker multi-stage containers, Kubernetes manifests,
GitHub Actions CI/CD deployment pipelines, and Nginx reverse proxies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from saleha.agents.base_agent import BaseAgent, AgentResponse


@dataclass
class DevOpsPipelineSpec:
    project_name: str
    dockerfile: str
    docker_compose: str
    github_actions_workflow: str
    nginx_conf: str
    model_used: str = ""


class DevOpsAgent(BaseAgent):
    """Principal DevOps & CI/CD Automation Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="DevOps", model=model)

    def generate_devops_pipeline(
        self,
        project_name: str,
        runtime: str = "python:3.12-slim"
    ) -> DevOpsPipelineSpec:
        """Synthesizes complete containerization and automated deployment pipelines."""
        dockerfile = f"""# ==============================================================================
# Production Multi-Stage Dockerfile for: {project_name}
# ==============================================================================

FROM {runtime} AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM {runtime} AS final
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8000
CMD ["python", "-m", "saleha.server.web_server"]
"""

        compose = f"""version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
    restart: unless-stopped
"""

        ci = """name: CI/CD Pipeline
on: [push, pull_request]
jobs:
  test-and-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest
"""

        nginx = """server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}"""

        return DevOpsPipelineSpec(
            project_name=project_name,
            dockerfile=dockerfile,
            docker_compose=compose,
            github_actions_workflow=ci,
            nginx_conf=nginx,
            model_used=self.model_preference
        )
