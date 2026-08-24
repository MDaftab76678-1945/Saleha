"""
Saleha Core: 1-Click Multi-Cloud & Kubernetes Deployment Generator

Synthesizes production-hardened multi-stage Dockerfiles, docker-compose manifests, and
Kubernetes Deployment/Service/Ingress configurations tailored to detected project runtimes.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class DeploymentPackage:
    app_name: str
    runtime: str
    port: int
    dockerfile: str
    docker_compose: str
    k8s_deployment: str
    k8s_service: str
    k8s_ingress: str


class CloudDeployer:
    """Generates production cloud and Kubernetes deployment artifacts."""

    def detect_runtime(self, root_dir: str = ".") -> str:
        """Detects project tech stack from root configuration files."""
        if os.path.isfile(os.path.join(root_dir, "requirements.txt")) or os.path.isfile(os.path.join(root_dir, "pyproject.toml")):
            return "python"
        if os.path.isfile(os.path.join(root_dir, "package.json")):
            return "nodejs"
        if os.path.isfile(os.path.join(root_dir, "go.mod")):
            return "go"
        if os.path.isfile(os.path.join(root_dir, "Cargo.toml")):
            return "rust"
        return "python"

    def generate_package(self, root_dir: str = ".", app_name: str = "saleha-app", port: int = 8000) -> DeploymentPackage:
        """Synthesizes complete deployment package."""
        rt = self.detect_runtime(root_dir)

        # 1. Multi-Stage Dockerfile
        if rt == "python":
            df = (
                "FROM python:3.11-slim AS builder\n"
                "WORKDIR /app\n"
                "COPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt\n\n"
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages\n"
                "COPY . .\n"
                f"EXPOSE {port}\n"
                "USER 10001\n"
                f"CMD [\"saleha\", \"serve\", \"--host\", \"0.0.0.0\", \"--port\", \"{port}\", \"--no-open\"]\n"
            )
        elif rt == "nodejs":
            df = (
                "FROM node:20-alpine AS builder\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci --only=production\n"
                "FROM node:20-alpine\nWORKDIR /app\nCOPY --from=builder /app/node_modules ./node_modules\nCOPY . .\n"
                f"EXPOSE {port}\nUSER node\nCMD [\"node\", \"server.js\"]\n"
            )
        else:
            df = (
                "FROM golang:1.22-alpine AS builder\nWORKDIR /app\nCOPY . .\nRUN go build -o service main.go\n"
                "FROM alpine:3.19\nWORKDIR /app\nCOPY --from=builder /app/service .\n"
                f"EXPOSE {port}\nCMD [\"./service\"]\n"
            )

        # 2. Docker Compose
        dc = (
            "version: '3.8'\n\n"
            "services:\n"
            f"  {app_name}:\n"
            "    build: .\n"
            f"    container_name: {app_name}\n"
            f"    ports:\n      - \"{port}:{port}\"\n"
            "    restart: unless-stopped\n"
            "    environment:\n      - ENV=production\n"
            "    healthcheck:\n"
            f"      test: [\"CMD\", \"curl\", \"-f\", \"http://localhost:{port}/health\"]\n"
            "      interval: 30s\n      timeout: 5s\n      retries: 3\n"
        )

        # 3. K8s Deployment
        k8s_deploy = (
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            f"  name: {app_name}\n"
            "  labels:\n"
            f"    app: {app_name}\n"
            "spec:\n"
            "  replicas: 3\n"
            "  selector:\n"
            "    matchLabels:\n"
            f"      app: {app_name}\n"
            "  template:\n"
            "    metadata:\n"
            "      labels:\n"
            f"        app: {app_name}\n"
            "    spec:\n"
            "      containers:\n"
            f"      - name: {app_name}\n"
            f"        image: {app_name}:latest\n"
            "        ports:\n"
            f"        - containerPort: {port}\n"
            "        resources:\n"
            "          limits:\n            cpu: '1'\n            memory: 1Gi\n"
            "          requests:\n           cpu: 100m\n           memory: 128Mi\n"
        )

        # 4. K8s Service
        k8s_svc = (
            "apiVersion: v1\n"
            "kind: Service\n"
            "metadata:\n"
            f"  name: {app_name}-service\n"
            "spec:\n"
            "  type: ClusterIP\n"
            "  selector:\n"
            f"    app: {app_name}\n"
            "  ports:\n"
            f"  - port: 80\n    targetPort: {port}\n"
        )

        # 5. K8s Ingress
        k8s_ing = (
            "apiVersion: networking.k8s.io/v1\n"
            "kind: Ingress\n"
            "metadata:\n"
            f"  name: {app_name}-ingress\n"
            "spec:\n"
            "  rules:\n"
            f"  - host: {app_name}.local\n"
            "    http:\n"
            "      paths:\n"
            "      - path: /\n        pathType: Prefix\n"
            "        backend:\n"
            "          service:\n"
            f"            name: {app_name}-service\n            port:\n              number: 80\n"
        )

        return DeploymentPackage(
            app_name=app_name,
            runtime=rt,
            port=port,
            dockerfile=df,
            docker_compose=dc,
            k8s_deployment=k8s_deploy,
            k8s_service=k8s_svc,
            k8s_ingress=k8s_ing
        )

    def export_package(self, pkg: DeploymentPackage, output_dir: str) -> List[str]:
        """Writes deployment configuration files to disk."""
        os.makedirs(output_dir, exist_ok=True)
        files_written = []

        mapping = {
            "Dockerfile": pkg.dockerfile,
            "docker-compose.yml": pkg.docker_compose,
            "k8s-deployment.yaml": pkg.k8s_deployment,
            "k8s-service.yaml": pkg.k8s_service,
            "k8s-ingress.yaml": pkg.k8s_ingress
        }

        for filename, content in mapping.items():
            p = os.path.join(output_dir, filename)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            files_written.append(p)

        return files_written


# Global instance
cloud_deployer = CloudDeployer()

