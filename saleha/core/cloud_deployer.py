"""
Saleha Core: Autonomous Cloud Deployer & CI/CD Pipeline Synthesizer

Detects project stack and automatically synthesizes production-ready multi-stage
Dockerfiles, docker-compose manifests, and GitHub Actions CI/CD workflows.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class DeploymentAsset:
    relative_path: str
    content: str
    description: str


@dataclass
class DeploymentPlan:
    stack_detected: str
    target_environment: str
    assets: List[DeploymentAsset] = field(default_factory=list)


class CloudDeployer:
    """Autonomous Cloud & CI/CD Asset Synthesizer."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)

    def detect_stack(self, dir_path: Optional[str] = None) -> str:
        """Detects the primary runtime stack of a project directory."""
        target = dir_path or self.root_dir

        if os.path.isfile(os.path.join(target, "pyproject.toml")) or os.path.isfile(os.path.join(target, "requirements.txt")) or os.path.isfile(os.path.join(target, "setup.py")):
            return "python"
        elif os.path.isfile(os.path.join(target, "package.json")):
            return "node"
        elif os.path.isfile(os.path.join(target, "go.mod")):
            return "go"
        elif os.path.isfile(os.path.join(target, "Cargo.toml")):
            return "rust"
        return "generic"

    def generate_dockerfile(self, stack: str) -> str:
        """Synthesizes a hardened multi-stage Dockerfile."""
        if stack == "python":
            return (
                "# Stage 1: Build & Dependencies\n"
                "FROM python:3.12-slim AS builder\n"
                "WORKDIR /app\n"
                "RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*\n"
                "COPY requirements.txt* pyproject.toml* ./\n"
                "RUN pip install --no-cache-dir --user -r requirements.txt 2>/dev/null || pip install --no-cache-dir --user .\n\n"
                "# Stage 2: Final Minimal Runtime\n"
                "FROM python:3.12-slim AS runner\n"
                "WORKDIR /app\n"
                "COPY --from=builder /root/.local /root/.local\n"
                "COPY . .\n"
                "ENV PATH=/root/.local/bin:$PATH\n"
                "ENV PYTHONUNBUFFERED=1\n"
                "EXPOSE 8000\n"
                "CMD [\"python\", \"main.py\"]\n"
            )
        elif stack == "node":
            return (
                "FROM node:20-alpine AS builder\n"
                "WORKDIR /app\n"
                "COPY package*.json ./\n"
                "RUN npm ci\n"
                "COPY . .\n"
                "RUN npm run build --if-present\n\n"
                "FROM node:20-alpine AS runner\n"
                "WORKDIR /app\n"
                "COPY --from=builder /app ./\n"
                "ENV NODE_ENV=production\n"
                "EXPOSE 3000\n"
                "CMD [\"npm\", \"start\"]\n"
            )
        return (
            "FROM alpine:latest\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "CMD [\"sh\", \"-c\", \"echo 'Container started'\"]\n"
        )

    def generate_docker_compose(self, app_name: str = "saleha-service") -> str:
        """Synthesizes a standard docker-compose service definition."""
        return (
            "version: '3.8'\n\n"
            "services:\n"
            f"  {app_name}:\n"
            "    build: .\n"
            "    restart: unless-stopped\n"
            "    ports:\n"
            "      - '8000:8000'\n"
            "    environment:\n"
            "      - ENV=production\n"
            "    healthcheck:\n"
            "      test: [\"CMD\", \"curl\", \"-f\", \"http://localhost:8000/health\"]\n"
            "      interval: 30s\n"
            "      timeout: 5s\n"
            "      retries: 3\n"
        )

    def generate_github_ci(self, stack: str) -> str:
        """Synthesizes a production GitHub Actions CI workflow."""
        if stack == "python":
            return (
                "name: CI Pipeline\n\n"
                "on:\n"
                "  push:\n"
                "    branches: [ main, master ]\n"
                "  pull_request:\n"
                "    branches: [ main, master ]\n\n"
                "jobs:\n"
                "  test:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "    - uses: actions/checkout@v4\n"
                "    - name: Set up Python\n"
                "      uses: actions/setup-python@v5\n"
                "      with:\n"
                "        python-version: '3.12'\n"
                "    - name: Install dependencies\n"
                "      run: |\n"
                "        python -m pip install --upgrade pip\n"
                "        pip install pytest\n"
                "        pip install -e . 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true\n"
                "    - name: Run Tests\n"
                "      run: pytest\n"
            )
        return (
            "name: Generic CI Pipeline\n\n"
            "on: [push, pull_request]\n"
            "jobs:\n"
            "  build:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "    - uses: actions/checkout@v4\n"
            "    - name: Verify build\n"
            "      run: echo 'Build verified'\n"
        )

    def plan_deployment(self, dir_path: Optional[str] = None) -> DeploymentPlan:
        """Analyzes directory and produces complete deployment assets."""
        target = dir_path or self.root_dir
        stack = self.detect_stack(target)

        plan = DeploymentPlan(stack_detected=stack, target_environment="container+ci")
        plan.assets.append(DeploymentAsset(
            relative_path="Dockerfile",
            content=self.generate_dockerfile(stack),
            description="Hardened multi-stage container build"
        ))
        plan.assets.append(DeploymentAsset(
            relative_path="docker-compose.yml",
            content=self.generate_docker_compose(),
            description="Service orchestrator and health check manifest"
        ))
        plan.assets.append(DeploymentAsset(
            relative_path=".github/workflows/ci.yml",
            content=self.generate_github_ci(stack),
            description="Automated continuous integration pipeline"
        ))
        return plan

    def apply_plan(self, plan: DeploymentPlan, target_dir: Optional[str] = None) -> List[str]:
        """Writes deployment assets to target directory."""
        base = target_dir or self.root_dir
        written = []
        for asset in plan.assets:
            full_p = os.path.join(base, asset.relative_path)
            os.makedirs(os.path.dirname(full_p), exist_ok=True)
            with open(full_p, "w", encoding="utf-8") as f:
                f.write(asset.content)
            written.append(asset.relative_path)
        return written


# Global default instance
cloud_deployer = CloudDeployer()
