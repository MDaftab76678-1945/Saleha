"""
Saleha Agents: DevOps & CI/CD Deployment Agent

Writes a Dockerfile, docker-compose.yml, a GitHub Actions workflow and an
nginx config for a project -- and checks each one before calling it done:
the Dockerfile's instructions, the YAML of the compose file and the
workflow (services, jobs, steps), the nginx braces and semicolons.

When a project directory is given, what can be read from it is read, not
guessed: the language, the entry point, the test command, the port. With
no model answering, the same facts fill a fixed template (`is_template`),
whose CMD is the project's own entry point -- it used to start Saleha's own
web server for every project.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import BaseAgent


@dataclass
class DevOpsPipelineSpec:
    project_name: str
    dockerfile: str
    docker_compose: str
    github_actions_workflow: str
    nginx_conf: str
    model_used: str = ""
    # True when no model answered and the files are the fixed template
    # filled with the project facts below.
    is_template: bool = True
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None      # True: every check passed; None: nothing could be checked
    facts: Dict[str, Any] = field(default_factory=dict)


def project_facts(project_dir: Optional[str]) -> Dict[str, Any]:
    """Language, entry point, test command and port, read from the project's own files."""
    facts: Dict[str, Any] = {"language": "python", "entry": "", "test": "pytest", "port": 8000,
                             "install": "pip install --no-cache-dir -r requirements.txt"}
    if not project_dir or not os.path.isdir(project_dir):
        return facts
    has = lambda rel: os.path.exists(os.path.join(project_dir, rel))  # noqa: E731
    python_project = any(has(f) for f in ("pyproject.toml", "requirements.txt", "setup.py", "manage.py"))
    if has("package.json") and not python_project:
        try:
            with open(os.path.join(project_dir, "package.json"), encoding="utf-8") as fh:
                pkg = json.load(fh)
        except (OSError, ValueError):
            pkg = {}
        scripts = pkg.get("scripts") or {}
        facts.update(language="node", port=3000, install="npm ci" if has("package-lock.json") else "npm install",
                     test="npm test" if "test" in scripts else "",
                     entry="npm start" if "start" in scripts else f"node {pkg.get('main') or 'index.js'}")
        return facts
    if has("pyproject.toml") and not has("requirements.txt"):
        facts["install"] = "pip install --no-cache-dir ."
    for candidate in ("main.py", "app.py", "manage.py", "server.py", "wsgi.py"):
        if has(candidate):
            facts["entry"] = (f"python {candidate} runserver 0.0.0.0:8000" if candidate == "manage.py"
                              else f"python {candidate}")
            break
    if not facts["entry"] and has("pyproject.toml"):
        try:
            with open(os.path.join(project_dir, "pyproject.toml"), encoding="utf-8") as fh:
                m = re.search(r"\[project\.scripts\]\s*\n\s*([\w.-]+)\s*=", fh.read())
            if m:
                facts["entry"] = m.group(1)
        except OSError:
            pass
    facts["test"] = "pytest" if has("tests") or has("test") else ""
    return facts


def _template(project_name: str, runtime: str, facts: Dict[str, Any]) -> Tuple[str, str, str, str]:
    entry = facts.get("entry") or "python main.py"
    port = facts.get("port", 8000)
    node = facts.get("language") == "node"
    base = "node:20-slim" if node and runtime.startswith("python") else runtime
    copy_deps = "COPY package*.json ./" if node else "COPY requirements.txt* pyproject.toml* ./"
    dockerfile = (f"# Template (no model answered) for: {project_name}\n"
                  f"FROM {base}\nWORKDIR /app\n{copy_deps}\nRUN {facts['install']}\nCOPY . .\n"
                  f"EXPOSE {port}\nCMD {json.dumps(entry.split())}\n")
    compose = (f"services:\n  app:\n    build: .\n    ports:\n      - \"{port}:{port}\"\n"
               "    restart: unless-stopped\n")
    setup = ("      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n" if node else
             "      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n")
    test = f"      - run: {facts['test']}\n" if facts.get("test") else ""
    ci = ("name: CI\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n"
          f"      - uses: actions/checkout@v4\n{setup}      - run: {facts['install']}\n{test}")
    nginx = ("server {\n    listen 80;\n    server_name _;\n\n    location / {\n"
             f"        proxy_pass http://app:{port};\n        proxy_set_header Host $host;\n"
             "        proxy_set_header X-Real-IP $remote_addr;\n    }\n}\n")
    return dockerfile, compose, ci, nginx


def check_all(dockerfile: str, compose: str, ci: str, nginx: str) -> List[ac.Check]:
    return [ac.check_dockerfile(dockerfile),
            ac.check_yaml(compose, "docker-compose.yml", ac.compose_problem),
            ac.check_yaml(ci, "CI workflow", ac.workflow_problem),
            ac.check_nginx(nginx)]


class DevOpsAgent(BaseAgent):
    """Principal DevOps & CI/CD Automation Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="DevOps", model=model)

    def generate_devops_pipeline(self, project_name: str, runtime: str = "python:3.12-slim",
                                 project_dir: Optional[str] = None, description: str = "") -> DevOpsPipelineSpec:
        """Deployment files for the project, each checked; the template when no model answers."""
        facts = project_facts(project_dir)
        prompt = (
            f"Write deployment files for the project `{project_name}`.\n"
            + (f"What it is: {description}\n" if description else "")
            + f"Facts read from the project (use them exactly): language={facts['language']}, "
              f"install command=`{facts['install']}`, start command=`{facts['entry'] or 'unknown'}`, "
              f"test command=`{facts['test'] or 'none'}`, port={facts['port']}, base image={runtime}.\n"
              "Answer with exactly four fenced blocks, in this order:\n"
              "1. a dockerfile block: the Dockerfile (multi-stage if useful; CMD runs the start command)\n"
              "2. a yaml block: docker-compose.yml with a `services:` mapping\n"
              "3. a yaml block: .github/workflows/ci.yml with `on:` and `jobs:` (each job has runs-on and steps)\n"
              "4. an nginx block: a server block proxying to the app\n"
              "Put only the language after each opening fence. No other text.")

        def build(content: str) -> Tuple[Tuple[str, str, str, str], List[ac.Check]]:
            blocks = ac.fenced_blocks(content)
            yamls = [b for info, b in blocks if info.split()[:1] in (["yaml"], ["yml"])]
            dockerfile = ac.pick(blocks, ("dockerfile", "docker"), starts="from ")
            compose = next((y for y in yamls if re.search(r"(?m)^services:", y)), "")
            ci = next((y for y in yamls if re.search(r"(?m)^jobs:", y)), "")
            nginx = ac.pick(blocks, ("nginx", "conf"), contains=r"server\s*\{")
            files = (dockerfile, compose, ci, nginx)
            return files, check_all(*files)

        files, checks, resp, _rounds = ac.produce(self, prompt, build)
        is_template = files is None or not files[0]
        if is_template:
            note = ac.fallback_note(checks, files is not None)
            files = _template(project_name, runtime, facts)
            checks = note + check_all(*files)
        dockerfile, compose, ci, nginx = files
        return DevOpsPipelineSpec(
            project_name=project_name, dockerfile=dockerfile, docker_compose=compose,
            github_actions_workflow=ci, nginx_conf=nginx,
            model_used="template (no usable model answer)" if is_template else resp.model_used,
            is_template=is_template, checks=ac.as_dicts(checks), verified=ac.artifact_verdict(checks),
            facts=facts)
